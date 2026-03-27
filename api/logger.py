"""
Configuração centralizada de logging para a API.

Uso nos módulos:
    from api.logger import get_logger
    logger = get_logger(__name__)
    logger.info("mensagem")
    logger.warning("aviso")
    logger.error("erro", exc_info=True)
"""
import logging
import os
from logging.handlers import RotatingFileHandler

# Diretório de logs na raiz do projeto (um nível acima de api/)
_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)

_LOG_FILE = os.path.join(_LOG_DIR, "api.log")

_FMT = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

# Configura o logger raiz da API uma única vez
_root = logging.getLogger("api")
if not _root.handlers:
    _root.setLevel(logging.DEBUG)

    # Console — INFO e acima
    _console = logging.StreamHandler()
    _console.setLevel(logging.INFO)
    _console.setFormatter(logging.Formatter(_FMT, datefmt=_DATE_FMT))

    # Arquivo rotativo — DEBUG e acima (10 MB × 5 backups)
    _file = RotatingFileHandler(
        _LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    _file.setLevel(logging.DEBUG)
    _file.setFormatter(logging.Formatter(_FMT, datefmt=_DATE_FMT))

    _root.addHandler(_console)
    _root.addHandler(_file)


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger filho do logger raiz 'api'."""
    if name.startswith("api."):
        return logging.getLogger(name)
    return logging.getLogger(f"api.{name}")
