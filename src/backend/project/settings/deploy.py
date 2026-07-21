"""HyperFileLens fixed tenant/operations deployment settings."""

from .env import env_bool, env_csv, env_int

HFL_EMAIL_SIGNUP_ENABLED = env_bool("HFL_EMAIL_SIGNUP_ENABLED", default=False)
HFL_PLATFORM_OPS_ENABLED = env_bool("HFL_PLATFORM_OPS_ENABLED", default=True)
HFL_SELF_SERVICE_PASSWORD_RESET = env_bool(
    "HFL_SELF_SERVICE_PASSWORD_RESET",
    default=True,
)
HFL_PLATFORM_OPS_ALLOWED_CIDRS = env_csv("HFL_PLATFORM_OPS_ALLOWED_CIDRS")
HFL_ADMIN_PORT = env_int("HFL_ADMIN_PORT", 11444)
