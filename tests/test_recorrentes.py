"""Testes para o módulo de despesas recorrentes."""
import pytest


def test_listar_sem_auth_retorna_401(client):
    resp = client.get("/api/recorrentes")
    assert resp.status_code == 401


def test_criar_sem_auth_retorna_401(client):
    resp = client.post("/api/recorrentes", json={})
    assert resp.status_code == 401


def test_processar_sem_auth_retorna_401(client):
    resp = client.post("/api/recorrentes/processar")
    assert resp.status_code == 401


def test_listar_retorna_lista(client, auth_headers, mock_supabase):
    """GET /api/recorrentes deve retornar lista."""
    mock_supabase.table.return_value.select.return_value.order.return_value.execute.return_value.data = [
        {"id": 1, "obra": "Obra A", "valor": 500.0, "frequencia": "mensal"}
    ]
    resp = client.get("/api/recorrentes", headers=auth_headers)
    assert resp.status_code == 200
