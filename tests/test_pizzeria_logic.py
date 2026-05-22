import pytest
import os
from pizza_express.database.db import get_db
from pizza_express.logic.business import compute_order_totals, delivery_fee, vat_breakdown

def test_vat_breakdown():
    """Vérifie l'extraction de la TVA à 20% d'un prix TTC."""
    result = vat_breakdown(120.0) # 120 TTC -> 100 HT + 20 TVA
    assert result["ht"] == 100.0
    assert result["tva"] == 20.0
    assert result["ttc"] == 120.0

def test_delivery_fee_logic():
    """Vérifie que les frais de livraison s'appliquent correctement selon le type et le montant."""
    # Sur place : toujours 0
    assert delivery_fee(50.0, "SUR_PLACE") == 0.0
    # Livraison : dépend du seuil configuré
    # Si montant élevé, les frais sont offerts (0.0)
    assert delivery_fee(500.0, "LIVRAISON") == 0.0

def test_order_total_trigger():
    """Vérifie que le déclencheur SQL met à jour le montant total de la commande automatiquement."""
    db = get_db()
    with db.cursor() as cur:
        # Créer une commande vide
        cur.execute("INSERT INTO COMMANDE (type_commande, statut) VALUES ('EMPORTER', 'EN_ATTENTE')")
        cmd_id = cur.lastrowid
        
        # Ajouter une ligne de commande (quantité 2 x 50 MAD)
        # On utilise le produit 1 issu des données de démonstration
        cur.execute("""INSERT INTO LIGNE_COMMANDE (id_commande, id_produit, taille, quantite, prix_unitaire) 
                       VALUES (?, 1, 'Medium', 2, 50.0)""", (cmd_id,))
        
        cur.execute("SELECT montant_total FROM COMMANDE WHERE id_commande=?", (cmd_id,))
        total = cur.fetchone()["montant_total"]
        assert total == 100.0

def test_stock_reduction_3_5_percent():
    """Vérifie le déclencheur de réduction de stock de 3.5% au passage en préparation."""
    db = get_db()
    with db.cursor() as cur:
        # Configuration d'un produit et d'un ingrédient de test
        cur.execute("INSERT OR IGNORE INTO CATEGORIE (nom) VALUES ('TestCat')")
        cur.execute("SELECT id_categorie FROM CATEGORIE WHERE nom='TestCat'")
        cat_id = cur.fetchone()[0]
        
        cur.execute("""INSERT INTO PRODUIT (nom, prix_small, prix_medium, prix_large, id_categorie) 
                       VALUES ('Pizza Test', 10, 20, 30, ?)""", (cat_id,))
        pid = cur.lastrowid
        
        # Stock initial à 100.0
        cur.execute("""INSERT INTO INGREDIENT (nom, stock_actuel, stock_min, prix_unitaire) 
                       VALUES ('Ingred Test', 100.0, 10, 5)""")
        ing_id = cur.lastrowid
        
        cur.execute("INSERT INTO COMPOSITION (id_produit, id_ingredient, quantite_requise) VALUES (?, ?, 0.5)", (pid, ing_id))
        
        # Créer commande en attente
        cur.execute("""INSERT INTO COMMANDE (type_commande, statut, montant_total, date_commande) 
                       VALUES ('SUR_PLACE', 'EN_ATTENTE', 20, datetime('now'))""")
        oid = cur.lastrowid
        cur.execute("INSERT INTO LIGNE_COMMANDE (id_commande, id_produit, taille, quantite, prix_unitaire) VALUES (?, ?, 'Medium', 1, 20)", (oid, pid))
        
        # Changement de statut vers 'EN_PREPARATION' déclenche la réduction proportionnelle
        cur.execute("UPDATE COMMANDE SET statut='EN_PREPARATION' WHERE id_commande=?", (oid,))
        
        cur.execute("SELECT stock_actuel FROM INGREDIENT WHERE id_ingredient=?", (ing_id,))
        stock_final = cur.fetchone()["stock_actuel"]
        
        # Calcul attendu : 100 * 0.965 = 96.5
        assert round(stock_final, 2) == 96.5

def test_loyalty_points_trigger():
    """Vérifie que les points de fidélité sont crédités correctement lors de la livraison."""
    db = get_db()
    with db.cursor() as cur:
        cur.execute("INSERT INTO CLIENT (nom, points_fidelite) VALUES ('Test Client', 0)")
        cid = cur.lastrowid
        cur.execute("INSERT INTO COMMANDE (id_client, type_commande, statut, montant_total) VALUES (?, 'LIVRAISON', 'PRETE', 200)", (cid,))
        oid = cur.lastrowid
        
        # Passage au statut LIVREE
        cur.execute("UPDATE COMMANDE SET statut='LIVREE' WHERE id_commande=?", (oid,))
        
        cur.execute("SELECT points_fidelite FROM CLIENT WHERE id_client=?", (cid,))
        pts = cur.fetchone()["points_fidelite"]
        # Règle : 1 point par tranche de 10 MAD -> 200 / 10 = 20 points
        assert pts == 20