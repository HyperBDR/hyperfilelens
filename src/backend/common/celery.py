"""Celery application for asynchronous and periodic backend tasks."""

import os

from celery import Celery

_SETTINGS_MODULE = "project.settings"

os.environ.setdefault("DJANGO_SETTINGS_MODULE", _SETTINGS_MODULE)

app = Celery("common")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
