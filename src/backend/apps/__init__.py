"""HyperFileLens application package (OSS).

Uses ``extend_path`` so Enterprise Edition can contribute additional
``apps.*`` modules (e.g. ``apps.ee``) from a second ``src/backend`` on
``sys.path`` without colliding as a nested regular package.
"""

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
