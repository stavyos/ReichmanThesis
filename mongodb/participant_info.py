from dataclasses import dataclass
from enum import Enum


class Gender(Enum):
    Female = 0
    Male = 1
    Other = 2

    @staticmethod
    def from_str(string: str):
        if 'male'.__eq__(string.lower()):
            return Gender.Male
        elif 'female'.__eq__(string.lower()):
            return Gender.Female
        else:
            raise NotImplementedError


@dataclass
class ParticipantInfo:
    email: str
    gender: Gender
    age: int
    years_of_education: str
    is_native_en: bool
    is_cs_expert: bool
    is_psyc_expert: bool
    curr_in_therapy: bool
    been_in_therapy: bool
