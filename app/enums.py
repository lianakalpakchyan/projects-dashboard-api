from enum import StrEnum


class DatabaseMode(StrEnum):
    RAW = "RAW"
    ORM = "ORM"


class Role(StrEnum):
    OWNER = "OWNER"
    PARTICIPANT = "PARTICIPANT"
