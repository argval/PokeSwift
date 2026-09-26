"""Load Players/Jev/.env into the process environment."""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = PACKAGE_ROOT / ".env"
REPO_ENV_PATH = PACKAGE_ROOT.parent / ".env"


def load_player_env(path=None):
    """Load KEY=VALUE pairs from .env without overwriting existing exports.

    Checks `Players/Jev/.env` first, then the repo-root `.env`. Returns the
    path that was loaded, or None when no file is present.
    """
    from dotenv import load_dotenv

    if path is not None:
        env_path = Path(path)
        if not env_path.is_file():
            return None
        load_dotenv(env_path, override=False)
        return env_path

    for env_path in (DEFAULT_ENV_PATH, REPO_ENV_PATH):
        if env_path.is_file():
            load_dotenv(env_path, override=False)
            return env_path
    return None
