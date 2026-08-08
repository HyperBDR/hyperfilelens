"""Subscription domain (OSS shell: models/migrations/license).

Uses ``extend_path`` so EE can contribute governance APIs (plans/quotas/…)
while this tree keeps models and license endpoints.
"""

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
