from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.object_storage import ObjectStorageError, object_storage
from app.modules.knowledge.processing import chunks, embed, extract
from app.modules.knowledge.security import KnowledgeSecurityError, validate_file


class MissingObject(Exception):
    code = "NoSuchKey"


@dataclass
class StoredObject:
    size: int


class Response(BytesIO):
    def release_conn(self) -> None:
        return


class FakeS3:
    def __init__(self) -> None:
        self.bucket = False
        self.objects: dict[str, bytes] = {}

    def bucket_exists(self, _bucket: str) -> bool:
        return self.bucket

    def make_bucket(self, _bucket: str) -> None:
        self.bucket = True

    def put_object(
        self,
        _bucket: str,
        key: str,
        stream: BytesIO,
        length: int,
        **_kwargs: object,
    ) -> None:
        self.objects[key] = stream.read(length)

    def stat_object(self, _bucket: str, key: str, **_kwargs: object) -> StoredObject:
        if key not in self.objects:
            raise MissingObject
        return StoredObject(size=len(self.objects[key]))

    def get_object(self, _bucket: str, key: str, **_kwargs: object) -> Response:
        if key not in self.objects:
            raise MissingObject
        return Response(self.objects[key])

    def remove_object(self, _bucket: str, key: str) -> None:
        self.objects.pop(key, None)

    def list_objects(
        self, _bucket: str, *, prefix: str, recursive: bool
    ) -> list[object]:
        del recursive
        return [
            type("Item", (), {"object_name": key})()
            for key in self.objects
            if key.startswith(prefix)
        ]


def test_chunks_and_embeddings_are_deterministic() -> None:
    parts = chunks("Orkestral conhecimento " * 200)
    assert len(parts) > 1
    assert embed(parts[0]) == embed(parts[0])
    assert len(embed(parts[0])) == 384


def test_text_extraction() -> None:
    assert extract(b"conteudo autorizado", "text/plain") == "conteudo autorizado"


def test_rejects_executable_content() -> None:
    with pytest.raises(KnowledgeSecurityError):
        validate_file(b"MZ\x00payload", "text/plain", 1024)


def test_object_storage_enforces_tenant_integrity_and_verified_delete() -> None:
    company_id = uuid4()
    foreign_company_id = uuid4()
    key = f"knowledge/{company_id}/base/document/file.txt"
    fake = FakeS3()
    store = object_storage(Settings(), fake)

    checksum = store.put_tenant_object(
        company_id=company_id,
        key=key,
        data=b"conteudo isolado",
        content_type="text/plain",
    )
    assert store.read_tenant_object(
        company_id=company_id,
        key=key,
        expected_sha256=checksum,
    ) == b"conteudo isolado"
    with pytest.raises(ObjectStorageError, match="escopo"):
        store.read_tenant_object(company_id=foreign_company_id, key=key)

    store.delete_tenant_object(company_id=company_id, key=key)
    assert fake.objects == {}


def test_object_storage_purges_only_the_requested_tenant() -> None:
    company_id = uuid4()
    other_company_id = uuid4()
    fake = FakeS3()
    store = object_storage(Settings(), fake)
    own_key = f"knowledge/{company_id}/base/a.txt"
    other_key = f"knowledge/{other_company_id}/base/b.txt"
    for tenant, key in ((company_id, own_key), (other_company_id, other_key)):
        store.put_tenant_object(
            company_id=tenant,
            key=key,
            data=b"dado",
            content_type="text/plain",
        )

    assert store.purge_tenant(company_id) == 1
    assert own_key not in fake.objects
    assert other_key in fake.objects
