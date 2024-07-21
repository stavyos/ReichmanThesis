import http.client
import json
import os
import time
from typing import Tuple, List, Dict


from QualtricsAPI import Responses
from QualtricsAPI.XM import MailingList

import mongo

os.environ['token'] = 'MYQm22dxYO0tsQ6o6UPSa4Xf6THvpqTx99aaM0Xf'
os.environ['data_center'] = 'sjc1'
os.environ['directory_id'] = 'POOL_3nUCQkhzyoceRg2'

MAILING_LIST = 'CG_2uvMA0rVMexhxE6'
SURVEY = 'SV_8kWc1MTpZcGLBOu'
DISTRIBUTION = 'EMD_PC5R0TCzZ9GRZ4y'


def add_new_participant(participant_id: str, session_id: str) -> Tuple[str, str]:
    m = MailingList(token=os.environ['token'], data_center=os.environ['data_center'],
                    directory_id=os.environ['directory_id'])

    contact_id, contact_list_id = m.create_contact_in_list(mailing_list=MAILING_LIST,
                                                           first_name=participant_id, last_name=session_id)
    return contact_id, contact_list_id


# noinspection PyTypeChecker
def auto_links_updater():
    def get_dist_links(distribution_id: str, survey_id: str, skip_token: str = '0') -> dict:
        conn = http.client.HTTPSConnection(f"{os.environ['data_center']}.qualtrics.com")

        headers = {
            'Content-Type': "application/json",
            'X-API-TOKEN': os.environ['token']
        }

        endpoint = f"/API/v3/distributions/{distribution_id}/links?skipToken={skip_token}&surveyId={survey_id}"
        conn.request("GET", endpoint, headers=headers)

        res = conn.getresponse()
        data = res.read().decode('utf-8')

        return json.loads(data)

    def get_all_dist_links(distribution_id: str, survey_id: str) -> List[Dict[str, str]]:
        pages = [get_dist_links(distribution_id=distribution_id, survey_id=survey_id)]

        while pages[-1]['result']['nextPage'] is not None:
            nxt_page = pages[-1]['result']['nextPage']
            skip_token = nxt_page[nxt_page.find('skipToken=') + len('skipToken='):]
            pages.append(get_dist_links(distribution_id=distribution_id,
                                        survey_id=survey_id, skip_token=skip_token))

        return pages

    while True:
        try:
            print(f'({int(time.time())}) Start updating distribution links')

            dist_data = get_all_dist_links(distribution_id=DISTRIBUTION, survey_id=SURVEY)

            links_dict = {}
            for x in dist_data:
                for user in x['result']['elements']:
                    participant_id = user['firstName']
                    session_id = user['lastName']
                    link = user['link']
                    links_dict[f'{participant_id}_{session_id}'] = link

            for x in mongo.TABLE.find(filter={'survey_link': ''}):
                participant_id = x['participant_id']
                session_id = x['session_id']

                if f'{participant_id}_{session_id}' not in links_dict:
                    continue

                survey_link = links_dict[f'{participant_id}_{session_id}']
                mongo.update_survey_link(participant_id=participant_id, session_id=session_id, survey_link=survey_link)

            time.sleep(10)
        except:
            pass


def auto_response_updater():
    while True:
        try:
            print(f'({int(time.time())}) Start updating responses status')

            unanswered_surveys = mongo.get_all_unanswered_surveys()

            r = Responses()
            df = r.get_survey_responses(survey=SURVEY)

            for row in df.iterrows():
                response_id = row[1]['ResponseId']
                participant_id = row[1]['RecipientFirstName']
                session_id = row[1]['RecipientLastName']
                if not participant_id.isnumeric() or not session_id.isnumeric():
                    continue

                if f'{participant_id}_{session_id}' in unanswered_surveys:
                    mongo.mark_survey_as_completed(participant_id=int(participant_id), session_id=int(session_id),
                                                   response_id=response_id)

            time.sleep(10)
        except:
            pass


def delete_survey_response(survey_id: str, response_id: str):
    conn = http.client.HTTPSConnection(f"{os.environ['data_center']}.qualtrics.com")

    headers = {
        'Content-Type': "application/json",
        'X-API-TOKEN': os.environ['token']
    }

    endpoint = f"/API/v3/surveys/{survey_id}/responses/{response_id}"
    conn.request("DELETE", endpoint, headers=headers)

    res = conn.getresponse()
    data = res.read().decode('utf-8')

    return json.loads(data)
