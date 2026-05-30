"""Service layer: file loading, calculations, and integration stubs."""

from pathlib import Path

# Repo root resolved from this file: src/api/services/__init__.py -> parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
MOCK_DIR = DATA_DIR / "mock"
RAW_DIR = DATA_DIR / "raw"
PREPARED_DIR = DATA_DIR / "prepared"
