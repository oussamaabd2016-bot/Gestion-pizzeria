"""Report generation and pending orders queries."""

import csv
import os
from datetime import datetime, timedelta
from typing import Optional

from pizza_express.config import REPORTS_DIR
from pizza_express.logic.business import vat_breakdown
from pizza_express.database.db import get_db, get_setting


STATUS_DOTS = {
    "EN_ATTENTE": "○",
    "EN_PREPARATION": "●",
    "PRETE": "●",
    "LIVREE": "●",
    "ANNULEE": "●",
}

STATUS_COLORS = {
    "EN_ATTENTE": "#F7F7F7",
    "EN_PREPARATION": "#F1C40F", # Yellow
    "PRETE": "#27AE60",         # Green
    "LIVREE": "#27AE60",        # Green
    "ANNULEE": "#E74C3C",       # Red
}

STATUS_ORDER_SQL = """
CASE c.statut
    WHEN 'EN_ATTENTE' THEN 1
    WHEN 'EN_PREPARATION' THEN 2
    WHEN 'PRETE' THEN 3
    WHEN 'LIVREE' THEN 4
    WHEN 'ANNULEE' THEN 5
    ELSE 6
END
"""


def status_dot(status: str) -> str:
    return f"{STATUS_DOTS.get(status, '⚪')} {status}"


def _ensure_reports_dir() -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    return REPORTS_DIR


def _period_bounds(period: str = "day") -> tuple[str, str, str, str]:
    now = datetime.now()
    if period == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = now
    last_year_start = start.replace(year=start.year - 1)
    last_year_end = end.replace(year=end.year - 1)
    return (
        start.strftime("%Y-%m-%d %H:%M:%S"),
        end.strftime("%Y-%m-%d %H:%M:%S"),
        last_year_start.strftime("%Y-%m-%d %H:%M:%S"),
        last_year_end.strftime("%Y-%m-%d %H:%M:%S"),
    )


def pending_orders(user_role: str | None = None) -> list[dict]:
    """Active orders; filtered by role (PIZZAIOLO=pizza products, LIVREUR=delivery)."""
    db = get_db()
    role = (user_role or "").upper()
    base = """
        SELECT DISTINCT c.id_commande, c.type_commande, c.statut, c.date_commande,
               c.montant_total, COALESCE(cl.nom, 'Sans client') AS client_nom
        FROM COMMANDE c
        LEFT JOIN CLIENT cl ON cl.id_client = c.id_client
    """
    where = " WHERE c.statut NOT IN ('LIVREE', 'ANNULEE') "
    params: list = []

    if role == "LIVREUR":
        where += " AND c.type_commande = 'LIVRAISON' "
    elif role == "PIZZAIOLO":
        base += """
            JOIN LIGNE_COMMANDE lc ON lc.id_commande = c.id_commande
            JOIN PRODUIT p ON p.id_produit = lc.id_produit
            JOIN CATEGORIE cat ON cat.id_categorie = p.id_categorie
        """
        where += " AND (LOWER(cat.nom) LIKE '%pizza%' OR cat.id_categorie = 1) "

    sql = base + where + f" ORDER BY {STATUS_ORDER_SQL}, datetime(c.date_commande) ASC"
    with db.cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def sales_summary(period: str = "day") -> dict:
    db = get_db()
    s, e, ls, le = _period_bounds(period)
    with db.cursor() as cur:
        cur.execute(
            """SELECT COALESCE(SUM(montant_total + frais_livraison), 0) FROM COMMANDE
               WHERE statut='LIVREE' AND date_commande BETWEEN ? AND ?""",
            (s, e),
        )
        current = cur.fetchone()[0]
        cur.execute(
            """SELECT COALESCE(SUM(montant_total + frais_livraison), 0) FROM COMMANDE
               WHERE statut='LIVREE' AND date_commande BETWEEN ? AND ?""",
            (ls, le),
        )
        previous = cur.fetchone()[0]
        cur.execute(
            """SELECT p.nom, SUM(lc.quantite) AS qty FROM LIGNE_COMMANDE lc
               JOIN PRODUIT p ON p.id_produit = lc.id_produit
               JOIN COMMANDE c ON c.id_commande = lc.id_commande
               WHERE c.statut='LIVREE' AND c.date_commande BETWEEN ? AND ?
               GROUP BY p.id_produit ORDER BY qty DESC LIMIT 5""",
            (s, e),
        )
        top = [dict(r) for r in cur.fetchall()]
    change = ((current - previous) / previous * 100) if previous else 0
    return {"current": current, "previous": previous, "change_pct": change, "top_products": top}


def stock_valorized_report() -> list[dict]:
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """SELECT nom, stock_actuel, stock_min, prix_unitaire,
               (stock_actuel * prix_unitaire) AS valorise FROM INGREDIENT ORDER BY nom"""
        )
        return [dict(r) for r in cur.fetchall()]


def employee_performance() -> list[dict]:
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """SELECT e.nom || ' ' || e.prenom AS employe, e.poste,
               COUNT(c.id_commande) AS nb_commandes,
               COALESCE(SUM(c.montant_total), 0) AS ca
               FROM EMPLOYE e
               LEFT JOIN COMMANDE c ON c.id_employe = e.id_employe AND c.statut='LIVREE'
               WHERE e.actif=1 GROUP BY e.id_employe"""
        )
        return [dict(r) for r in cur.fetchall()]


def export_csv(filename: str, headers: list[str], rows: list[list]) -> str:
    path = os.path.join(_ensure_reports_dir(), filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    return path


def export_sales_csv(period: str = "day") -> str:
    data = sales_summary(period)
    rows = [
        ["Periode actuelle", data["current"]],
        ["Meme periode annee precedente", data["previous"]],
        ["Variation %", f"{data['change_pct']:.1f}"],
    ]
    for p in data["top_products"]:
        rows.append([p["nom"], p["qty"]])
    return export_csv(f"ventes_{datetime.now():%Y%m%d_%H%M%S}.csv", ["Indicateur", "Valeur"], rows)


def export_stock_csv() -> str:
    data = stock_valorized_report()
    rows = [[r["nom"], r["stock_actuel"], r["stock_min"], r["prix_unitaire"], r["valorise"]] for r in data]
    return export_csv(
        f"stock_{datetime.now():%Y%m%d_%H%M%S}.csv",
        ["Ingredient", "Stock", "Min", "Prix unit.", "Valorise MAD"],
        rows,
    )


def export_reorder_slip() -> Optional[str]:
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """SELECT i.nom, i.stock_actuel, i.stock_min,
               CASE WHEN (i.stock_min * 2 - i.stock_actuel) > 0 THEN (i.stock_min * 2 - i.stock_actuel) ELSE 0 END AS qty_commander,
               f.nom AS fournisseur
               FROM INGREDIENT i
               JOIN FOURNISSEUR f ON f.id_fournisseur = i.id_fournisseur
               WHERE i.stock_actuel < i.stock_min"""
        )
        items = cur.fetchall()
    if not items:
        return None
    rows = [[r["nom"], r["stock_actuel"], r["stock_min"], r["qty_commander"], r["fournisseur"]] for r in items]
    return export_csv(
        f"reappro_{datetime.now():%Y%m%d_%H%M%S}.csv",
        ["Ingredient", "Stock", "Min", "A commander", "Fournisseur"],
        rows,
    )


def export_pdf_report(title: str, lines: list[str]) -> str:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        path = os.path.join(_ensure_reports_dir(), f"{title.replace(' ', '_')}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(title + "\n\n" + "\n".join(lines))
        return path
    path = os.path.join(_ensure_reports_dir(), f"{title.replace(' ', '_')}_{datetime.now():%Y%m%d_%H%M%S}.pdf")
    c = canvas.Canvas(path, pagesize=A4)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 800, title)
    c.setFont("Helvetica", 10)
    y = 770
    for line in lines:
        c.drawString(50, y, line[:90])
        y -= 14
        if y < 50:
            c.showPage()
            y = 800
    c.save()
    return path


def _receipt_data(commande_id: int) -> tuple[dict, list[dict]]:
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """SELECT c.*, COALESCE(cl.nom, 'Sans client') AS client_nom,
               COALESCE(cl.telephone, '') AS client_tel,
               COALESCE(e.nom || ' ' || e.prenom, '') AS employe_nom,
               COALESCE(t.numero, '') AS table_numero
               FROM COMMANDE c
               LEFT JOIN CLIENT cl ON cl.id_client = c.id_client
               LEFT JOIN EMPLOYE e ON e.id_employe = c.id_employe
               LEFT JOIN TABLE_RESTAURANT t ON t.id_table = c.id_table
               WHERE c.id_commande=?""",
            (commande_id,),
        )
        order = cur.fetchone()
        if not order:
            raise ValueError(f"Commande #{commande_id} introuvable.")
        cur.execute(
            """SELECT lc.*, p.nom
               FROM LIGNE_COMMANDE lc
               JOIN PRODUIT p ON p.id_produit = lc.id_produit
               WHERE lc.id_commande=?
               ORDER BY lc.id_ligne""",
            (commande_id,),
        )
        lines = [dict(r) for r in cur.fetchall()]
    return dict(order), lines


def export_receipt_pdf(commande_id: int) -> str:
    order, lines = _receipt_data(commande_id)
    pizzeria = get_setting("nom_pizzeria", "PizzaExpress") or "PizzaExpress"
    phone = get_setting("pizzeria_telephone", "")
    email = get_setting("pizzeria_email", "")
    filename = f"recu_commande_{commande_id}_{datetime.now():%Y%m%d_%H%M%S}"
    try:
        from reportlab.lib.pagesizes import A6
        from reportlab.pdfgen import canvas
    except ImportError:
        path = os.path.join(_ensure_reports_dir(), f"{filename}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"{pizzeria}\n")
            if phone:
                f.write(f"Tel: {phone}\n")
            if email:
                f.write(f"Email: {email}\n")
            f.write(f"\nRecu commande #{commande_id}\n")
            f.write(f"Date: {order['date_commande'][:16]}\n")
            f.write(f"Client: {order['client_nom']}\n\n")
            for line in lines:
                total_line = line["prix_unitaire"] * line["quantite"] - line["remise"]
                f.write(f"{line['nom']} {line['taille']} x{line['quantite']} {total_line:.2f} MAD\n")
            total_ttc = order["montant_total"] + order["frais_livraison"]
            vat = vat_breakdown(total_ttc)
            f.write(f"\nSous-total: {order['montant_total']:.2f} MAD\n")
            f.write(f"Livraison: {order['frais_livraison']:.2f} MAD\n")
            f.write(f"Total TTC: {vat['ttc']:.2f} MAD\nHT: {vat['ht']:.2f} MAD\nTVA: {vat['tva']:.2f} MAD\n")
        return path

    path = os.path.join(_ensure_reports_dir(), f"{filename}.pdf")
    pdf = canvas.Canvas(path, pagesize=A6)
    width, height = A6
    y = height - 24

    def center(text: str, font="Helvetica", size=9, step=12) -> None:
        nonlocal y
        pdf.setFont(font, size)
        pdf.drawCentredString(width / 2, y, text[:40])
        y -= step

    def left(text: str, font="Helvetica", size=8, step=11) -> None:
        nonlocal y
        pdf.setFont(font, size)
        pdf.drawString(18, y, text[:42])
        y -= step

    def right(label: str, value: str, font="Helvetica", size=8, step=11) -> None:
        nonlocal y
        pdf.setFont(font, size)
        pdf.drawString(18, y, label[:24])
        pdf.drawRightString(width - 18, y, value[:16])
        y -= step

    center(pizzeria, "Helvetica-Bold", 13, 15)
    if phone:
        center(f"Tel: {phone}", size=8, step=10)
    if email:
        center(email, size=8, step=10)
    center("-" * 30, size=8, step=10)
    left(f"Recu commande #{commande_id}", "Helvetica-Bold", 9)
    left(f"Date: {order['date_commande'][:16]}")
    left(f"Type: {order['type_commande']}  Statut: {order['statut']}")
    left(f"Client: {order['client_nom']}")
    if order.get("client_tel"):
        left(f"Tel client: {order['client_tel']}")
    if order.get("table_numero"):
        left(f"Table: {order['table_numero']}")
    if order.get("employe_nom"):
        left(f"Serveur: {order['employe_nom']}")
    center("-" * 30, size=8, step=10)
    for line in lines:
        total_line = line["prix_unitaire"] * line["quantite"] - line["remise"]
        left(f"{line['nom']} ({line['taille']})", "Helvetica-Bold", 8, 10)
        right(f"{line['quantite']} x {line['prix_unitaire']:.2f}", f"{total_line:.2f} MAD")
        if y < 70:
            pdf.showPage()
            y = height - 24
    center("-" * 30, size=8, step=10)
    total_ttc = order["montant_total"] + order["frais_livraison"]
    vat = vat_breakdown(total_ttc)
    right("Sous-total", f"{order['montant_total']:.2f} MAD")
    if order["frais_livraison"]:
        right("Livraison", f"{order['frais_livraison']:.2f} MAD")
    if order["remise_pct"]:
        right("Remise", f"{order['remise_pct']:.0f}%")
    right("HT", f"{vat['ht']:.2f} MAD")
    right("TVA 20%", f"{vat['tva']:.2f} MAD")
    right("TOTAL TTC", f"{vat['ttc']:.2f} MAD", "Helvetica-Bold", 10, 14)
    center("Merci et a bientot", "Helvetica-Bold", 9, 12)
    pdf.save()
    return path
