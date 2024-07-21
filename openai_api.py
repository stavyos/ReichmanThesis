import os
from enum import Enum
from typing import Dict

import openai
from dotenv import load_dotenv

from get_env_path import get_env_path

load_dotenv(get_env_path())

openai.api_key = os.getenv('OPEN_AI_API_KEY')


class Model(Enum):
    Ada = 0,  # text-ada-001
    Davinci = 1,  # text-davinci-003
    ChatGPT = 2  # gpt-3.5-turbo
    ChatGPT16K = 3  # gpt-3.5-turbo-16k


def get_model_name(model: Model) -> str:
    if model is Model.Ada:
        return 'text-ada-001'
    elif model is Model.Davinci:
        return 'text-davinci-003'
    elif model is Model.ChatGPT:
        return 'gpt-3.5-turbo'
    elif model is Model.ChatGPT16K:
        return 'gpt-3.5-turbo-16k'


def predict(text_to_inference: str, model: Model, max_tokens: int, temperature: float) -> Dict[str, str]:
    if model is Model.ChatGPT:
        txt = text_to_inference[:]

        trim_idx = max(txt.find('Therapist:'), txt.find('Patient:'))
        txt = txt[:trim_idx]

        messages = txt.split('\n')
        for i in range(len(messages)):
            messages[i] = messages[i][:max(messages[i].find(' '), 0)].strip()
        if len(messages[-1]) == -1:
            messages.pop(len(messages) - 1)
    else:
        model_name = get_model_name(model=model)

        response = openai.Completion.create(
            model=model_name,
            prompt=text_to_inference,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=["therapist:", "Therapist:", "patient:", "Patient:"]
        )

        return {
            'model_name': model_name,
            'answer': response.choices[0].text.strip()
        }
