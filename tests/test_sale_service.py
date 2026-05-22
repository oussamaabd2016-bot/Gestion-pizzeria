import pytest

from app.extensions import db
from app.models import Encaissement, LigneVente, ModePaiement, Paiement, Produit, Vente
from app.services import CashService, SaleService
from app.services.calculation_service import money


def test_create_sale_is_atomic_and_snapshots_price(app, user):
    with app.app_context():
        CashService().open_cash(user, solde_initial="100.00")
        produit = Produit(nom_produit="Eclair", prix_vente=money("8.50"), disponibilite=True)
        db.session.add(produit)
        db.session.commit()

        vente = SaleService().create_sale(
            user,
            [{"id_produit": produit.id_produit, "quantite": 2}],
            [{"mode": ModePaiement.ESPECES.value, "montant_recu": "20.00"}],
        )

        ligne = LigneVente.query.filter_by(id_vente=vente.id_vente).one()
        paiement = Paiement.query.filter_by(id_vente=vente.id_vente).one()
        encaissement = Encaissement.query.filter_by(id_vente=vente.id_vente).one()

        assert vente.total_vente == money("17.00")
        assert ligne.prix_unitaire_snapshot == money("8.50")
        assert paiement.rendu_monnaie == money("3.00")
        assert encaissement.montant == money("17.00")

        produit.prix_vente = money("9.50")
        db.session.commit()
        assert LigneVente.query.filter_by(id_vente=vente.id_vente).one().prix_unitaire_snapshot == money("8.50")


def test_create_sale_rolls_back_when_payment_is_short(app, user):
    with app.app_context():
        CashService().open_cash(user)
        produit = Produit(nom_produit="Tarte", prix_vente=money("15.00"), disponibilite=True)
        db.session.add(produit)
        db.session.commit()

        with pytest.raises(ValueError):
            SaleService().create_sale(
                user,
                [{"id_produit": produit.id_produit, "quantite": 1}],
                [{"mode": ModePaiement.CARTE.value, "montant_recu": "10.00"}],
            )

        assert Vente.query.count() == 0
        assert LigneVente.query.count() == 0
        assert Paiement.query.count() == 0
        assert Encaissement.query.count() == 0
