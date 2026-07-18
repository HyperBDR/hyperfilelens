from django.test import SimpleTestCase

from apps.source.constants import ResourceType
from apps.source.services.internal.nas_display import connection_summary_for_resource


class NasDisplayTests(SimpleTestCase):
    def test_smb_mount_source_uri(self):
        summary = connection_summary_for_resource(
            resource_type=ResourceType.NAS,
            config={
                "protocol": "smb",
                "server": "192.168.14.23",
                "share": "backup",
            },
        )
        self.assertEqual(summary, "//192.168.14.23/backup")

    def test_nfs_mount_source_uri(self):
        summary = connection_summary_for_resource(
            resource_type=ResourceType.NAS,
            config={
                "protocol": "nfs",
                "server": "192.168.14.23",
                "export_path": "/srv/nfs/backup",
                "path": "/mnt/nfs-backup",
            },
        )
        self.assertEqual(summary, "192.168.14.23:/srv/nfs/backup")

    def test_cifs_resource_type(self):
        summary = connection_summary_for_resource(
            resource_type=ResourceType.CIFS,
            config={"server": "192.168.1.100", "share": "media"},
        )
        self.assertEqual(summary, "//192.168.1.100/media")
