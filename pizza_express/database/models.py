"""Object-oriented model wrappers for database entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from pizza_express.database.db import get_db


@dataclass
class Client:
    id_client: Optional[int] = None
    nom: str = ""
    email: str = ""
    telephone: str = ""
    points_fidelite: int = 0
    date_dernier_achat: Optional[str] = None
    actif: int = 1

    def save(self) -> int:
        from pizza_express.logic.validators import normalize_phone

        tel = normalize_phone(self.telephone)
        email = (self.email or "").strip() or None
        db = get_db()
        with db.cursor() as cur:
            if self.id_client:
                cur.execute(
                    """UPDATE CLIENT SET nom=?, email=?, telephone=?,
                       points_fidelite=?, actif=? WHERE id_client=?""",
                    (self.nom, email, tel, self.points_fidelite, self.actif, self.id_client),
                )
                return self.id_client
            cur.execute(
                "INSERT INTO CLIENT (nom, email, telephone, points_fidelite) VALUES (?,?,?,?)",
                (self.nom, email, tel, self.points_fidelite),
            )
            self.id_client = cur.lastrowid
            return self.id_client

    def deactivate(self) -> None:
        self.actif = 0
        self.save()

    @classmethod
    def get(cls, id_client: int) -> Optional["Client"]:
        db = get_db()
        with db.cursor() as cur:
            cur.execute("SELECT * FROM CLIENT WHERE id_client=?", (id_client,))
            row = cur.fetchone()
        return cls._from_row(row) if row else None

    @classmethod
    def search(cls, term: str) -> list["Client"]:
        db = get_db()
        t = f"%{term}%"
        with db.cursor() as cur:
            cur.execute(
                """SELECT * FROM CLIENT WHERE actif=1 AND
                   (nom LIKE ? OR email LIKE ? OR telephone LIKE ?)""",
                (t, t, t),
            )
            return [cls._from_row(r) for r in cur.fetchall()]

    @classmethod
    def _from_row(cls, row: Any) -> "Client":
        return cls(
            id_client=row["id_client"],
            nom=row["nom"],
            email=row["email"] or "",
            telephone=row["telephone"] or "",
            points_fidelite=row["points_fidelite"],
            date_dernier_achat=row["date_dernier_achat"],
            actif=row["actif"],
        )


@dataclass
class Produit:
    id_produit: Optional[int] = None
    nom: str = ""
    description: str = ""
    prix_small: float = 0
    prix_medium: float = 0
    prix_large: float = 0
    temps_preparation: int = 10
    allergenes: str = ""
    disponible: int = 1
    id_categorie: Optional[int] = None
    deleted: int = 0
    image_path: str = ""

    def prix_for_taille(self, taille: str) -> float:
        return {"Small": self.prix_small, "Medium": self.prix_medium, "Large": self.prix_large}.get(taille, self.prix_medium)

    def save(self) -> int:
        db = get_db()
        with db.cursor() as cur:
            if self.id_produit:
                cur.execute(
                    """UPDATE PRODUIT SET nom=?, description=?, prix_small=?, prix_medium=?,
                       prix_large=?, temps_preparation=?, allergenes=?, disponible=?,
                       id_categorie=?, image_path=? WHERE id_produit=?""",
                    (
                        self.nom, self.description, self.prix_small, self.prix_medium,
                        self.prix_large, self.temps_preparation, self.allergenes,
                        self.disponible, self.id_categorie, self.image_path or "", self.id_produit,
                    ),
                )
                return self.id_produit
            cur.execute(
                """INSERT INTO PRODUIT (nom, description, prix_small, prix_medium, prix_large,
                   temps_preparation, allergenes, disponible, id_categorie, image_path)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    self.nom, self.description, self.prix_small, self.prix_medium,
                    self.prix_large, self.temps_preparation, self.allergenes,
                    self.disponible, self.id_categorie, self.image_path or "",
                ),
            )
            self.id_produit = cur.lastrowid
            return self.id_produit

    def soft_delete(self) -> None:
        db = get_db()
        with db.cursor() as cur:
            cur.execute("UPDATE PRODUIT SET deleted=1, disponible=0 WHERE id_produit=?", (self.id_produit,))

    def reactivate(self) -> None:
        db = get_db()
        with db.cursor() as cur:
            cur.execute("UPDATE PRODUIT SET deleted=0, disponible=1 WHERE id_produit=?", (self.id_produit,))

    @classmethod
    def list_active(cls) -> list["Produit"]:
        db = get_db()
        with db.cursor() as cur:
            cur.execute("SELECT * FROM PRODUIT WHERE deleted=0 ORDER BY nom")
            return [cls._from_row(r) for r in cur.fetchall()]

    @classmethod
    def _from_row(cls, row: Any) -> "Produit":
        keys = cls.__dataclass_fields__
        return cls(**{k: row[k] for k in keys if k in row.keys()})


@dataclass
class Categorie:
    id_categorie: Optional[int] = None
    nom: str = ""
    description: str = ""

    def save(self) -> int:
        db = get_db()
        with db.cursor() as cur:
            if self.id_categorie:
                cur.execute("UPDATE CATEGORIE SET nom=?, description=? WHERE id_categorie=?", (self.nom, self.description, self.id_categorie))
            else:
                cur.execute("INSERT INTO CATEGORIE (nom, description) VALUES (?,?)", (self.nom, self.description))
                self.id_categorie = cur.lastrowid
        return self.id_categorie or 0


@dataclass
class Employe:
    id_employe: Optional[int] = None
    nom: str = ""
    prenom: str = ""
    email: str = ""
    telephone: str = ""
    poste: str = "CAISSIER"
    actif: int = 1

    def save(self) -> int:
        db = get_db()
        with db.cursor() as cur:
            if self.id_employe:
                cur.execute(
                    "UPDATE EMPLOYE SET nom=?, prenom=?, email=?, telephone=?, poste=?, actif=? WHERE id_employe=?",
                    (self.nom, self.prenom, self.email, self.telephone, self.poste, self.actif, self.id_employe),
                )
            else:
                cur.execute(
                    "INSERT INTO EMPLOYE (nom, prenom, email, telephone, poste) VALUES (?,?,?,?,?)",
                    (self.nom, self.prenom, self.email, self.telephone, self.poste),
                )
                self.id_employe = cur.lastrowid
        return self.id_employe or 0

    def soft_delete(self) -> None:
        self.actif = 0
        self.save()


@dataclass
class Ingredient:
    id_ingredient: Optional[int] = None
    nom: str = ""
    stock_actuel: float = 0
    stock_min: float = 0
    prix_unitaire: float = 0
    id_fournisseur: Optional[int] = None

    @property
    def alert_level(self) -> str:
        if self.stock_min <= 0:
            return "OK"
        if self.stock_actuel < 0.5 * self.stock_min:
            return "RED"
        if self.stock_actuel < self.stock_min:
            return "ORANGE"
        return "OK"

    @property
    def valorized(self) -> float:
        return self.stock_actuel * self.prix_unitaire


@dataclass
class Fournisseur:
    id_fournisseur: Optional[int] = None
    nom: str = ""
    contact: str = ""
    email: str = ""
    telephone: str = ""


@dataclass
class Composition:
    id_produit: int = 0
    id_ingredient: int = 0
    quantite_requise: float = 0


@dataclass
class Commande:
    id_commande: Optional[int] = None
    id_client: Optional[int] = None
    type_commande: str = "SUR_PLACE"
    statut: str = "EN_ATTENTE"
    date_commande: str = ""
    montant_total: float = 0
    frais_livraison: float = 0
    remise_pct: float = 0
    points_utilises: int = 0
    id_employe: Optional[int] = None
    id_table: Optional[int] = None
    temps_prep_estime: int = 0
    nom_client_libre: str = ""

    def save(self) -> int:
        db = get_db()
        with db.cursor() as cur:
            if self.id_commande:
                cur.execute(
                    """UPDATE COMMANDE SET id_client=?, type_commande=?, statut=?,
                       frais_livraison=?, remise_pct=?, points_utilises=?,
                       id_employe=?, id_table=?, temps_prep_estime=?, nom_client_libre=?
                       WHERE id_commande=?""",
                    (
                        self.id_client, self.type_commande, self.statut,
                        self.frais_livraison, self.remise_pct, self.points_utilises,
                        self.id_employe, self.id_table, self.temps_prep_estime,
                        self.nom_client_libre, self.id_commande,
                    ),
                )
            else:
                cur.execute(
                    """INSERT INTO COMMANDE (id_client, type_commande, statut, frais_livraison,
                       remise_pct, points_utilises, id_employe, id_table, temps_prep_estime, nom_client_libre)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        self.id_client, self.type_commande, self.statut,
                        self.frais_livraison, self.remise_pct, self.points_utilises,
                        self.id_employe, self.id_table, self.temps_prep_estime,
                        self.nom_client_libre,
                    ),
                )
                self.id_commande = cur.lastrowid
        return self.id_commande or 0


@dataclass
class LigneCommande:
    id_ligne: Optional[int] = None
    id_commande: int = 0
    id_produit: int = 0
    taille: str = "Medium"
    quantite: int = 1
    prix_unitaire: float = 0
    remise: float = 0


@dataclass
class TableRestaurant:
    id_table: Optional[int] = None
    numero: int = 0
    capacite: int = 4
    zone: str = "SALLE"
    statut: str = "LIBRE"
    pos_x: int = 50
    pos_y: int = 50


@dataclass
class Reservation:
    id_reservation: Optional[int] = None
    id_client: int = 0
    id_table: int = 0
    date_reservation: str = ""
    nb_personnes: int = 2
    statut: str = "EN_ATTENTE"
    fin_prevue: Optional[str] = None


@dataclass
class Utilisateur:
    id_utilisateur: Optional[int] = None
    nom: str = ""
    email: str = ""
    telephone: str = ""
    password_hash: str = ""
    role: str = "CAISSIER"
    id_employe: Optional[int] = None
