"""S3 storage backend exercised against moto's in-process S3 emulator (no network, no real bucket)."""

import boto3
import pytest
from moto import mock_aws

from app.config import get_settings
from app.services import media
from app.storage import S3Storage, get_storage
from tests.conftest import png_bytes


@pytest.fixture
def s3(monkeypatch):
    for k, v in {
        "MEDIA_STORAGE": "s3", "S3_BUCKET": "baysahne-test", "S3_REGION": "eu-central-1",
        "S3_ACCESS_KEY_ID": "test", "S3_SECRET_ACCESS_KEY": "test",
        "S3_PUBLIC_BASE_URL": "https://cdn.example.com", "S3_ENDPOINT_URL": "",
    }.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    get_storage.cache_clear()
    with mock_aws():
        client = boto3.client("s3", region_name="eu-central-1")
        client.create_bucket(Bucket="baysahne-test", CreateBucketConfiguration={"LocationConstraint": "eu-central-1"})
        yield client
    get_settings.cache_clear()
    get_storage.cache_clear()


def test_store_and_delete_image_in_s3(s3, db):
    assert isinstance(get_storage(), S3Storage)
    asset, created = media.store_image(db, png_bytes(1600, 900), original_filename="afis.png")
    db.commit()
    assert created
    keys = {o["Key"] for o in s3.list_objects_v2(Bucket="baysahne-test")["Contents"]}
    assert keys == {asset.storage_key, asset.variants["sm"]["key"], asset.variants["lg"]["key"]}
    head = s3.head_object(Bucket="baysahne-test", Key=asset.variants["lg"]["key"])
    assert head["ContentType"] == "image/webp" and "immutable" in head["CacheControl"]
    out = media.image_dict(asset)
    assert out["url"] == f"https://cdn.example.com/{asset.storage_key}"  # URL derived from config, not stored

    media.delete_asset(db, asset)
    db.commit()
    assert s3.list_objects_v2(Bucket="baysahne-test").get("KeyCount") == 0
