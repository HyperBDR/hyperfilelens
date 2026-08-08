"""Platform Ops (OSS shell: models/migrations).

Uses ``extend_path`` so EE can contribute ``api`` / ``services`` / ``selectors``
from a second ``src/backend`` on ``sys.path`` while this tree keeps models.
"""

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
