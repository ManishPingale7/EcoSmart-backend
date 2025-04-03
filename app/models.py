from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class AuthorityBase(BaseModel):
    username: str
    email: EmailStr
    role: str = "authority"

class AuthorityCreate(AuthorityBase):
    password: str

class Authority(AuthorityBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AuthorityLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class GoogleUser(BaseModel):
    email: EmailStr
    name: str
    picture: Optional[str] = None
    google_id: str 