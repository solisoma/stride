from typing import Literal
from pydantic import BaseModel, Field, field_validator
import re
import uuid


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator('email')
    @classmethod
    def email_format(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Enter a valid email address')
        return value


class Registration(Credentials):
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=15, max_length=128)


class ClaimInput(BaseModel):
    journey_id: int
    access_token: str = Field(min_length=1, max_length=100)


class JourneyInput(BaseModel):
    goal: Literal['exam', 'technical_interview', 'new_field']
    subject: str = Field(min_length=1, max_length=200)


class PracticeInput(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    format: Literal['multiple_choice', 'typed'] = 'typed'


class AnswerInput(BaseModel):
    answer: str = Field(min_length=1, max_length=20000)
    submission_id: str = Field(default_factory=lambda: str(uuid.uuid4()), min_length=1, max_length=100)


class MessageInput(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    activity_id: int | None = Field(default=None, gt=0)


class ReviewDecision(BaseModel):
    decision: Literal['use_source', 'use_alternative', 'exclude', 'pending']
    note: str = Field(default='', max_length=3000)

