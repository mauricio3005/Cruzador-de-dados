"""Testes para o endpoint de fechamento de folha de pagamento."""
import pytest
from unittest.mock import MagicMock, patch


def _make_funcionario(etapa="Estrutura", valor=1000.0):
    return {"etapa": etapa, "valor": str(valor), "nome": "João"}


def test_fechar_folha_sem_auth_retorna_401(client):
    """Endpoint deve rejeitar chamadas sem Authorization header."""
    resp = client.post("/api/folha/fechar", json={
        "folha_id": 1, "obra": "Obra A", "quinzena": "2024-01-01"
    })
    assert resp.status_code == 401


def test_fechar_folha_sem_funcionarios_retorna_400(client, auth_headers, mock_supabase):
    """Deve retornar 400 se a folha não tiver funcionários."""
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    resp = client.post("/api/folha/fechar", json={
        "folha_id": 1, "obra": "Obra A", "quinzena": "2024-01-01"
    }, headers=auth_headers)
    assert resp.status_code == 400
    assert "funcionários" in resp.json()["detail"].lower()


def test_fechar_folha_comprovante_muito_grande_retorna_413(client, auth_headers):
    """Deve rejeitar comprovantes maiores que 10 MB."""
    # ~11 MB em base64 (~14.5 MB de string)
    big_b64 = "A" * (15 * 1024 * 1024)
    resp = client.post("/api/folha/fechar", json={
        "folha_id": 1, "obra": "Obra A", "quinzena": "2024-01-01",
        "comprovantes": [big_b64]
    }, headers=auth_headers)
    assert resp.status_code == 413


def test_fechar_folha_rollback_em_falha_de_upload(client, auth_headers, mock_supabase):
    """Se upload falhar, despesas inseridas devem ser deletadas."""
    funcionarios = [_make_funcionario()]
    # Select retorna funcionários
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = funcionarios
    # Insert retorna id
    mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [{"id": "uuid-1"}]
    # Upload falha
    mock_supabase.storage.from_.return_value.upload.side_effect = Exception("Storage indisponível")

    resp = client.post("/api/folha/fechar", json={
        "folha_id": 1, "obra": "Obra A", "quinzena": "2024-01-01",
        "comprovantes": ["dGVzdA=="],  # "test" em base64
        "comprovantes_tipos": ["image/jpeg"]
    }, headers=auth_headers)

    assert resp.status_code == 500
    assert "revertida" in resp.json()["detail"].lower()
