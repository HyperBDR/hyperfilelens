from unittest import TestCase, mock

from apps.storage.services.internal.s3_client import (
    check_s3_bucket_readable,
    ensure_s3_bucket,
    list_s3_buckets,
)
from botocore.exceptions import ClientError


class S3ClientUrlStyleTests(TestCase):
    @mock.patch("apps.storage.services.internal.s3_client.boto3.client")
    def test_list_s3_buckets_uses_auto_style_by_default(self, boto_client):
        client = mock.Mock()
        client.list_buckets.return_value = {"Buckets": [{"Name": "bucket-a"}]}
        boto_client.return_value = client

        buckets = list_s3_buckets(
            endpoint="https://obs.cn-north-5.myhuaweicloud.com",
            region="cn-north-5",
            access_key_id="AK",
            secret_access_key="SK",
        )

        self.assertEqual(buckets, ["bucket-a"])
        config = boto_client.call_args.kwargs["config"]
        self.assertEqual(config.s3["addressing_style"], "auto")
        self.assertEqual(config.request_checksum_calculation, "when_required")
        self.assertEqual(config.response_checksum_validation, "when_required")

    @mock.patch("apps.storage.services.internal.s3_client.boto3.client")
    def test_list_s3_buckets_honors_path_style(self, boto_client):
        client = mock.Mock()
        client.list_buckets.return_value = {"Buckets": []}
        boto_client.return_value = client

        list_s3_buckets(
            endpoint="https://s3.example.com",
            region="us-east-1",
            access_key_id="AK",
            secret_access_key="SK",
            s3_url_style="path",
        )

        config = boto_client.call_args.kwargs["config"]
        self.assertEqual(config.s3["addressing_style"], "path")

    @mock.patch("apps.storage.services.internal.s3_client.boto3.client")
    def test_list_s3_buckets_honors_virtual_hosted_style(self, boto_client):
        client = mock.Mock()
        client.list_buckets.return_value = {"Buckets": []}
        boto_client.return_value = client

        list_s3_buckets(
            endpoint="https://obs.cn-north-5.myhuaweicloud.com",
            region="cn-north-5",
            access_key_id="AK",
            secret_access_key="SK",
            s3_url_style="virtual_hosted",
        )

        config = boto_client.call_args.kwargs["config"]
        self.assertEqual(config.s3["addressing_style"], "virtual")


class EnsureS3BucketTests(TestCase):
    @mock.patch("apps.storage.services.internal.s3_client._client")
    def test_skips_create_when_bucket_already_listed(self, client_factory):
        client = mock.Mock()
        client.list_buckets.return_value = {"Buckets": [{"Name": "bucket-a"}]}
        client_factory.return_value = client

        ensure_s3_bucket(
            endpoint="https://obs.cn-north-9.myhuaweicloud.com",
            region="cn-north-9",
            bucket="bucket-a",
            access_key_id="AK",
            secret_access_key="SK",
        )

        client.create_bucket.assert_not_called()
        client.head_bucket.assert_not_called()

    @mock.patch("apps.storage.services.internal.s3_client._client")
    def test_creates_bucket_when_missing_from_list(self, client_factory):
        client = mock.Mock()
        client.list_buckets.return_value = {"Buckets": []}
        client_factory.return_value = client

        ensure_s3_bucket(
            endpoint="https://obs.cn-north-9.myhuaweicloud.com",
            region="cn-north-9",
            bucket="new-bucket",
            access_key_id="AK",
            secret_access_key="SK",
            s3_url_style="virtual_hosted",
        )

        client.create_bucket.assert_called_once_with(
            Bucket="new-bucket",
            CreateBucketConfiguration={"LocationConstraint": "cn-north-9"},
        )
        client.head_bucket.assert_not_called()

    @mock.patch("apps.storage.services.internal.s3_client._client")
    def test_treats_bucket_already_owned_as_success(self, client_factory):
        client = mock.Mock()
        client.list_buckets.return_value = {"Buckets": []}
        client.create_bucket.side_effect = ClientError(
            {
                "Error": {"Code": "BucketAlreadyOwnedByYou", "Message": "owned"},
                "ResponseMetadata": {"HTTPStatusCode": 409},
            },
            "CreateBucket",
        )
        client_factory.return_value = client

        ensure_s3_bucket(
            endpoint="https://obs.cn-north-9.myhuaweicloud.com",
            region="cn-north-9",
            bucket="new-bucket",
            access_key_id="AK",
            secret_access_key="SK",
        )


class CheckS3BucketReadableTests(TestCase):
    @mock.patch("apps.storage.services.internal.s3_client._client")
    def test_uses_head_bucket_without_mutating_storage(self, client_factory):
        client = mock.Mock()
        client_factory.return_value = client

        check_s3_bucket_readable(
            endpoint="https://s3.example.com",
            region="us-east-1",
            bucket="backup-bucket",
            access_key_id="AK",
            secret_access_key="SK",
        )

        client.head_bucket.assert_called_once_with(Bucket="backup-bucket")
        client.list_buckets.assert_not_called()
        client.create_bucket.assert_not_called()
        client.put_object.assert_not_called()
        client.delete_object.assert_not_called()
