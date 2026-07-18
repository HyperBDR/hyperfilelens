"""
Captcha generation and validation service.
"""

import random
import string
import uuid

from django.core.cache import cache

CAPTCHA_LENGTH = 4
CAPTCHA_EXPIRE_SECONDS = 60  # 60 seconds


def generate_captcha_id() -> str:
    return f"captcha_{uuid.uuid4().hex[:16]}"


def generate_captcha_text(length: int = CAPTCHA_LENGTH) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def get_captcha_cache_key(captcha_id: str) -> str:
    return f"captcha:{captcha_id}"


def save_captcha(captcha_id: str, text: str) -> None:
    key = get_captcha_cache_key(captcha_id)
    cache.set(key, text.lower(), timeout=CAPTCHA_EXPIRE_SECONDS)


def get_captcha_text(captcha_id: str) -> str | None:
    key = get_captcha_cache_key(captcha_id)
    return cache.get(key)


def validate_captcha(captcha_id: str, user_input: str) -> bool:
    stored = get_captcha_text(captcha_id)
    if not stored:
        return False
    return stored == user_input.lower().strip()


def generate_svg_captcha(text: str) -> str:
    """
    Generate an SVG captcha image as base64 string.
    Returns a data URI: data:image/svg+xml;base64,...
    """
    svg = _make_captcha_svg(text)
    import base64

    encoded = base64.b64encode(svg.encode()).decode()
    return f"data:image/svg+xml;base64,{encoded}"


def _make_captcha_svg(text: str) -> str:
    """
    Create a simple SVG captcha image.
    """
    width, height = 120, 40
    chars = list(text)
    char_width = width // (len(chars) + 1)

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#f9f9f9"/>',
    ]

    # Draw wavy lines for noise
    noise_color = "#cccccc"
    for i in range(3):
        y_offset = 8 + i * 12
        svg_parts.append(
            f'<path d="M0,{y_offset} Q30,{y_offset - 5} 60,{y_offset} Q90,{y_offset + 5} {width},{y_offset}" '
            f'stroke="{noise_color}" stroke-width="1" fill="none"/>'
        )

    # Draw characters with slight rotation
    for i, char in enumerate(chars):
        x = char_width * (i + 0.5) + random.uniform(-3, 3)
        y = height // 2 + random.uniform(-5, 5)
        rotation = random.uniform(-15, 15)
        color = "#2d5a8a"
        svg_parts.append(
            f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" '
            f'font-size="24" font-weight="bold" fill="{color}" '
            f'text-anchor="middle" dominant-baseline="middle" '
            f'transform="rotate({rotation},{x},{y})">{char}</text>'
        )

    svg_parts.append("</svg>")
    return "".join(svg_parts)
