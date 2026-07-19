from __future__ import annotations

import ipaddress
import socket
from io import BytesIO
from urllib.parse import urlsplit
from zipfile import BadZipFile, ZipFile

SUPPORTED = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "text/csv": "csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/html": "html",
}


class KnowledgeSecurityError(ValueError):
    pass


def validate_file(data: bytes, mime: str, max_bytes: int) -> None:
    if not data or len(data) > max_bytes:
        raise KnowledgeSecurityError("Arquivo vazio ou acima do limite permitido.")
    if mime not in SUPPORTED:
        raise KnowledgeSecurityError("Tipo de documento não suportado.")
    if mime == "application/pdf" and not data.startswith(b"%PDF"):
        raise KnowledgeSecurityError("Assinatura PDF inválida.")
    if mime.startswith("text/") and b"\x00" in data:
        raise KnowledgeSecurityError("Conteúdo textual inválido.")
    if SUPPORTED[mime] in {"docx", "xlsx"}:
        try:
            with ZipFile(BytesIO(data)) as archive:
                names = archive.namelist()
                if any(".." in name or name.startswith("/") for name in names):
                    raise KnowledgeSecurityError("Pacote contém caminho inseguro.")
                if any(name.lower().endswith(("vbaproject.bin", ".exe", ".js")) for name in names):
                    raise KnowledgeSecurityError("Documento contém conteúdo executável.")
                if sum(info.file_size for info in archive.infolist()) > max_bytes * 10:
                    raise KnowledgeSecurityError("Documento compactado excede o limite seguro.")
        except BadZipFile as exc:
            raise KnowledgeSecurityError("Pacote de documento inválido.") from exc


def validate_web_url(url: str, allowed_domains: list[str]) -> str:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        raise KnowledgeSecurityError("Somente páginas HTTPS são aceitas.")
    if not allowed_domains or not any(
        host == d.lower() or host.endswith("." + d.lower()) for d in allowed_domains
    ):
        raise KnowledgeSecurityError("Domínio não autorizado pela administração.")
    for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
        ip = ipaddress.ip_address(item[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise KnowledgeSecurityError("Destino de rede não permitido.")
    return url
