"""Input validation helpers."""

import re

EMAIL_RE = re.compile(r"^[\w.\-+]+@[\w.\-]+\.[A-Za-z]{2,}$")
PHONE_DIGITS_RE = re.compile(r"^\d{9,}$")


def normalize_phone(phone: str) -> str:
    return "".join(c for c in phone if c.isdigit())


def validate_email(email: str, required: bool = False) -> tuple[bool, str]:
    email = (email or "").strip()
    if not email:
        if required:
            return False, "Email requis."
        return True, ""
    if len(email) < 3 or "@" not in email:
        return False, "Email invalide."
    if not EMAIL_RE.match(email):
        return False, "Email invalide."
    return True, ""


def validate_phone(phone: str, required: bool = True) -> tuple[bool, str]:
    digits = normalize_phone(phone)
    if not digits:
        if required:
            return False, "Telephone requis (9 chiffres minimum)."
        return True, ""
    if not PHONE_DIGITS_RE.match(digits):
        return False, "Telephone: chiffres uniquement, 9 minimum."
    return True, ""


def validate_positive_number(value: str, field: str = "Valeur") -> tuple[bool, str, float]:
    v = (value or "").strip().replace(",", ".")
    if not v:
        return False, f"{field} requis.", 0
    try:
        n = float(v)
        if n <= 0:
            return False, f"{field} doit etre > 0.", 0
        return True, "", n
    except ValueError:
        return False, f"{field} numerique invalide.", 0


def validate_quantity(value: str) -> tuple[bool, str, int]:
    try:
        q = int((value or "").strip())
        if q <= 0:
            return False, "Quantite doit etre > 0.", 0
        return True, "", q
    except ValueError:
        return False, "Quantite invalide.", 0


def password_strength(password: str) -> tuple[bool, str]:
    """Minimum 4 letters or digits."""
    if len(password) < 4:
        return False, "Mot de passe: minimum 4 caracteres."
    if not re.match(r"^[A-Za-z0-9]+$", password):
        return False, "Mot de passe: lettres et chiffres uniquement."
    return True, ""
