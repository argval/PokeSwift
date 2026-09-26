"""Load Players/Jev/.env into the process environment."""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = PACKAGE_ROOT / ".env"


def load_player_env(path=None):
    """Load KEY=VALUE pairs from .env without overwriting existing exports.

    Returns the path that was loaded, or None when the file is missing.
    """
    from dotenv import load_dotenv

    env_path = Path(path) if path is not None else DEFAULT_ENV_PATH
    if not env_path.is_file():
        return None
    load_dotenv(env_path, override=False)
    return env_path
