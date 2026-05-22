import pytest

from app.services.calculation_service import calculate_change, calculate_line_total, calculate_sale_total, money


def test_line_total_uses_quantity_and_money_rounding():
    assert calculate_line_total("2.335", 3) == money("7.02")


def test_sale_total_sums_lines():
    total = calculate_sale_total(
        [
            {"prix": "12.50", "quantite": 2},
            {"prix": "3.00", "quantite": 1},
        ]
    )
    assert total == money("28.00")


def test_change_rejects_insufficient_payment():
    with pytest.raises(ValueError):
        calculate_change("20.00", [{"montant_recu": "19.99"}])
