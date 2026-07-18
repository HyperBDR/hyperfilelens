"""Register project models with Django Admin when not already registered.

Custom ``ModelAdmin`` classes in per-app ``admin.py`` take precedence; this
fills in CRUD for any remaining ``apps.*`` models with default admin UI.
"""

from __future__ import annotations

from django.contrib import admin
from django.apps import apps
from django.db.models import Model


def _is_project_model(model: type[Model]) -> bool:
    try:
        app_config = apps.get_app_config(model._meta.app_label)
    except LookupError:
        return False
    return app_config.name.startswith("apps.")


def autoregister_project_models(*, site: admin.AdminSite | None = None) -> int:
    """
    Register unregistered concrete project models on *site* (default site).

    Returns the number of models newly registered.
    """
    admin_site = site or admin.site
    registered = 0

    for model in apps.get_models():
        if not _is_project_model(model):
            continue
        if model._meta.abstract or not model._meta.managed:
            continue
        if admin_site.is_registered(model):
            continue
        admin_site.register(model)
        registered += 1

    return registered
