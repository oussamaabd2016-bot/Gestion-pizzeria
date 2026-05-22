"""Core business rules for orders, loyalty, VAT, and delivery."""

from __future__ import annotations

from typing import Optional

from pizza_express.config import (
    DELIVERY_FEE_MAD,
    DELIVERY_FREE_THRESHOLD_MAD,
    LOYALTY_DISCOUNT_PERCENT,
    LOYALTY_DISCOUNT_THRESHOLD,
    LOYALTY_FREE_PIZZA_POINTS,
    PREP_BUFFER_MINUTES,
    VAT_RATE,
)
from pizza_express.database.db import get_db
from pizza_express.database.models import Client


def delivery_fee(subtotal: float, order_type: str) -> float:
    if order_type != "LIVRAISON":
        return 0.0
    return 0.0 if subtotal >= DELIVERY_FREE_THRESHOLD_MAD else float(DELIVERY_FEE_MAD)


def loyalty_discount_percent(client: Optional[Client]) -> float:
    if client and client.points_fidelite > LOYALTY_DISCOUNT_THRESHOLD:
        return float(LOYALTY_DISCOUNT_PERCENT)
    return 0.0


def can_redeem_free_pizza(points: int) -> bool:
    return points >= LOYALTY_FREE_PIZZA_POINTS


def vat_breakdown(ttc_amount: float) -> dict[str, float]:
    """Prices are TTC; extract HT and VAT at 20%."""
    ht = ttc_amount / (1 + VAT_RATE)
    tva = ttc_amount - ht
    return {"ht": round(ht, 2), "tva": round(tva, 2), "ttc": round(ttc_amount, 2)}


def estimate_prep_minutes(product_ids_quantities: list[tuple[int, int]]) -> int:
    db = get_db()
    total = PREP_BUFFER_MINUTES
    with db.cursor() as cur:
        for pid, qty in product_ids_quantities:
            cur.execute("SELECT temps_preparation FROM PRODUIT WHERE id_produit=?", (pid,))
            row = cur.fetchone()
            if row:
                total += row["temps_preparation"] * qty
    return total


def employee_has_active_order(employe_id: int, exclude_commande: Optional[int] = None) -> bool:
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """SELECT COUNT(*) FROM COMMANDE
               WHERE id_employe=? AND statut IN ('EN_ATTENTE','EN_PREPARATION','PRETE')
               AND id_commande != COALESCE(?, -1)""",
            (employe_id, exclude_commande),
        )
        return cur.fetchone()[0] > 0


def compute_order_totals(
    subtotal: float,
    order_type: str,
    client: Optional[Client],
    points_to_use: int = 0,
) -> dict[str, float]:
    remise_pct = loyalty_discount_percent(client)
    remise = subtotal * remise_pct / 100
    after_remise = subtotal - remise
    frais = delivery_fee(after_remise, order_type)
    total = after_remise + frais
    return {
        "subtotal": subtotal,
        "remise_pct": remise_pct,
        "remise": remise,
        "frais_livraison": frais,
        "total": total,
        "points_utilises": min(points_to_use, LOYALTY_FREE_PIZZA_POINTS) if points_to_use else 0,
    }


def ingredients_below_min() -> list[dict]:
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """SELECT i.*, f.nom AS fournisseur_nom FROM INGREDIENT i
               LEFT JOIN FOURNISSEUR f ON f.id_fournisseur = i.id_fournisseur
               WHERE i.stock_actuel < i.stock_min ORDER BY i.stock_actuel"""
        )
        return [dict(r) for r in cur.fetchall()]


def receipt_lines(commande_id: int) -> list[str]:
    db = get_db()
    lines = []
    with db.cursor() as cur:
        cur.execute(
            """SELECT lc.*, p.nom FROM LIGNE_COMMANDE lc
               JOIN PRODUIT p ON p.id_produit = lc.id_produit
               WHERE lc.id_commande=?""",
            (commande_id,),
        )
        for r in cur.fetchall():
            total_ligne = r["prix_unitaire"] * r["quantite"] - r["remise"]
            vat = vat_breakdown(total_ligne)
            lines.append(
                f"{r['nom']} ({r['taille']}) x{r['quantite']} = {total_ligne:.2f} MAD "
                f"(HT {vat['ht']:.2f} + TVA {vat['tva']:.2f})"
            )
        cur.execute("SELECT * FROM COMMANDE WHERE id_commande=?", (commande_id,))
        cmd = cur.fetchone()
        if cmd:
            vat_total = vat_breakdown(cmd["montant_total"] + cmd["frais_livraison"])
            lines.append(f"Frais livraison: {cmd['frais_livraison']:.2f} MAD")
            lines.append(f"Total TTC: {vat_total['ttc']:.2f} MAD (HT {vat_total['ht']:.2f}, TVA 20%: {vat_total['tva']:.2f})")
    return lines
