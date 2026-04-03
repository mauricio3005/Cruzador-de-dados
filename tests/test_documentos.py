"""Testes para o endpoint de documentos."""
import pytest


def test_remover_nf_sem_auth_retorna_401(client):
    """DELETE /api/documentos/nf/{id} deve exigir auth."""
    resp = client.delete("/api/documentos/nf/1")
    assert resp.status_code == 401


def test_remover_nf_nao_encontrada_retorna_404(client, auth_headers, mock_supabase):
    """Deve retornar 404 se NF não existir."""
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    resp = client.delete("/api/documentos/nf/999", headers=auth_headers)
    assert resp.status_code == 404
