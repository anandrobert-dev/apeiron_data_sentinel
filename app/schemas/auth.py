"""Authentication schemas."""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: str | None = None
    role: str = "ValidatorUser"
    client_ids: list[str] | None = None
