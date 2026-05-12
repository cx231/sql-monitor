from __future__ import annotations

import base64
import hashlib
import html
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt import InvalidTokenError

from app.config import get_settings
from app.security import ALGORITHM

CAPTCHA_EXPIRE_SECONDS = 300
CAPTCHA_TYPE = "captcha"


@dataclass(frozen=True)
class CaptchaChallenge:
    captcha_token: str
    image_data_url: str
    expires_in_seconds: int = CAPTCHA_EXPIRE_SECONDS


def generate_captcha_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _captcha_hash(code: str, nonce: str, secret_key: str) -> str:
    payload = f"{code}:{nonce}:{secret_key}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _render_svg_data_url(code: str) -> str:
    escaped_code = html.escape(code)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="132" height="44" viewBox="0 0 132 44">
  <rect width="132" height="44" rx="6" fill="#F8FAFC"/>
  <path d="M8 12 C24 4, 38 20, 54 12 S88 4, 124 14" fill="none" stroke="#CBD5E1" stroke-width="2"/>
  <path d="M10 34 C30 24, 42 40, 62 30 S94 22, 122 34" fill="none" stroke="#E2E8F0" stroke-width="2"/>
  <text x="66" y="29" text-anchor="middle" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="24" font-weight="700" letter-spacing="4" fill="#1E293B">{escaped_code}</text>
</svg>"""
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def create_captcha_challenge(code: str | None = None) -> CaptchaChallenge:
    settings = get_settings()
    captcha_code = code or generate_captcha_code()
    nonce = secrets.token_hex(16)
    expire_at = datetime.now(timezone.utc) + timedelta(seconds=CAPTCHA_EXPIRE_SECONDS)
    token_payload: dict[str, Any] = {
        "type": CAPTCHA_TYPE,
        "captcha_hash": _captcha_hash(captcha_code, nonce, settings.secret_key),
        "nonce": nonce,
        "exp": expire_at,
    }
    token = jwt.encode(token_payload, settings.secret_key, algorithm=ALGORITHM)
    return CaptchaChallenge(
        captcha_token=token,
        image_data_url=_render_svg_data_url(captcha_code),
    )


def verify_captcha(captcha_token: str, captcha_code: str) -> bool:
    if len(captcha_code) != 6 or not captcha_code.isdigit():
        return False

    settings = get_settings()
    try:
        payload = jwt.decode(
            captcha_token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "type", "captcha_hash", "nonce"]},
        )
    except InvalidTokenError:
        return False

    if payload.get("type") != CAPTCHA_TYPE:
        return False

    expected_hash = payload.get("captcha_hash")
    nonce = payload.get("nonce")
    if not isinstance(expected_hash, str) or not isinstance(nonce, str):
        return False

    actual_hash = _captcha_hash(captcha_code, nonce, settings.secret_key)
    return secrets.compare_digest(actual_hash, expected_hash)
