import subprocess
import os
import logging

logger = logging.getLogger(__name__)


def _vault_path(vault: str) -> str:
    if vault == "personal":
        path = os.environ.get("PERSONAL_VAULT_PATH")
    elif vault == "agent":
        path = os.environ.get("AGENT_VAULT_PATH")
    else:
        raise ValueError(f"Unknown vault: '{vault}'. Use 'personal' or 'agent'.")
    if not path:
        raise EnvironmentError(f"{'PERSONAL' if vault == 'personal' else 'AGENT'}_VAULT_PATH not set in environment")
    return path


def _git(vault_path: str, *args) -> str:
    result = subprocess.run(
        ["git", "-C", vault_path] + list(args),
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def pull(vault: str = "agent") -> bool:
    path = _vault_path(vault)
    for attempt in range(2):
        try:
            _git(path, "pull", "--rebase")
            return True
        except RuntimeError as e:
            logger.warning(f"pull attempt {attempt + 1} failed: {e}")
    return False


def read(file_path: str, vault: str = "agent") -> str:
    """Pull then read a file from the vault. Returns file contents."""
    pull(vault)
    full_path = os.path.join(_vault_path(vault), file_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


def write(file_path: str, content: str, commit_msg: str, vault: str = "personal") -> bool:
    """Pull, write (overwrite), commit, push. Creates parent dirs if needed."""
    pull(vault)
    path = _vault_path(vault)
    full_path = os.path.join(path, file_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    _git(path, "add", file_path)
    _git(path, "commit", "-m", commit_msg)
    for attempt in range(2):
        try:
            _git(path, "push")
            return True
        except RuntimeError as e:
            logger.warning(f"push attempt {attempt + 1} failed: {e}")
    return False


def append(file_path: str, content: str, commit_msg: str, vault: str = "personal") -> bool:
    """Pull, append to file, commit, push."""
    pull(vault)
    path = _vault_path(vault)
    full_path = os.path.join(path, file_path)
    with open(full_path, "a", encoding="utf-8") as f:
        f.write(content)
    _git(path, "add", file_path)
    _git(path, "commit", "-m", commit_msg)
    for attempt in range(2):
        try:
            _git(path, "push")
            return True
        except RuntimeError as e:
            logger.warning(f"push attempt {attempt + 1} failed: {e}")
    return False


def exists(file_path: str, vault: str = "agent") -> bool:
    """Returns True if the file exists in the vault (without pulling)."""
    full_path = os.path.join(_vault_path(vault), file_path)
    return os.path.isfile(full_path)
