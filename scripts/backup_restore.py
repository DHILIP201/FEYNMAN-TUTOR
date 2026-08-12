"""
scripts/backup_restore.py
=========================
Production disaster recovery and snapshot verification utility for Feynman AI.
Supports both SQLite local snapshots and PostgreSQL pg_dump / pg_restore pipelines.
"""

import os
import shutil
import subprocess
import time
from datetime import datetime
from typing import Dict, Any


def create_database_backup(backup_dir: str = "./backups") -> Dict[str, Any]:
    """
    Creates a timestamped snapshot backup of the current database.
    """
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    db_url = os.getenv("DATABASE_URL", "sqlite:///./feynman.db")

    if "sqlite" in db_url:
        sqlite_file = db_url.replace("sqlite:///", "").replace("sqlite://", "")
        if not os.path.exists(sqlite_file):
            return {"status": "error", "message": f"SQLite database file '{sqlite_file}' not found."}
        
        backup_filename = f"feynman_backup_{timestamp}.sqlite3"
        dest_path = os.path.join(backup_dir, backup_filename)
        shutil.copy2(sqlite_file, dest_path)
        size_bytes = os.path.getsize(dest_path)
        return {
            "status": "success",
            "db_type": "sqlite",
            "source": sqlite_file,
            "backup_path": dest_path,
            "size_bytes": size_bytes,
            "timestamp": timestamp
        }
    else:
        # PostgreSQL backup via pg_dump
        backup_filename = f"feynman_pg_backup_{timestamp}.dump"
        dest_path = os.path.join(backup_dir, backup_filename)
        try:
            cmd = ["pg_dump", "-Fc", "--no-owner", "--no-acl", "-f", dest_path, db_url]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode == 0 and os.path.exists(dest_path):
                return {
                    "status": "success",
                    "db_type": "postgresql",
                    "backup_path": dest_path,
                    "size_bytes": os.path.getsize(dest_path),
                    "timestamp": timestamp
                }
            else:
                return {"status": "error", "detail": res.stderr}
        except Exception as e:
            return {"status": "error", "detail": str(e)}


def restore_database_backup(backup_path: str, target_db_path: str = "./feynman.db") -> Dict[str, Any]:
    """
    Restores a database from a verified snapshot backup.
    """
    if not os.path.exists(backup_path):
        return {"status": "error", "message": f"Backup file '{backup_path}' does not exist."}

    if backup_path.endswith(".sqlite3") or backup_path.endswith(".db"):
        shutil.copy2(backup_path, target_db_path)
        return {
            "status": "success",
            "restored_to": target_db_path,
            "size_bytes": os.path.getsize(target_db_path)
        }
    else:
        # PostgreSQL restore
        db_url = os.getenv("DATABASE_URL", "")
        try:
            cmd = ["pg_restore", "--clean", "--if-exists", "--no-owner", "-d", db_url, backup_path]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            return {
                "status": "success" if res.returncode == 0 else "warning",
                "detail": res.stderr
            }
        except Exception as e:
            return {"status": "error", "detail": str(e)}


if __name__ == "__main__":
    print("Testing backup utility...")
    bk = create_database_backup()
    print("Backup result:", bk)
