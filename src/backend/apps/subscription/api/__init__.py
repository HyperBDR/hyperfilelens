"""Subscription API package (OSS + EE via extend_path)."""

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
