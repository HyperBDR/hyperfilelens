from django.test import SimpleTestCase

from apps.source.constants import ResourceType
from apps.source.services.internal.nas_path_normalize import (
    normalize_nfs_export_path,
    normalize_nas_config,
    normalize_resource_config,
    normalize_smb_share,
)


class NasPathNormalizeTests(SimpleTestCase):
    def test_normalize_smb_share_strips_leading_slashes(self):
        self.assertEqual(normalize_smb_share("data"), "data")
        self.assertEqual(normalize_smb_share("/data"), "data")
        self.assertEqual(normalize_smb_share("//data"), "data")
        self.assertEqual(normalize_smb_share("\\data"), "data")
        self.assertEqual(normalize_smb_share("share/subdir"), "share/subdir")
        self.assertEqual(normalize_smb_share("/share/subdir/"), "share/subdir")

    def test_normalize_nfs_export_path_adds_leading_slash(self):
        self.assertEqual(normalize_nfs_export_path("data"), "/data")
        self.assertEqual(normalize_nfs_export_path("/data"), "/data")
        self.assertEqual(normalize_nfs_export_path("//data"), "/data")
        self.assertEqual(normalize_nfs_export_path("/export/backup/"), "/export/backup")
        self.assertEqual(normalize_nfs_export_path("export/backup"), "/export/backup")

    def test_normalize_nas_config_smb(self):
        cfg = normalize_nas_config(
            {
                "protocol": "smb",
                "server": "192.168.1.10",
                "share": "/media",
            }
        )
        self.assertEqual(cfg["share"], "media")

    def test_normalize_nas_config_nfs(self):
        cfg = normalize_nas_config(
            {
                "protocol": "nfs",
                "server": "192.168.1.10",
                "export_path": "data",
            }
        )
        self.assertEqual(cfg["export_path"], "/data")

    def test_normalize_resource_config_for_legacy_types(self):
        cifs = normalize_resource_config(
            ResourceType.CIFS,
            {"server": "10.0.0.1", "share": "/backup"},
        )
        self.assertEqual(cifs["share"], "backup")

        nfs = normalize_resource_config(
            ResourceType.NFS,
            {"server": "10.0.0.1", "export_path": "export"},
        )
        self.assertEqual(nfs["export_path"], "/export")
