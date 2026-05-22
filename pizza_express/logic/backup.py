"""Database backup and restore."""

import os
import shutil
from datetime import datetime

from pizza_express.config import BACKUPS_DIR, DB_PATH


def create_backup() -> str:
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    name = f"pizza_express_{datetime.now():%Y%m%d_%H%M%S}.db"
    dest = os.path.join(BACKUPS_DIR, name)
    shutil.copy2(DB_PATH, dest)
    return dest


def restore_backup(backup_path: str) -> tuple[bool, str]:
    if not os.path.isfile(backup_path):
        return False, "Fichier introuvable."
    shutil.copy2(backup_path, DB_PATH)
    from pizza_express.database.db import Database
    Database._instance = None
    return True, "Base restauree. Redemarrez l'application."
