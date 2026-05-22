"""Authentication, registration, and account management."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

import bcrypt

from pizza_express.config import LOGIN_ERROR
from pizza_express.database.db import get_db
from pizza_express.logic.validators import password_strength, validate_email, validate_phone


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def _ensure_email(email: str, nom: str) -> str:
    email = (email or "").strip()
    if email:
        return email
    base = re.sub(r"[^a-z0-9]", "", (nom or "user").lower())[:20] or "user"
    return f"{base}@pizza.local"


def login(email_or_user: str, password: str) -> tuple[Optional[dict[str, Any]], str]:
    ident = email_or_user.strip()
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT * FROM UTILISATEUR WHERE email = ? OR nom = ?",
            (ident, ident),
        )
        row = cur.fetchone()
    if not row:
        return None, LOGIN_ERROR
    if not verify_password(password, row["password_hash"]):
        return None, LOGIN_ERROR
    touch_session(row["id_utilisateur"])
    return dict(row), ""


def register(nom: str, email: str, telephone: str, password: str, role: str = "CAISSIER") -> tuple[bool, str]:
    if not (nom or "").strip():
        return False, "Nom obligatoire."
    email_final = _ensure_email(email, nom)
    if email.strip():
        ok, msg = validate_email(email, required=False)
        if not ok:
            return False, msg
    ok, msg = validate_phone(telephone, required=True)
    if not ok:
        return False, msg
    ok, msg = password_strength(password)
    if not ok:
        return False, msg
    tel = "".join(c for c in telephone if c.isdigit())
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id_utilisateur FROM UTILISATEUR WHERE email=?", (email_final,))
        if cur.fetchone():
            return False, "Cet identifiant/email est deja utilise."
        cur.execute(
            """INSERT INTO UTILISATEUR (nom, email, telephone, password_hash, role)
               VALUES (?,?,?,?,?)""",
            (nom.strip(), email_final, tel, hash_password(password), role),
        )
    return True, "Compte cree. Vous pouvez vous connecter."


def create_staff_account(nom: str, email: str, telephone: str, password: str, role: str) -> tuple[bool, str]:
    if role not in ("SERVEUR", "PIZZAIOLO", "LIVREUR", "CAISSIER", "MANAGER"):
        return False, "Role invalide."
    return register(nom, email, telephone, password, role)


def change_password(user_id: int, old_password: str, new_password: str) -> tuple[bool, str]:
    if not new_password:
        return False, "Nouveau mot de passe requis."
    ok, msg = password_strength(new_password)
    if not ok:
        return False, msg
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT password_hash FROM UTILISATEUR WHERE id_utilisateur=?", (user_id,))
        row = cur.fetchone()
        if not row or not verify_password(old_password, row["password_hash"]):
            return False, "Ancien mot de passe incorrect."
        cur.execute(
            "UPDATE UTILISATEUR SET password_hash=? WHERE id_utilisateur=?",
            (hash_password(new_password), user_id),
        )
    return True, "Mot de passe modifie."


def change_identifiant(user_id: int, old_password: str, new_nom: str) -> tuple[bool, str]:
    if not (new_nom or "").strip():
        return False, "Identifiant requis."
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT password_hash FROM UTILISATEUR WHERE id_utilisateur=?", (user_id,))
        row = cur.fetchone()
        if not row or not verify_password(old_password, row["password_hash"]):
            return False, "Ancien mot de passe incorrect."
        cur.execute("UPDATE UTILISATEUR SET nom=? WHERE id_utilisateur=?", (new_nom.strip(), user_id))
    return True, "Identifiant modifie."


def change_email_optional(user_id: int, old_password: str, new_email: str) -> tuple[bool, str]:
    if not new_email.strip():
        return True, ""
    ok, msg = validate_email(new_email, required=False)
    if not ok:
        return False, msg
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT password_hash FROM UTILISATEUR WHERE id_utilisateur=?", (user_id,))
        row = cur.fetchone()
        if not row or not verify_password(old_password, row["password_hash"]):
            return False, "Ancien mot de passe incorrect."
        cur.execute(
            "UPDATE UTILISATEUR SET email=? WHERE id_utilisateur=?",
            (new_email.strip(), user_id),
        )
    return True, "Email modifie."


def touch_session(user_id: int) -> None:
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "UPDATE UTILISATEUR SET derniere_activite=? WHERE id_utilisateur=?",
            (datetime.now().isoformat(), user_id),
        )


def check_session_timeout(user: dict[str, Any], timeout_seconds: int = 7200) -> bool:
    last = user.get("derniere_activite")
    if not last:
        return False
    try:
        return (datetime.now() - datetime.fromisoformat(last)).total_seconds() > timeout_seconds
    except ValueError:
        return False
