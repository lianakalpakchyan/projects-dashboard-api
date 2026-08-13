import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator


class UserCreate(BaseModel):
    login: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    repeat_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "UserCreate":
        if self.password != self.repeat_password:
            raise ValueError("password and repeat_password do not match")
        return self


class UserLogin(BaseModel):
    login: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    login: str
