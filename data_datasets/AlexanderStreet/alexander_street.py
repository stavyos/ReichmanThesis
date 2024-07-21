from __future__ import annotations

import json
import logging
import os.path
import random
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, Any
from typing import List, Tuple

ALEXANDER_STREET_JSON_FILENAME = os.path.join('dataset', 'alexander_street_dataset.json')

logger = logging.getLogger(__name__)
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(name)s -   %(message)s",
                    datefmt="%m/%d/%Y %H:%M:%S", handlers=[logging.StreamHandler(sys.stdout)])
logger.setLevel(logging.INFO)


class JsonExtension:
    def to_dict(self) -> Dict[str, Any]:
        raise NotImplementedError

    @staticmethod
    def from_dict(kwargs) -> Any:
        raise NotImplementedError


@dataclass()
class Conversation(JsonExtension):
    url: str
    title: str
    citation_info: str
    summary: str
    field_of_interest: str
    author: str
    publisher: str
    content_type: str
    page_count: int
    publication_year: int
    place_published: str
    subject: str
    presenting_condition: str
    clinician: str
    utterances: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    @staticmethod
    def from_dict(kwargs: dict) -> Conversation:
        return Conversation(**kwargs)


@dataclass()
class Volume(JsonExtension):
    conversations: List[Conversation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'conversations': [conv.to_dict() for conv in self.conversations]
        }

    @staticmethod
    def from_dict(kwargs) -> Volume:
        convs = [Conversation.from_dict(conv) for conv in kwargs['conversations']]
        return Volume(conversations=convs)


class AlexanderStreetDataset(JsonExtension):
    def __init__(self):
        self.volume_ctrn = Volume()
        self.volume_psyc = Volume()

    def get_conversation_summary_dictionaries(self, volume_ctrn: bool = True,
                                              volume_psyc: bool = True) -> Tuple[Dict[str, List[str]], Dict[str, str]]:
        # noinspection PyTypeChecker
        convs: Dict[str, List[str]] = {}
        summary = {}

        if volume_ctrn:
            for i in range(len(self.volume_ctrn.conversations)):
                convs[f'ctrn_{i}'] = self.volume_ctrn.conversations[i].utterances.copy()
                summary[f'ctrn_{i}'] = self.volume_ctrn.conversations[i].summary[:]

        if volume_psyc:
            for i in range(len(self.volume_psyc.conversations)):
                convs[f'psyc_{i}'] = self.volume_psyc.conversations[i].utterances.copy()
                summary[f'psyc_{i}'] = self.volume_psyc.conversations[i].summary[:]

        return convs, summary

    def get_all_therapist_utterances(self, volume_ctrn: bool = True, volume_psyc: bool = True) -> List[str]:
        utterances: List[str] = []

        # noinspection DuplicatedCode
        if volume_ctrn:
            for i in range(len(self.volume_ctrn.conversations)):
                sentences = filter(lambda x: x.startswith('Therapist:'),
                                   self.volume_ctrn.conversations[i].utterances.copy())
                sentences = map(lambda x: x.replace('Therapist:', '').strip(), sentences)
                utterances.extend(list(sentences))

        # noinspection DuplicatedCode
        if volume_psyc:
            for i in range(len(self.volume_psyc.conversations)):
                sentences = filter(lambda x: x.startswith('Therapist:'),
                                   self.volume_psyc.conversations[i].utterances.copy())
                sentences = map(lambda x: x.replace('Therapist:', '').strip(), sentences)
                utterances.extend(list(sentences))

        return utterances

    def is_data_valid(self, ) -> bool:
        data, _ = self.get_conversation_summary_dictionaries()
        for k in data.keys():
            if len(data[k]) > 0:
                therapist_turn = True if re.match('^(Therapist: )[^ ]', data[k][0]) else False

                for seq in data[k]:
                    if not re.match(r'(^(Therapist: )[^ ])|(^(Patient: )[^ ])', seq):
                        msg = f'Therapist or Patient is not followed by space: {k}, {seq}'
                        logger.error(msg)
                        raise Exception(msg)

                    if therapist_turn:
                        if not re.match(r'^(Therapist: )[^ ]', seq):
                            msg = f'Patient is talking twice in a row: {k}, {seq}'
                            logger.error(msg)
                            raise Exception(msg)
                    else:
                        if not re.match(r'^(Patient: )[^ ]', seq):
                            msg = f'Therapist is talking twice in a row: {k}, {seq}'
                            logger.error(msg)
                            raise Exception(msg)

                    therapist_turn ^= True

        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'volume_ctrn': self.volume_ctrn.to_dict(),
            'volume_psyc': self.volume_psyc.to_dict()
        }

    @staticmethod
    def from_dict(kwargs) -> AlexanderStreetDataset:
        dataset = AlexanderStreetDataset()
        dataset.volume_ctrn = Volume()
        dataset.volume_psyc = Volume()

        for k in kwargs.keys():
            if k == 'volume_ctrn':
                dataset.volume_ctrn = Volume.from_dict(kwargs=kwargs[k])
            elif k == 'volume_psyc':
                dataset.volume_psyc = Volume.from_dict(kwargs=kwargs[k])

        return dataset

    @staticmethod
    def load_dataset(json_file: str) -> AlexanderStreetDataset:
        dataset = AlexanderStreetDataset()
        dataset.volume_ctrn = Volume()
        dataset.volume_psyc = Volume()

        file_path = os.path.join(os.path.dirname(__file__), json_file)
        if not os.path.isfile(file_path):
            logger.info(f'File {file_path} not found. skipping loading dataset and initializing clean dataset.')
            return dataset

        with open(file_path, 'r') as handle:
            data: dict = json.load(handle)
            return AlexanderStreetDataset.from_dict(kwargs=data)

    def save_dataset(self, filename: str, overide: bool = False):
        if not filename.endswith('.json'):
            filename += '.json'

        file_path = os.path.join(os.path.dirname(__file__), filename)
        if os.path.exists(file_path) and not overide:
            logger.info(f'File {file_path} already exists.')
            return

        with open(file_path, 'w') as handle:
            json.dump(self.to_dict(), handle, indent=4)


def split_dataset(json_file: str,
                  first_partition: float = 0.8, second_partition: float = 0.2,
                  seed: int = 42) -> Tuple[AlexanderStreetDataset, AlexanderStreetDataset]:
    if first_partition + second_partition != 1.0:
        msg = (f'first_partition + second_partition must be equal to 1.0,'
               f' ({first_partition} + {second_partition} = {first_partition + second_partition})')
        logger.error(msg)
        raise ValueError(msg)

    random.seed(seed)

    as_dataset = AlexanderStreetDataset.load_dataset(json_file=json_file)
    as_dataset_partition_one = AlexanderStreetDataset.load_dataset(json_file='')
    as_dataset_partition_two = AlexanderStreetDataset.load_dataset(json_file='')

    # noinspection DuplicatedCode
    # splitting ctrn
    ctrn_count = len(as_dataset.volume_ctrn.conversations)
    indices = list(range(ctrn_count))
    random.shuffle(indices)

    first_partition_indices = indices[:int(ctrn_count * first_partition)]
    second_partition_indices = indices[int(ctrn_count * first_partition):]
    for i in first_partition_indices:
        as_dataset_partition_one.volume_ctrn.conversations.append(as_dataset.volume_ctrn.conversations[i])
    for i in second_partition_indices:
        as_dataset_partition_two.volume_ctrn.conversations.append(as_dataset.volume_ctrn.conversations[i])

    # noinspection DuplicatedCode
    # splitting psyc (same process)
    psyc_count = len(as_dataset.volume_psyc.conversations)
    indices = list(range(psyc_count))
    random.shuffle(indices)

    first_partition_indices = indices[:int(psyc_count * first_partition)]
    second_partition_indices = indices[int(psyc_count * first_partition):]
    for i in first_partition_indices:
        as_dataset_partition_one.volume_psyc.conversations.append(as_dataset.volume_psyc.conversations[i])
    for i in second_partition_indices:
        as_dataset_partition_two.volume_psyc.conversations.append(as_dataset.volume_psyc.conversations[i])

    return as_dataset_partition_one, as_dataset_partition_two
