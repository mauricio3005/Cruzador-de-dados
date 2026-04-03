import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch


@pytest.fixture
def client():
    from api.main import app
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token-valido"}


@pytest.fixture(autouse=True)
def mock_supabase():
    mock = MagicMock()
    # Configurar comportamentos padrão do mock
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    mock.table.return_value.insert.return_value.execute.return_value.data = []
    mock.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    mock.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = []
    with patch("api.supabase_client.get_supabase", return_value=mock):
        yield mock


@pytest.fixture(autouse=True)
def mock_auth():
    fake_user = MagicMock()
    fake_user.id = "user-123"
    fake_user.email = "test@test.com"
    with patch("api.dependencies.get_current_user", return_value=fake_user):
        yield fake_user
