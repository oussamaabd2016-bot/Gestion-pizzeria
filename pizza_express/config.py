"""Configuration and constants for PizzaExpress."""

import os

# Light theme (calm business palette)
THEME_LIGHT = {
    "primary": "#256D85",
    "primary_dark": "#1E5668",
    "primary_light": "#5EA6B8",
    "accent": "#D9A441",
    "bg": "#F7F9FB",
    "bg_alt": "#E8EEF2",
    "card": "#FFFFFF",
    "sidebar": "#2B2D31",
    "sidebar_text": "#F4F6F8",
    "text": "#202327",
    "text_muted": "#69717A",
    "success": "#2F7D5C",
    "warning": "#D9A441",
    "danger": "#C94A4A",
    "border": "#DDE4EA",
}

THEME_DARK = {
    "primary": "#6BB7C8",
    "primary_dark": "#3A8FA3",
    "primary_light": "#92D3DE",
    "accent": "#E0B75B",
    "bg": "#181A1B",
    "bg_alt": "#222629",
    "card": "#25292C",
    "sidebar": "#111315",
    "sidebar_text": "#F4F6F8",
    "text": "#EEF2F3",
    "text_muted": "#AAB3B8",
    "success": "#68B58B",
    "warning": "#E0B75B",
    "danger": "#E57373",
    "border": "#3A4146",
}

# Legacy aliases
PRIMARY_RED = THEME_LIGHT["primary"]
SECONDARY_RED = THEME_LIGHT["accent"]
LIGHT_RED = THEME_LIGHT["bg_alt"]
DARK_RED = THEME_LIGHT["primary_dark"]
BG_COLOR = THEME_LIGHT["bg"]
CARD_BG = THEME_LIGHT["card"]
TEXT_DARK = THEME_LIGHT["text"]
TEXT_MUTED = THEME_LIGHT["text_muted"]
SUCCESS = THEME_LIGHT["success"]
WARNING = THEME_LIGHT["warning"]
DANGER = THEME_LIGHT["danger"]

# Business rules
LOYALTY_POINTS_PER_10_MAD = 1
LOYALTY_FREE_PIZZA_POINTS = 100
LOYALTY_DISCOUNT_THRESHOLD = 500
LOYALTY_DISCOUNT_PERCENT = 5
DELIVERY_FREE_THRESHOLD_MAD = 150
DELIVERY_FEE_MAD = 25
VAT_RATE = 0.20
PREP_BUFFER_MINUTES = 10
SESSION_TIMEOUT_SECONDS = 2 * 60 * 60
LOYALTY_EXPIRY_DAYS = 365
RESERVATION_MIN_ADVANCE_HOURS = 1
NO_SHOW_MINUTES = 15
MEAL_DURATION_MINUTES = 90

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "pizza_express.db")
REPORTS_DIR = os.path.join(BASE_DIR, "data", "reports")
IMAGES_DIR = os.path.join(BASE_DIR, "data", "images")
BACKUPS_DIR = os.path.join(BASE_DIR, "data", "backups")

TYPE_COMMANDE = ("SUR_PLACE", "EMPORTER", "LIVRAISON")
STATUT_COMMANDE = ("EN_ATTENTE", "EN_PREPARATION", "PRETE", "LIVREE", "ANNULEE")
STATUT_TABLE = ("LIBRE", "OCCUPEE", "RESERVEE")
STATUT_RESERVATION = ("EN_ATTENTE", "CONFIRMEE", "ANNULEE", "TERMINEE")
POSTE_EMPLOYE = ("SERVEUR", "PIZZAIOLO", "LIVREUR", "CAISSIER", "MANAGER")
ZONE_TABLE = ("TERRASSE", "SALLE", "VIP")
TAILLES = ("Small", "Medium", "Large")
ACCOUNT_ROLES = ("SERVEUR", "PIZZAIOLO", "LIVREUR", "CAISSIER", "MANAGER")

ROLE_ACCESS = {
    "MANAGER": {"dashboard", "customers", "orders", "menu", "stock", "employees", "tables", "reports", "settings"},
    "CAISSIER": {"dashboard", "customers", "orders", "menu", "stock", "tables", "reports", "settings"},
    "SERVEUR": {"dashboard", "customers", "orders", "menu", "stock", "tables", "reports", "settings"},
    "PIZZAIOLO": {"dashboard", "orders", "menu", "settings"},
    "LIVREUR": {"dashboard", "orders", "settings"},
    "STOCK_MANAGER": {"dashboard", "stock", "menu", "settings"},
}

ORDER_STATUS_COLORS = {
    "LIVREE": "#2F7D5C",
    "EN_PREPARATION": "#D9A441",
    "ANNULEE": "#C94A4A",
    "EN_ATTENTE": "#69717A",
    "PRETE": "#3A7CA5",
}

LOGIN_ERROR = "Identifiant ou mot de passe est incorrect."
