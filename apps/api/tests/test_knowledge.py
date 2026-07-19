import pytest

from app.modules.knowledge.processing import chunks, embed, extract
from app.modules.knowledge.security import KnowledgeSecurityError, validate_file


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
