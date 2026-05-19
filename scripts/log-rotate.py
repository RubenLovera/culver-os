"""
log-rotate.py — Deletes VPS log files older than 30 days.

Runs daily at 04:05 UTC via systemd timer.
"""

import os
import sys
import time
from pathlib import Path

LOG_DIRS = [
    "/var/log",
    "/root/culver-os/logs",
]
MAX_AGE_DAYS = 30
MAX_AGE_SECONDS = MAX_AGE_DAYS * 86400


def rotate_dir(log_dir: str) -> int:
    deleted = 0
    path = Path(log_dir)
    if not path.exists():
        return 0
    cutoff = time.time() - MAX_AGE_SECONDS
    for log_file in path.glob("*.log*"):
        if log_file.is_file() and log_file.stat().st_mtime < cutoff:
            try:
                log_file.unlink()
                deleted += 1
                print(f"[log-rotate] deleted {log_file}")
            except Exception as e:
                print(f"[log-rotate] ⚠️ could not delete {log_file}: {e}")
    return deleted


def main():
    total = 0
    for log_dir in LOG_DIRS:
        total += rotate_dir(log_dir)
    print(f"[log-rotate] ✅ deleted {total} log files older than {MAX_AGE_DAYS} days")


if __name__ == "__main__":
    main()
