"""Testes para os endpoints de IA."""
import io
import pytest


def test_extrair_sem_auth_retorna_401(client):
    """Endpoint /extrair deve rejeitar sem auth."""
    resp = client.post("/api/ai/extrair", files={"file": ("test.jpg", b"fake", "image/jpeg")})
    assert resp.status_code == 401


def test_extrair_arquivo_muito_grande_retorna_413(client, auth_headers):
    """Arquivo maior que 20 MB deve ser rejeitado."""
    # 21 MB de dados falsos
    big_file = b"x" * (21 * 1024 * 1024)
    resp = client.post(
        "/api/ai/extrair",
        files={"file": ("big.jpg", big_file, "image/jpeg")},
        headers=auth_headers,
    )
    assert resp.status_code == 413


def test_extrair_tipo_nao_permitido_retorna_415(client, auth_headers):
    """Tipo de arquivo não permitido deve retornar 415."""
    resp = client.post(
        "/api/ai/extrair",
        files={"file": ("script.exe", b"MZ\x90\x00", "application/octet-stream")},
        headers=auth_headers,
    )
    assert resp.status_code == 415


def test_referencias_sem_auth_retorna_401(client):
    """GET /api/ai/referencias deve exigir auth."""
    resp = client.get("/api/ai/referencias")
    assert resp.status_code == 401


def test_chat_sem_auth_retorna_401(client):
    """POST /api/ai/chat deve exigir auth."""
    resp = client.post("/api/ai/chat", json={"mensagem": "olá"})
    assert resp.status_code == 401
