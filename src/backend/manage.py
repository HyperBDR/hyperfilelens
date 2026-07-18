#!/usr/bin/env python
"""Django management CLI for the HyperFileLens backend.

Sets ``src/backend`` as the working directory and prepends it to ``sys.path``
so ``project.settings`` and application modules resolve regardless of the
shell's current directory.

Typical usage:
  cd src/backend && python manage.py migrate
  python manage.py runserver 0.0.0.0:8000
"""

import os
import sys
from pathlib import Path


def _bootstrap_backend_root() -> Path:
    """Set backend root as cwd and ensure it is on ``sys.path``.

    Returns:
        Resolved path to ``src/backend``.
    """
    backend_root = Path(__file__).resolve().parent
    os.chdir(backend_root)
    backend_root_str = str(backend_root)
    if backend_root_str not in sys.path:
        sys.path.insert(0, backend_root_str)
    return backend_root


def main() -> None:
    _bootstrap_backend_root()

    from project import configure_django

    configure_django()

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
