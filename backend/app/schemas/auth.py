from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str
    captcha_token: Optional[str] = None
    captcha_code: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    display_name: Optional[str] = None
    role: str


class CaptchaResponse(BaseModel):
    captcha_token: str
    image_data_url: str
    expires_in_seconds: int
