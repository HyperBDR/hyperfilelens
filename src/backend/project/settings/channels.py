"""
Django Channels (WebSocket) settings (deployment).
"""

from .env import env_str

REDIS_URL = env_str("REDIS_URL", "redis://localhost:6379/0")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                {
                    "address": REDIS_URL,
                    "socket_connect_timeout": 5,
                    "socket_timeout": None,
                }
            ]
        },
    },
}
