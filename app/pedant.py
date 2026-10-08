from pydantic import BaseModel, Field
from datetime import time

class User(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=7)