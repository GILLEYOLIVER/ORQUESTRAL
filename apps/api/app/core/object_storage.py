from __future__ import annotations

import hashlib
import hmac
from io import BytesIO
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from minio import Minio
from minio.sse import SseCustomerKey

from app.core.config import Settings


class ObjectStorageError(RuntimeError):
    """Erro seguro de armazenamento que não inclui endpoint nem credenciais."""


def _is_missing(error: Exception) -> bool:
    return getattr(error, "code", "") in {"NoSuchKey", "NoSuchObject", "NotFound"}


class S3ObjectStorage:
    """Fronteira S3 neutra com isolamento e verificação por tenant."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        endpoint = urlsplit(str(settings.storage_endpoint))
        self.client = client or Minio(
            endpoint.netloc,
            access_key=settings.storage_access_key,
            secret_key=settings.storage_secret_key,
            secure=endpoint.scheme == "https",
        )

    def _sse(self) -> SseCustomerKey | None:
        if not self.settings.object_storage_sse_enabled:
            return None
        key = hmac.new(
            self.settings.encryption_key.encode("utf-8"),
            b"orkestral-object-storage-sse-v1",
            hashlib.sha256,
        ).digest()
        return SseCustomerKey(key)

    @staticmethod
    def tenant_prefix(company_id: UUID) -> str:
        return f"knowledge/{company_id}/"

    def validate_tenant_key(self, company_id: UUID, key: str) -> None:
        if (
            not key.startswith(self.tenant_prefix(company_id))
            or ".." in key.split("/")
            or any(ord(character) < 32 for character in key)
        ):
            raise ObjectStorageError("Chave de objeto fora do escopo da empresa.")

    def ensure_bucket(self) -> None:
        try:
            if not self.client.bucket_exists(self.settings.storage_bucket):
                self.client.make_bucket(self.settings.storage_bucket)
        except Exception as exc:
            raise ObjectStorageError("Armazenamento de objetos indisponível.") from exc

    def put_tenant_object(
        self,
        *,
        company_id: UUID,
        key: str,
        data: bytes,
        content_type: str,
    ) -> str:
        self.validate_tenant_key(company_id, key)
        checksum = hashlib.sha256(data).hexdigest()
        self.ensure_bucket()
        try:
            self.client.put_object(
                self.settings.storage_bucket,
                key,
                BytesIO(data),
                len(data),
                content_type=content_type,
                metadata={"X-Amz-Meta-Sha256": checksum},
                sse=self._sse(),
            )
            stored = self.client.stat_object(
                self.settings.storage_bucket,
                key,
                ssec=self._sse(),
            )
        except Exception as exc:
            raise ObjectStorageError("Não foi possível armazenar o objeto.") from exc
        if stored.size is None or int(stored.size) != len(data):
            raise ObjectStorageError("O tamanho persistido não corresponde ao objeto enviado.")
        return checksum

    def read_tenant_object(
        self,
        *,
        company_id: UUID,
        key: str,
        expected_sha256: str | None = None,
    ) -> bytes:
        self.validate_tenant_key(company_id, key)
        try:
            response = self.client.get_object(
                self.settings.storage_bucket,
                key,
                ssec=self._sse(),
            )
            try:
                data = response.read()
            finally:
                response.close()
                response.release_conn()
        except Exception as exc:
            raise ObjectStorageError("Não foi possível ler o objeto.") from exc
        if expected_sha256 and not hmac.compare_digest(
            hashlib.sha256(data).hexdigest(), expected_sha256
        ):
            raise ObjectStorageError("A verificação de integridade do objeto falhou.")
        return data

    def delete_tenant_object(self, *, company_id: UUID, key: str) -> None:
        self.validate_tenant_key(company_id, key)
        try:
            self.client.remove_object(self.settings.storage_bucket, key)
            self.client.stat_object(
                self.settings.storage_bucket,
                key,
                ssec=self._sse(),
            )
        except Exception as exc:
            if _is_missing(exc):
                return
            raise ObjectStorageError("Não foi possível confirmar a exclusão do objeto.") from exc
        raise ObjectStorageError("O objeto permaneceu disponível após a exclusão.")

    def purge_tenant(self, company_id: UUID) -> int:
        """Elimina e confirma objetos da empresa sem tocar em outro tenant."""
        prefix = self.tenant_prefix(company_id)
        try:
            keys = [
                item.object_name
                for item in self.client.list_objects(
                    self.settings.storage_bucket,
                    prefix=prefix,
                    recursive=True,
                )
            ]
            for key in keys:
                self.delete_tenant_object(company_id=company_id, key=key)
            remaining = list(
                self.client.list_objects(
                    self.settings.storage_bucket,
                    prefix=prefix,
                    recursive=True,
                )
            )
        except ObjectStorageError:
            raise
        except Exception as exc:
            raise ObjectStorageError("Não foi possível eliminar os objetos da empresa.") from exc
        if remaining:
            raise ObjectStorageError("A eliminação dos objetos da empresa não foi concluída.")
        return len(keys)


def object_storage(settings: Settings, client: Any | None = None) -> S3ObjectStorage:
    return S3ObjectStorage(settings, client)
