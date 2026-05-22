# PizzaExpress

Application bureau Python/Tkinter pour la gestion d'une pizzeria.

## Installation

```powershell
pip install -r pizza_express/requirements.txt
python run_pizza_express.py
```

## Compte demo

- Email: `admin@pizzaexpress.ma`
- Mot de passe: `Admin123!`

## Modules

- Connexion / inscription (bcrypt, validation mot de passe)
- Tableau de bord (ventes, top produits, tables, employes)
- Clients (fidelite, recherche)
- Commandes (sur place, emporter, livraison, détails extensibles via flèches, TVA)
- Menu (produits 3 tailles, composition liée au stock, allergenes, catégories)
- Stock (gestion des ingrédients, alertes RED/ORANGE, déduction automatique de 3.5% à la préparation)
- Employes (roles, soft delete)
- Tables & reservations (plan interactif avec codes couleurs : Vert=Libre, Rouge=Occupé, Orange=Réservé)
- Rapports CSV/PDF avec comparaison N-1
- Interface UI (thème moderne unifié, panier élargi pour une meilleure ergonomie)
- Tests (suite de tests unitaires pour la logique métier et les déclencheurs de base de données)

## Base de donnees

SQLite: `pizza_express/data/pizza_express.db`

Triggers: total commande, deduction stock, points fidelite.
