from ninja import Schema
from typing import List

class TaskSchema(Schema):
    date: str
    successful: bool
    taskName: str
    errorMessage: str

class ResponseSchema(Schema):
    successRatio: float
    tasks: List[TaskSchema]