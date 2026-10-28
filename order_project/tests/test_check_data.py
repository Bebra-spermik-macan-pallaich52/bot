"""Три основных параметризованных теста, всего 44 случая."""
import json
from pathlib import Path

import pytest
from app.utils.check_data import CheckData


def read_cases(name, fields):
    path = Path(__file__).parent / "data" / f"{name}_test_cases.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [tuple(row[field] for field in fields) for row in rows]


# Исходные JSON неизменны; ниже добавлены собственные представители классов.
ID_CASES = read_cases("is_valid_id", ("id", "valid")) + [
    ("", False), ("WXYZ", True), ("KLMNO", False), ("R7", False),
    ("ЖЮ", False), ("T U", False), (42, False),
]
QUANTITY_CASES = read_cases("is_valid_quantity", ("quantity", "valid")) + [
    (0, False), ("1", True), ("0", False), ("9999999999", True),
    ("0008", True), ("", False), ("7kg", False), ("8\t", False),
    (False, False), ("2.75", False),
]
ORDER_CASES = read_cases("check_params", ("id", "quantity", "status")) + [
    ("QQ", "-6", "Некорректно"),
    ("R", "0008", "Корректно"),
    ("WXYZ", "9999999999", "Корректно"),
    ("KLMNO", "24", "Некорректно"),
    ("T U", "7kg", "Некорректно"),
]


class TestCheckData:
    @pytest.mark.parametrize("product_id, expected", ID_CASES)
    def test_is_valid_id(self, product_id, expected):
        assert CheckData.is_valid_id(product_id) is expected

    @pytest.mark.parametrize("quantity, expected", QUANTITY_CASES)
    def test_is_valid_quantity(self, quantity, expected):
        assert CheckData.is_valid_quantity(quantity) is expected

    @pytest.mark.parametrize("product_id, quantity, expected", ORDER_CASES)
    def test_check_params(self, product_id, quantity, expected):
        # Все пары валидности: да/да, да/нет, нет/да, нет/нет.
        assert CheckData.check_params(product_id, quantity) == expected
