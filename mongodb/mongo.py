import os
import random
import time
from typing import List, Dict, Union, Tuple

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from participant_info import Gender
from xm import qualtrics

DB_NAME = 'thesis'
CLIENT = MongoClient('mongodb://localhost:27017')
DB: Database = CLIENT['thesis']
TABLE: Collection = DB['experiments']


def backup_db():
    backup_path = os.path.join(DB_NAME, str(int(time.time())))
    # create database back directory with db_name
    os.makedirs(backup_path, exist_ok=True)

    # list all tables in database
    tables = DB.list_collection_names()

    # dump all tables in db
    for table in tables:
        print("exporting data for table", table)
        data = list(DB[table].find())
        # write data in json file
        with open(f"{os.path.join(backup_path, table)}.json", "w", encoding='UTF-8') as writer:
            writer.write(str(data))


# backup_db()
# print('Back up completed')


def gen_unique_id() -> int:
    a = str(random.randint(10, 99))
    c = str(random.randint(10, 99))
    b = str(time.time()).replace('.', '')
    b = int(b) % 10000000

    return int(f'{a}{b}{c}')


def gen_new_participant_id() -> int:
    participant_id = gen_unique_id()

    while is_participant_exists(participant_id=participant_id):
        participant_id = gen_unique_id()

    return participant_id


def is_participant_exists(participant_id: int) -> bool:
    return TABLE.find_one(filter={'participant_id': participant_id}) is not None


def load_session(participant_id: int) -> Union[Dict[str, Union[int, List[str]]], None]:
    if not is_participant_exists(participant_id=participant_id):
        return None

    _filter = {
        'participant_id': participant_id,
        'metadata': True,
        'survey_completed': False
    }

    incomplete_session_metadata = TABLE.find_one(filter=_filter)
    if incomplete_session_metadata is not None:
        _filter.pop('survey_completed')
        _filter['metadata'] = False
        _filter['session_id'] = incomplete_session_metadata['session_id']
        incomplete_session = TABLE.find_one(filter=_filter)

        history = []
        for itm in incomplete_session['session']:
            utt = itm['utt'].strip()
            prefix = 'Therapist :' if itm['model_utt'] else 'Patient :'
            history.append(f'{prefix} {utt}')
        return {
            'session_id': incomplete_session['session_id'],
            'history': history
        }
    else:
        _filter.pop('survey_completed')
        _filter['metadata'] = False
        completed_session = TABLE.find_one(filter=_filter)

        ref = str(completed_session['ref'])
        email = str(completed_session['info']['email'])
        gender = Gender(completed_session['info']['gender'])
        age = int(completed_session['info']['age'])
        yoe = str(completed_session['info']['yoe'])
        is_native_en = bool(completed_session['info']['is_native_en'])
        is_cs_expert = bool(completed_session['info']['is_cs_expert'])
        is_psyc_expert = bool(completed_session['info']['is_psyc_expert'])
        curr_in_therapy = bool(completed_session['info']['curr_in_therapy'])
        been_in_therapy = bool(completed_session['info']['been_in_therapy'])
        res = add_new_session(ref=ref, participant_id=participant_id, email=email, gender=gender, age=age, yoe=yoe,
                              is_native_en=is_native_en, is_cs_expert=is_cs_expert, is_psyc_expert=is_psyc_expert,
                              curr_in_therapy=curr_in_therapy, been_in_therapy=been_in_therapy)

        session_id = res['session_id']

        return {
            'session_id': session_id,
            'history': [f'Therapist: {res["utterance"].strip()}']
        }


def get_patient_info(participant_id: int):
    _filter = {
        'participant_id': participant_id,
        'metadata': True,
        'survey_completed': False
    }

    incomplete_session_metadata = TABLE.find_one(filter=_filter)
    if incomplete_session_metadata is not None:
        _filter.pop('survey_completed')
        _filter['metadata'] = False
        _filter['session_id'] = incomplete_session_metadata['session_id']
        incomplete_session = TABLE.find_one(filter=_filter)

        history = []
        for itm in incomplete_session['session']:
            utt = itm['utt'].strip()
            prefix = 'Therapist :' if itm['model_utt'] else 'Patient :'
            history.append(f'{prefix} {utt}')
        return {
            'session_id': incomplete_session['session_id'],
            'history': history
        }
    else:
        _filter.pop('survey_completed')
        _filter['metadata'] = False
        completed_session = TABLE.find_one(filter=_filter)

        ref = str(completed_session['ref'])
        email = str(completed_session['info']['email'])
        gender = Gender(completed_session['info']['gender'])
        age = int(completed_session['info']['age'])
        yoe = str(completed_session['info']['yoe'])
        is_native_en = bool(completed_session['info']['is_native_en'])
        is_cs_expert = bool(completed_session['info']['is_cs_expert'])
        is_psyc_expert = bool(completed_session['info']['is_psyc_expert'])
        curr_in_therapy = bool(completed_session['info']['curr_in_therapy'])
        been_in_therapy = bool(completed_session['info']['been_in_therapy'])
        res = add_new_session(ref=ref, participant_id=participant_id, email=email, gender=gender, age=age, yoe=yoe,
                              is_native_en=is_native_en, is_cs_expert=is_cs_expert, is_psyc_expert=is_psyc_expert,
                              curr_in_therapy=curr_in_therapy, been_in_therapy=been_in_therapy)

        session_id = res['session_id']

        return {
            'session_id': session_id,
            'history': [f'Therapist : {res["utterance"].strip()}']
        }


def add_new_session(ref: str, participant_id: int, email: str, gender: Gender, age: int, yoe: str, is_native_en: bool,
                    is_cs_expert: bool, is_psyc_expert: bool, curr_in_therapy: bool, been_in_therapy: bool,
                    init_utterance: str = None, extra_info: dict = None) -> Dict[str, Union[str, int]]:
    info_page_data = {
        'email': email,
        'gender': gender.value,
        'age': age,
        'yoe': yoe,
        'is_native_en': is_native_en,
        'is_cs_expert': is_cs_expert,
        'is_psyc_expert': is_psyc_expert,
        'curr_in_therapy': curr_in_therapy,
        'been_in_therapy': been_in_therapy,
        'timestamp': time.time()
    }

    session_id = gen_unique_id()
    TABLE.insert_one({
        'ref': ref,
        'participant_id': participant_id,
        'session_id': session_id,
        'metadata': False,
        'info': info_page_data,
        'timestamp': time.time()
    })

    add_participant_metadata(participant_id=participant_id, session_id=session_id)

    if init_utterance is None:
        init_utterance = 'Hello, welcome to your first motivational session with me. ' \
                         'My name is Mike and I’m a professional motivational counselor therapist. ' \
                         'Can you start by tell me little bit about yourself and why you are here?'
    add_new_utterance(participant_id=participant_id, session_id=session_id,
                      model_name='Template', model_utt=True, utt=init_utterance, extra_info=extra_info)

    return {
        'session_id': session_id,
        'utterance': init_utterance
    }


def add_new_utterance(participant_id: int, session_id: int, model_name: str, model_utt: bool, utt: str,
                      extra_info: dict = None, retries: int = 1, timestamp: float = None):
    _filter = {
        'participant_id': participant_id,
        'session_id': session_id
    }

    if timestamp is None:
        timestamp = time.time()

    session = {
        'model_name': model_name,
        'model_utt': model_utt,
        'utt': utt,
        'retries': retries,
        'timestamp': timestamp
    }

    if extra_info is not None:
        session['extra_info'] = extra_info

    push = {'$push': {
        'session': session
    }}

    TABLE.update_one(filter=_filter, update=push)


def insert_questionnaire(participant_id: int, session_id: int, questions_and_answers: List[Tuple[str, int, int]],
                         good_words: str, bad_words: str):
    _filter = {
        'participant_id': participant_id,
        'session_id': session_id,
        'metadata': False
    }
    push = {'$set': {
        'questionnaire': {
            'questions_and_answers': questions_and_answers,
            'good_words': good_words,
            'bad_words': bad_words,
            'timestamp': time.time()
        }
    }}

    TABLE.update_one(filter=_filter, update=push)


def add_participant_metadata(participant_id: int, session_id: int):
    contact_id, contact_list_id = qualtrics.add_new_participant(participant_id=str(participant_id),
                                                                session_id=str(session_id))
    TABLE.insert_one({
        'participant_id': participant_id,
        'session_id': session_id,
        'metadata': True,
        'contact_id': contact_id,
        'contact_list_id': contact_list_id,
        'survey_link': '',
        'survey_completed': False,
        'timestamp': time.time()
    })


def get_survey_link(participant_id: int, session_id: int) -> str:
    _filter = {
        'participant_id': participant_id,
        'session_id': session_id,
        'metadata': True
    }

    res = TABLE.find_one(filter=_filter)
    if res is None:
        return ''

    if 'survey_link' in res:
        return res['survey_link']
    else:
        return ''


def update_survey_link(participant_id: int, session_id: int, survey_link: str):
    _filter = {
        'participant_id': participant_id,
        'session_id': session_id,
        'metadata': True
    }
    push = {'$set': {
        'survey_link': survey_link
    }}

    print(f'\tUpdating (participant_id, session_id) - ({participant_id}, {session_id})')
    TABLE.update_one(filter=_filter, update=push)


def get_all_unanswered_surveys() -> Dict[str, str]:
    _filter = {
        'metadata': True,
        'survey_completed': False
    }

    _dict = {f"{row['participant_id']}_{row['session_id']}": '' for row in TABLE.find(filter=_filter)}
    return _dict


def mark_survey_as_completed(participant_id: int, session_id: int, response_id: int):
    _filter = {
        'participant_id': participant_id,
        'session_id': session_id,
        'metadata': True
    }
    push = {'$set': {
        'survey_completed': True,
        'response_id': response_id
    }}

    print(f'\tUpdating (participant_id, session_id) - ({participant_id}, {session_id})')
    TABLE.update_one(filter=_filter, update=push)


def get_email(participant_id: int, session_id: int) -> Union[str, None]:
    _filter = {
        'participant_id': participant_id,
        'session_id': session_id,
        'metadata': False
    }

    res = TABLE.find_one(filter=_filter)
    if res is None:
        return None

    return res['info']['email']
