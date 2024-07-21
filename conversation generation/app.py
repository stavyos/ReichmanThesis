import json
import os
import random
import re
import threading
import time
from typing import List, Dict, Tuple

import requests
from dotenv import load_dotenv
from flask import Flask, request, render_template, jsonify
from sshtunnel import SSHTunnelForwarder
from transformers import AutoTokenizer

import mongodb.mongo as mongo
import openai_api
from get_env_path import get_env_path
from mongodb.participant_info import ParticipantInfo, Gender
from xm import qualtrics

load_dotenv(get_env_path())

app = Flask(__name__, static_url_path='/static')

MODEL_NAMES = {
    'gpt-j': 'EleutherAI/gpt-j-6B',
    'gpt-jt': 'togethercomputer/GPT-JT-6B-v1',
    'pythia-1b': 'EleutherAI/pythia-1b',
    'pythia-1.4b': 'EleutherAI/pythia-1.4b',
    'pythia-2.8b': 'EleutherAI/pythia-2.8b',
    'pythia-6.9b': 'EleutherAI/pythia-6.9b',
    'pythia-12b': 'EleutherAI/pythia-12b'
}

# TOKENIZER = AutoTokenizer.from_pretrained()
TOKENIZER = AutoTokenizer.from_pretrained(MODEL_NAMES['pythia-12b'])

CONVERSATION_FRAGMENT_LENGTH = int(os.getenv('CONVERSATION_FRAGMENT_LENGTH'))

REMOTE_HOST_IP = str(os.getenv('REMOTE_HOST_IP'))
REMOTE_HOST_PORT = int(os.getenv('REMOTE_HOST_PORT'))
LOCAL_HOST_IP = str(os.getenv('LOCAL_HOST_IP'))
SSH_USERNAME = str(os.getenv('SSH_USERNAME'))
SSH_PASSWORD = str(os.getenv('SSH_PASSWORD'))
REMOTE_HOST_BIND_PORT = int(os.getenv('REMOTE_HOST_BIND_PORT'))
PRE_PROMPT = 'The Therapist is an expert in motivational interviewing and his goal is to motivate the Patient to' \
             ' change his or her behavior.'


def predict(text_to_inference: str, max_tokens: int, temperature: float,
            open_ai_model: openai_api.Model = None) -> Dict[str, str]:
    if open_ai_model is not None:
        return openai_api.predict(text_to_inference=text_to_inference, model=open_ai_model,
                                  max_tokens=max_tokens, temperature=temperature)

    local_host_random_port = random.randint(5000, 9999)

    server = SSHTunnelForwarder(
        (REMOTE_HOST_IP, REMOTE_HOST_PORT),
        ssh_username=SSH_USERNAME,
        ssh_password=SSH_PASSWORD,
        remote_bind_address=(LOCAL_HOST_IP, REMOTE_HOST_BIND_PORT),
        local_bind_address=(LOCAL_HOST_IP, local_host_random_port),
    )

    server.start()

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.0; WOW64; rv:24.0) Gecko/20100101 Firefox/24.0'}
    response = requests.get(f'http://127.0.0.1:{local_host_random_port}/predict', headers=headers,
                            params={"input_sentence": f'{text_to_inference.strip()}'}).content

    server.stop()

    res = json.loads(response.decode("utf-8"))
    return res


def trim_to_fragment(history: List[str], frag_length: int) -> List[str]:
    tokens_count = 0

    frag = []
    for utt in history[::-1]:
        utt_len = len(TOKENIZER(utt).input_ids)
        tokens_count += utt_len
        if tokens_count < frag_length:
            frag.append(utt)

    frag = frag[::-1]
    return frag


@app.route("/login", methods=['GET', 'POST'])
def login():
    # noinspection PyUnresolvedReferences
    return render_template("login.html")


@app.route("/new_participant", methods=['GET', 'POST'])
def new_participant():
    ref = request.args.get('ref', None)

    if ref is None:
        return 'Error, ref is required.'

    # noinspection PyUnresolvedReferences
    return render_template("new_participant.html", ref=ref)


@app.route("/info", methods=['GET', 'POST'])
def info():
    ref = request.form['ref']
    participant_id = mongo.gen_new_participant_id()

    if request.referrer is not None and 'new_participant' in request.referrer:
        # noinspection PyUnresolvedReferences
        return render_template("info.html", ref=ref, participant_id=participant_id, email=request.form['email'])


def get_info_from_form() -> ParticipantInfo:
    email = request.form['email']
    gender = Gender.Female
    if request.form['gender'] == 'Male':
        gender = Gender.Male
    elif request.form['gender'] == 'Other':
        gender = Gender.Other
    age = int(request.form['age'])
    years_of_education = request.form['yoe']
    is_native_en = True if request.form['native_en'] == 'Yes' else False
    is_cs_expert = True if request.form['cs_expert'] == 'Yes' else False
    is_psyc_expert = True if request.form['psy_expert'] == 'Yes' else False
    curr_in_therapy = True if request.form['curr_in_therapy'] == 'Yes' else False
    been_in_therapy = True if request.form['been_in_therapy'] == 'Yes' else False

    return ParticipantInfo(email=email, gender=gender, age=age, years_of_education=years_of_education,
                           is_native_en=is_native_en, is_cs_expert=is_cs_expert, is_psyc_expert=is_psyc_expert,
                           curr_in_therapy=curr_in_therapy, been_in_therapy=been_in_therapy)


@app.route('/instructions', methods=['GET', 'POST'])
def instructions():
    ref = request.form['ref']

    if request.referrer is not None and request.referrer.endswith('info'):
        participant_id = request.form['participant_id']
        participant_info = get_info_from_form()
        # noinspection PyUnresolvedReferences
        return render_template("instructions.html", ref=ref, participant_id=participant_id,
                               email=participant_info.email, gender=participant_info.gender,
                               age=participant_info.age, yoe=participant_info.years_of_education,
                               native_en=participant_info.is_native_en, cs_expert=participant_info.is_cs_expert,
                               psy_expert=participant_info.is_psyc_expert,
                               curr_in_therapy=participant_info.curr_in_therapy,
                               been_in_therapy=participant_info.been_in_therapy)


# noinspection PyUnresolvedReferences
@app.route("/session", methods=['GET', 'POST'])
def session():
    def history_to_jinja(_history: List[str]) -> List[Tuple[bool, str]]:
        _tmp = []
        for _utt in _history:
            if re.match(r'Therapist[ ]*:', _utt):
                _tmp.append((True, re.sub('Therapist[ ]*:', '', _utt).strip()))  # True for the therapist
            else:
                _tmp.append((False, re.sub('Patient[ ]*:', '', _utt).strip()))  # True for the patient

        return _tmp

    def history_to_ema_arr(_history: List[str]) -> str:
        _tmp = [-1]
        for _utt in _history:
            if re.match(r'Therapist[ ]*:', _utt):
                continue
            else:
                _tmp.append(len(re.sub('Patient[ ]*:', '', _utt).strip()))  # True for the patient

        return ','.join([str(_v) for _v in _tmp[-5:]])

    participant_id = int(request.form['participant_id'])
    ref = request.form['ref']
    if request.referrer is not None and request.referrer.endswith('instructions'):
        participant_info = get_info_from_form()

        res = mongo.add_new_session(ref=ref, participant_id=participant_id, email=participant_info.email,
                                    gender=participant_info.gender, age=participant_info.age,
                                    yoe=participant_info.years_of_education,
                                    is_native_en=participant_info.is_native_en,
                                    is_cs_expert=participant_info.is_cs_expert,
                                    is_psyc_expert=participant_info.is_psyc_expert,
                                    curr_in_therapy=participant_info.curr_in_therapy,
                                    been_in_therapy=participant_info.been_in_therapy)
        session_id, utt = res['session_id'], res['utterance']

        history = [(True, utt)]

        survey_link = mongo.get_survey_link(participant_id=participant_id, session_id=session_id)
        return render_template("session.html", ref=ref, participant_id=participant_id, session_id=session_id,
                               history=history, survey_link=survey_link)
    elif request.referrer is not None and request.referrer.endswith('login'):
        res = mongo.load_session(participant_id=participant_id)

        if res is None:
            return render_template('participant_not_found.html', participant_id=participant_id)

        session_id, history = res['session_id'], res['history']

        history_jinja = history_to_jinja(_history=history)
        history_patient = history_to_ema_arr(_history=history)
        survey_link = mongo.get_survey_link(participant_id=participant_id, session_id=session_id)

        return render_template("session.html", ref=ref, participant_id=participant_id, session_id=session_id,
                               history=history_jinja, history_patient_length=history_patient, survey_link=survey_link)
    elif request.referrer is not None and request.referrer.endswith('session'):
        res = mongo.load_session(participant_id=participant_id)
        session_id, history = res['session_id'], res['history']

        if request.referrer is not None and request.referrer.endswith('session'):
            text_to_inference = request.form['text_to_inference'].strip()

            history = list(map(lambda x: x.strip(), history))
            history = list(filter(lambda x: len(x) > 0, history))

            his = '\n'.join(history)
            if len(history) < 4:
                pre_prompt = f'{PRE_PROMPT.strip()}\n\n'
            else:
                pre_prompt = ''

            to_infe = f'{pre_prompt}{his.strip()}\nPatient: {text_to_inference}\nTherapist: '

            hs = trim_to_fragment(history=to_infe.split('\n'), frag_length=CONVERSATION_FRAGMENT_LENGTH)
            to_infe = '\n'.join(hs)

            ts_utt_user = time.time()
            retries = 0
            model_name, answer = '', ''
            while len(answer.strip()) == 0 or answer.startswith('_'):
                retries += 1
                for _ in range(5):
                    try:
                        response = predict(text_to_inference=to_infe)
                        break
                    except:
                        time.sleep(1)
                # noinspection PyUnboundLocalVariable
                model_name, answer = response['model_name'], response['answer'].strip()

                search_res = re.search(r'(([pP]atient)|([tT]herapist)[ ]*:)|(<[|]endoftext[|]>)', answer)
                if search_res:
                    answer = answer[:search_res.span(0)[0]].strip()

                if len(answer.replace('.', '').strip()) == 0:  # Make sure the answer is not "..."
                    answer = ''

                answer = answer.strip()

            ts_utt_model = time.time()

            ex_info = {
                'pre_prompt': pre_prompt,
                'fragment_tokens_length': CONVERSATION_FRAGMENT_LENGTH
            }
            mongo.add_new_utterance(participant_id=participant_id, session_id=session_id, model_name=model_name,
                                    model_utt=False, utt=text_to_inference, extra_info=ex_info, timestamp=ts_utt_user)
            mongo.add_new_utterance(participant_id=participant_id, session_id=session_id, model_name=model_name,
                                    model_utt=True, utt=answer, retries=retries, timestamp=ts_utt_model)

            history.append(f'Patient: {text_to_inference}')
            history.append(f'Therapist: {answer}')

            history = list(map(lambda x: f'{x}\n', history))
            history[-1] = history[-1].strip()

        history_jinja = history_to_jinja(_history=history)
        history_patient = history_to_ema_arr(_history=history)
        survey_link = mongo.get_survey_link(participant_id=participant_id, session_id=session_id)

        return render_template("session.html", ref=ref, participant_id=participant_id, session_id=session_id,
                               history=history_jinja, history_patient_length=history_patient, survey_link=survey_link)
    else:
        pass


@app.route('/talk_with_ai/add_new_participant', methods=['POST', 'GET'])
def talk_with_ai_add_new_participant():
    participant_id = mongo.gen_new_participant_id()
    gender = Gender(int(request.form['gender']))
    ref = request.form['reference']
    email = request.form['email']
    age = int(request.form['age'])
    yoe = request.form['yoe']
    is_native_en = bool(request.form['is_native_en'])
    is_cs_expert = bool(request.form['is_cs_expert'])
    is_psyc_expert = bool(request.form['is_psyc_expert'])
    curr_in_therapy = bool(request.form['curr_in_therapy'])
    been_in_therapy = bool(request.form['been_in_therapy'])
    init_utterance = request.form['init_utterance'] if 'init_utterance' in request.form else None
    extra_info = json.loads(request.form['extra_info']) if 'extra_info' in request.form else None

    res = mongo.add_new_session(ref=ref, participant_id=participant_id, email=email, gender=gender,
                                age=age, yoe=yoe, is_native_en=is_native_en, is_cs_expert=is_cs_expert,
                                is_psyc_expert=is_psyc_expert, curr_in_therapy=curr_in_therapy,
                                been_in_therapy=been_in_therapy, init_utterance=init_utterance, extra_info=extra_info)

    session_id, utt = res['session_id'], res['utterance']

    return jsonify({
        'participant_id': participant_id,
        'session_id': session_id,
        'utterance': utt
    })


@app.route('/talk_with_ai/predict', methods=['POST'])
def talk_with_ai_predict():
    text_to_inference = request.form['text_to_inference']

    response = predict(text_to_inference=text_to_inference, max_tokens=512, temperature=0.9)
    model_name, answer = response['model_name'], response['answer'].strip()

    return jsonify({
        'model_name': model_name,
        'answer': answer
    })


threading.Thread(target=qualtrics.auto_links_updater).start()
time.sleep(3)
threading.Thread(target=qualtrics.auto_response_updater).start()

# Hide in production
if __name__ == "__main__":
    app.run(debug=True)
