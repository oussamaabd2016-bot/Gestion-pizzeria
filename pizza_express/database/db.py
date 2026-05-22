"""SQLite database setup with schema, constraints, triggers, and indexes."""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Optional

from pizza_express.config import BACKUPS_DIR, DB_PATH, IMAGES_DIR, MEAL_DURATION_MINUTES, NO_SHOW_MINUTES


class Database:
    """Singleton-style database manager for PizzaExpress."""

    _instance: Optional["Database"] = None

    def __init__(self, db_path: str = DB_PATH) -> None:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        os.makedirs(IMAGES_DIR, exist_ok=True)
        os.makedirs(BACKUPS_DIR, exist_ok=True)
        self.db_path = db_path
        self._init_schema()

    @classmethod
    def instance(cls, db_path: str = DB_PATH) -> "Database":
        if cls._instance is None:
            cls._instance = cls(db_path)
        return cls._instance

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def cursor(self):
        conn = self.connect()
        try:
            cur = conn.cursor()
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.cursor() as cur:
            cur.executescript(_SCHEMA_SQL)
            cur.executescript(_TRIGGERS_SQL)
            cur.executescript(_INDEXES_SQL)
            self._migrate(cur)
            self._seed_if_empty(cur)

    def _migrate(self, cur: sqlite3.Cursor) -> None:
        cur.execute("PRAGMA table_info(PRODUIT)")
        cols = {r[1] for r in cur.fetchall()}
        if "image_path" not in cols:
            cur.execute("ALTER TABLE PRODUIT ADD COLUMN image_path TEXT")
        cur.execute("PRAGMA table_info(COMMANDE)")
        cols = {r[1] for r in cur.fetchall()}
        if "nom_client_libre" not in cols:
            cur.execute("ALTER TABLE COMMANDE ADD COLUMN nom_client_libre TEXT")
        cur.execute(
            """CREATE TABLE IF NOT EXISTS APP_SETTINGS (
                cle TEXT PRIMARY KEY,
                valeur TEXT
            )"""
        )
        defaults = {
            "nom_pizzeria": "PizzaExpress",
            "pizzeria_telephone": "",
            "pizzeria_email": "",
            "theme": "light",
        }
        for k, v in defaults.items():
            cur.execute(
                "INSERT OR IGNORE INTO APP_SETTINGS (cle, valeur) VALUES (?, ?)",
                (k, v),
            )

    def _seed_if_empty(self, cur: sqlite3.Cursor) -> None:
        cur.execute("SELECT COUNT(*) FROM CATEGORIE")
        if cur.fetchone()[0] == 0:
            self._seed_demo_data(cur)

    def _seed_demo_data(self, cur: sqlite3.Cursor) -> None:
        """Insert demo categories, products, ingredients, and admin user."""
        import bcrypt

        cur.executemany(
            "INSERT INTO CATEGORIE (nom, description) VALUES (?, ?)",
            [
                ("Pizzas", "Pizzas classiques et speciales"),
                ("Boissons", "Boissons fraiches"),
                ("Desserts", "Desserts maison"),
            ],
        )
        cur.execute(
            """INSERT INTO FOURNISSEUR (nom, contact, email, telephone)
               VALUES ('Fournisseur Maroc', 'Ahmed B.', 'fournisseur@pizza.ma', '0612345678')"""
        )
        cur.executemany(
            """INSERT INTO INGREDIENT (nom, stock_actuel, stock_min, prix_unitaire, id_fournisseur)
               VALUES (?, ?, ?, ?, 1)""",
            [
                ("Farine", 500, 100, 8.5),
                ("Tomate", 200, 50, 12.0),
                ("Mozzarella", 150, 40, 45.0),
                ("Jambon", 80, 20, 55.0),
                ("Champignons", 60, 15, 30.0),
            ],
        )
        cur.executemany(
            """INSERT INTO PRODUIT (nom, description, prix_small, prix_medium, prix_large,
               temps_preparation, allergenes, disponible, id_categorie)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            [
                ("Margherita", "Tomate, mozzarella", 45, 65, 85, 12, "Gluten, Lait", 1),
                ("Regina", "Jambon, champignons", 55, 75, 95, 15, "Gluten, Lait", 1),
                ("4 Fromages", "Melange de fromages", 60, 80, 100, 14, "Gluten, Lait", 1),
                ("Coca-Cola", "33cl", 12, 15, 18, 0, "", 2),
                ("Tiramisu", "Dessert italien", 25, 35, 45, 5, "Gluten, Oeufs, Lait", 3),
            ],
        )
        for pid in range(1, 4):
            cur.executemany(
                "INSERT INTO COMPOSITION (id_produit, id_ingredient, quantite_requise) VALUES (?, ?, ?)",
                [
                    (pid, 1, 0.2),
                    (pid, 2, 0.1),
                    (pid, 3, 0.15),
                ],
            )
        cur.executemany(
            """INSERT INTO TABLE_RESTAURANT (numero, capacite, zone, statut, pos_x, pos_y)
               VALUES (?, ?, ?, 'LIBRE', ?, ?)""",
            [
                (1, 4, "SALLE", 50, 50),
                (2, 4, "SALLE", 200, 50),
                (3, 6, "VIP", 350, 50),
                (4, 2, "TERRASSE", 50, 200),
                (5, 4, "TERRASSE", 200, 200),
            ],
        )
        cur.executemany(
            """INSERT INTO EMPLOYE (nom, prenom, email, telephone, poste, actif)
               VALUES (?, ?, ?, ?, ?, 1)""",
            [
                ("Admin", "Manager", "admin@pizzaexpress.ma", "0600000001", "MANAGER"),
                ("Karim", "Caissier", "caissier@pizzaexpress.ma", "0600000002", "CAISSIER"),
                ("Youssef", "Pizzaiolo", "pizza@pizzaexpress.ma", "0600000003", "PIZZAIOLO"),
            ],
        )
        pwd = bcrypt.hashpw(b"Admin123!", bcrypt.gensalt()).decode()
        cur.execute(
            """INSERT INTO UTILISATEUR (nom, email, telephone, password_hash, role, id_employe)
               VALUES ('Admin Manager', 'admin@pizzaexpress.ma', '0600000001', ?, 'MANAGER', 1)""",
            (pwd,),
        )
        cur.execute(
            """INSERT INTO CLIENT (nom, email, telephone, points_fidelite)
               VALUES ('Client Demo', 'client@demo.ma', '0698765432', 520)"""
        )


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS CATEGORIE (
    id_categorie INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS FOURNISSEUR (
    id_fournisseur INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    contact TEXT,
    email TEXT,
    telephone TEXT
);

CREATE TABLE IF NOT EXISTS INGREDIENT (
    id_ingredient INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    stock_actuel REAL NOT NULL DEFAULT 0 CHECK (stock_actuel >= 0),
    stock_min REAL NOT NULL DEFAULT 0 CHECK (stock_min >= 0),
    prix_unitaire REAL NOT NULL CHECK (prix_unitaire > 0),
    id_fournisseur INTEGER REFERENCES FOURNISSEUR(id_fournisseur)
);

CREATE TABLE IF NOT EXISTS PRODUIT (
    id_produit INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    description TEXT,
    prix_small REAL NOT NULL CHECK (prix_small > 0),
    prix_medium REAL NOT NULL CHECK (prix_medium > 0),
    prix_large REAL NOT NULL CHECK (prix_large > 0),
    temps_preparation INTEGER NOT NULL DEFAULT 10,
    allergenes TEXT DEFAULT '',
    disponible INTEGER NOT NULL DEFAULT 1,
    id_categorie INTEGER REFERENCES CATEGORIE(id_categorie),
    deleted INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS COMPOSITION (
    id_composition INTEGER PRIMARY KEY AUTOINCREMENT,
    id_produit INTEGER NOT NULL REFERENCES PRODUIT(id_produit),
    id_ingredient INTEGER NOT NULL REFERENCES INGREDIENT(id_ingredient),
    quantite_requise REAL NOT NULL CHECK (quantite_requise > 0),
    UNIQUE(id_produit, id_ingredient)
);

CREATE TABLE IF NOT EXISTS CLIENT (
    id_client INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    email TEXT UNIQUE,
    telephone TEXT UNIQUE,
    points_fidelite INTEGER NOT NULL DEFAULT 0,
    date_dernier_achat TEXT,
    actif INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS EMPLOYE (
    id_employe INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    prenom TEXT NOT NULL,
    email TEXT,
    telephone TEXT,
    poste TEXT NOT NULL CHECK (poste IN ('SERVEUR','PIZZAIOLO','LIVREUR','CAISSIER','MANAGER')),
    actif INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS UTILISATEUR (
    id_utilisateur INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    telephone TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'CAISSIER',
    id_employe INTEGER REFERENCES EMPLOYE(id_employe),
    derniere_activite TEXT
);

CREATE TABLE IF NOT EXISTS TABLE_RESTAURANT (
    id_table INTEGER PRIMARY KEY AUTOINCREMENT,
    numero INTEGER NOT NULL UNIQUE,
    capacite INTEGER NOT NULL CHECK (capacite > 0),
    zone TEXT NOT NULL CHECK (zone IN ('TERRASSE','SALLE','VIP')),
    statut TEXT NOT NULL DEFAULT 'LIBRE'
        CHECK (statut IN ('LIBRE','OCCUPEE','RESERVEE')),
    pos_x INTEGER DEFAULT 50,
    pos_y INTEGER DEFAULT 50
);

CREATE TABLE IF NOT EXISTS RESERVATION (
    id_reservation INTEGER PRIMARY KEY AUTOINCREMENT,
    id_client INTEGER NOT NULL REFERENCES CLIENT(id_client),
    id_table INTEGER NOT NULL REFERENCES TABLE_RESTAURANT(id_table),
    date_reservation TEXT NOT NULL,
    nb_personnes INTEGER NOT NULL CHECK (nb_personnes > 0),
    statut TEXT NOT NULL DEFAULT 'EN_ATTENTE'
        CHECK (statut IN ('EN_ATTENTE','CONFIRMEE','ANNULEE','TERMINEE')),
    fin_prevue TEXT
);

CREATE TABLE IF NOT EXISTS COMMANDE (
    id_commande INTEGER PRIMARY KEY AUTOINCREMENT,
    id_client INTEGER REFERENCES CLIENT(id_client),
    type_commande TEXT NOT NULL CHECK (type_commande IN ('SUR_PLACE','EMPORTER','LIVRAISON')),
    statut TEXT NOT NULL DEFAULT 'EN_ATTENTE'
        CHECK (statut IN ('EN_ATTENTE','EN_PREPARATION','PRETE','LIVREE','ANNULEE')),
    date_commande TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    montant_total REAL NOT NULL DEFAULT 0,
    frais_livraison REAL NOT NULL DEFAULT 0,
    remise_pct REAL NOT NULL DEFAULT 0,
    points_utilises INTEGER NOT NULL DEFAULT 0,
    id_employe INTEGER REFERENCES EMPLOYE(id_employe),
    id_table INTEGER REFERENCES TABLE_RESTAURANT(id_table),
    temps_prep_estime INTEGER DEFAULT 0,
    nom_client_libre TEXT
);

CREATE TABLE IF NOT EXISTS LIGNE_COMMANDE (
    id_ligne INTEGER PRIMARY KEY AUTOINCREMENT,
    id_commande INTEGER NOT NULL REFERENCES COMMANDE(id_commande) ON DELETE CASCADE,
    id_produit INTEGER NOT NULL REFERENCES PRODUIT(id_produit),
    taille TEXT NOT NULL CHECK (taille IN ('Small','Medium','Large')),
    quantite INTEGER NOT NULL CHECK (quantite > 0),
    prix_unitaire REAL NOT NULL CHECK (prix_unitaire > 0),
    remise REAL NOT NULL DEFAULT 0
);
"""

_TRIGGERS_SQL = """
-- Update montant_total when order lines change
CREATE TRIGGER IF NOT EXISTS trg_ligne_insert_total
AFTER INSERT ON LIGNE_COMMANDE
BEGIN
    UPDATE COMMANDE SET montant_total = (
        SELECT COALESCE(SUM((prix_unitaire * quantite) - remise), 0)
        FROM LIGNE_COMMANDE WHERE id_commande = NEW.id_commande
    ) WHERE id_commande = NEW.id_commande;
END;

CREATE TRIGGER IF NOT EXISTS trg_ligne_update_total
AFTER UPDATE ON LIGNE_COMMANDE
BEGIN
    UPDATE COMMANDE SET montant_total = (
        SELECT COALESCE(SUM((prix_unitaire * quantite) - remise), 0)
        FROM LIGNE_COMMANDE WHERE id_commande = NEW.id_commande
    ) WHERE id_commande = NEW.id_commande;
END;

CREATE TRIGGER IF NOT EXISTS trg_ligne_delete_total
AFTER DELETE ON LIGNE_COMMANDE
BEGIN
    UPDATE COMMANDE SET montant_total = (
        SELECT COALESCE(SUM((prix_unitaire * quantite) - remise), 0)
        FROM LIGNE_COMMANDE WHERE id_commande = OLD.id_commande
    ) WHERE id_commande = OLD.id_commande;
END;

-- Deduct stock when order moves to EN_PREPARATION
CREATE TRIGGER IF NOT EXISTS trg_stock_on_preparation
AFTER UPDATE OF statut ON COMMANDE
WHEN NEW.statut = 'EN_PREPARATION' AND OLD.statut = 'EN_ATTENTE'
BEGIN
    -- Consommation proportionnelle (3.5%) pour chaque ingrédient utilisé dans la commande
    UPDATE INGREDIENT SET stock_actuel = stock_actuel * 0.965
    WHERE id_ingredient IN (
        SELECT c.id_ingredient FROM LIGNE_COMMANDE lc
        JOIN COMPOSITION c ON c.id_produit = lc.id_produit
        WHERE lc.id_commande = NEW.id_commande
    );
    UPDATE PRODUIT SET disponible = 0 WHERE id_produit IN (
        SELECT DISTINCT lc.id_produit FROM LIGNE_COMMANDE lc
        JOIN COMPOSITION comp ON comp.id_produit = lc.id_produit
        JOIN INGREDIENT ing ON ing.id_ingredient = comp.id_ingredient
        WHERE lc.id_commande = NEW.id_commande AND ing.stock_actuel <= 0
    );
    UPDATE PRODUIT SET disponible = 1 WHERE deleted = 0 AND id_produit NOT IN (
        SELECT DISTINCT p.id_produit FROM PRODUIT p
        JOIN COMPOSITION comp ON comp.id_produit = p.id_produit
        JOIN INGREDIENT ing ON ing.id_ingredient = comp.id_ingredient
        WHERE ing.stock_actuel <= 0 AND p.deleted = 0
    );
END;

-- Loyalty points when order delivered
CREATE TRIGGER IF NOT EXISTS trg_loyalty_on_delivery
AFTER UPDATE OF statut ON COMMANDE
WHEN NEW.statut = 'LIVREE' AND OLD.statut != 'LIVREE' AND NEW.id_client IS NOT NULL
BEGIN
    UPDATE CLIENT SET
        points_fidelite = points_fidelite + CAST((NEW.montant_total + NEW.frais_livraison) / 10 AS INTEGER) - NEW.points_utilises,
        date_dernier_achat = datetime('now','localtime')
    WHERE id_client = NEW.id_client;
END;
"""

_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_client_telephone ON CLIENT(telephone);
CREATE INDEX IF NOT EXISTS idx_client_email ON CLIENT(email);
CREATE INDEX IF NOT EXISTS idx_commande_date_statut ON COMMANDE(date_commande, statut);
CREATE INDEX IF NOT EXISTS idx_produit_categorie ON PRODUIT(id_categorie);
CREATE INDEX IF NOT EXISTS idx_ingredient_fournisseur ON INGREDIENT(id_fournisseur);
CREATE INDEX IF NOT EXISTS idx_reservation_date_statut ON RESERVATION(date_reservation, statut);
"""


def get_db() -> Database:
    return Database.instance()


def run_maintenance() -> None:
    """Expire loyalty points and handle no-show reservations."""
    db = get_db()
    expiry = (datetime.now() - timedelta(days=365)).isoformat()
    with db.cursor() as cur:
        cur.execute(
            """UPDATE CLIENT SET points_fidelite = 0
               WHERE date_dernier_achat IS NOT NULL AND date_dernier_achat < ?""",
            (expiry,),
        )
        cur.execute(
            """UPDATE RESERVATION SET statut = 'ANNULEE'
               WHERE statut = 'CONFIRMEE'
               AND datetime(date_reservation, '+15 minutes') < datetime('now','localtime')
               AND id_reservation IN (
                   SELECT r.id_reservation FROM RESERVATION r
                   LEFT JOIN COMMANDE c ON c.id_table = r.id_table
                   AND datetime(c.date_commande) >= datetime(r.date_reservation)
                   WHERE c.id_commande IS NULL
               )"""
        )
        cur.execute(
            """UPDATE TABLE_RESTAURANT SET statut = 'LIBRE'
               WHERE statut = 'RESERVEE' AND id_table IN (
                   SELECT id_table FROM RESERVATION
                   WHERE statut = 'ANNULEE'
                   AND datetime(date_reservation, '+15 minutes') < datetime('now','localtime')
               )"""
        )
        cur.execute(
            """UPDATE PRODUIT SET disponible = 0 WHERE deleted = 0 AND id_produit IN (
                   SELECT DISTINCT p.id_produit FROM PRODUIT p
                   JOIN COMPOSITION c ON c.id_produit = p.id_produit
                   JOIN INGREDIENT i ON i.id_ingredient = c.id_ingredient
                   WHERE i.stock_actuel <= 0)"""
        )


def check_reservation_overlap(
    cur: sqlite3.Cursor,
    id_table: int,
    date_res: str,
    exclude_id: Optional[int] = None,
) -> bool:
    """Return True if overlapping reservation exists."""
    fin = (
        datetime.fromisoformat(date_res.replace(" ", "T")[:19])
        + timedelta(minutes=MEAL_DURATION_MINUTES)
    ).isoformat()
    sql = """
        SELECT COUNT(*) FROM RESERVATION
        WHERE id_table = ? AND statut IN ('EN_ATTENTE','CONFIRMEE')
        AND id_reservation != COALESCE(?, -1)
        AND datetime(date_reservation) < datetime(?)
        AND datetime(COALESCE(fin_prevue, datetime(date_reservation, '+90 minutes'))) > datetime(?)
    """
    cur.execute(sql, (id_table, exclude_id, fin, date_res))
    return cur.fetchone()[0] > 0


def get_setting(cle: str, default: str = "") -> str:
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT valeur FROM APP_SETTINGS WHERE cle=?", (cle,))
        row = cur.fetchone()
    return row["valeur"] if row else default


def set_setting(cle: str, valeur: str) -> None:
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO APP_SETTINGS (cle, valeur) VALUES (?,?) ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur",
            (cle, valeur),
        )
