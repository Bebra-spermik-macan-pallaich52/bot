"""Границы, классы эквивалентности, попарные сочетания и исходные JSON."""

import pytest

from app.utils.check_data import CheckData


# Ожидаемые значения заданы вручную, независимо от проверяемых функций.
ID_CLASSES = [
    pytest.param("AB", True, id="valid"),
    pytest.param("", False, id="empty"),
    pytest.param("ABCDE", False, id="too-long"),
    pytest.param("AA", False, id="duplicate"),
    pytest.param("ab", False, id="lowercase"),
    pytest.param("АБ", False, id="cyrillic"),
    pytest.param("A1", False, id="digit"),
    pytest.param("A!", False, id="symbol"),
    pytest.param("A B", False, id="space"),
    pytest.param(None, False, id="null"),
    pytest.param(12, False, id="number"),
]

QUANTITY_CLASSES = [
    pytest.param("10", True, id="positive-string"),
    pytest.param(10, True, id="positive-int"),
    pytest.param("0", False, id="zero"),
    pytest.param("-1", False, id="negative"),
    pytest.param("1.5", False, id="decimal-string"),
    pytest.param(1.5, False, id="float"),
    pytest.param("", False, id="empty"),
    pytest.param("2t", False, id="text"),
    pytest.param(" 1 ", False, id="spaces"),
    pytest.param("+1", False, id="plus"),
    pytest.param("١", False, id="unicode-digit"),
    pytest.param(None, False, id="null"),
    pytest.param(True, False, id="bool"),
]


class TestCheckData:
    @pytest.mark.parametrize("product_id, expected", ID_CLASSES + [
        pytest.param("A", True, id="length-1"),
        pytest.param("ABC", True, id="length-3"),
        pytest.param("ABCD", True, id="length-4"),
        pytest.param("ABCA", False, id="duplicate-at-boundary"),
        pytest.param("1", False, id="one-digit"),
        pytest.param("1234", False, id="four-digits"),
        pytest.param("А", False, id="one-cyrillic"),
        pytest.param("АБВГ", False, id="four-cyrillic"),
        pytest.param("Ab", False, id="mixed-case"),
        pytest.param("AB\n", False, id="newline"),
        pytest.param("TRUE", True, id="uppercase-word"),
        pytest.param("None", False, id="mixed-case-word"),
        pytest.param(False, False, id="bool"),
        pytest.param([], False, id="list"),
    ])
    def test_is_valid_id(self, product_id, expected):
        actual = CheckData.is_valid_id(product_id)
        assert actual is expected

    @pytest.mark.parametrize("quantity, expected", QUANTITY_CLASSES + [
        pytest.param("1", True, id="minimum-string"),
        pytest.param(1, True, id="minimum-int"),
        pytest.param(0, False, id="zero-int"),
        pytest.param(-1, False, id="negative-int"),
        pytest.param("9999999999", True, id="large-string"),
        pytest.param(9999999999, True, id="large-int"),
        pytest.param("10000000000", True, id="no-upper-limit"),
        pytest.param("001", True, id="leading-zeros"),
        pytest.param("000", False, id="only-zeros"),
        pytest.param("1" * 5000, True, id="very-long-number"),
        pytest.param(1.0, False, id="integral-float"),
        pytest.param(-1.5, False, id="negative-float"),
        pytest.param("-1.5", False, id="negative-decimal-string"),
        pytest.param("1e3", False, id="exponent"),
        pytest.param("1_000", False, id="underscore"),
        pytest.param("1\n", False, id="newline"),
        pytest.param("None", False, id="none-word"),
        pytest.param("False", False, id="false-word"),
        pytest.param(False, False, id="false-bool"),
        pytest.param([], False, id="list"),
        pytest.param({}, False, id="dict"),
    ])
    def test_is_valid_quantity(self, quantity, expected):
        actual = CheckData.is_valid_quantity(quantity)
        assert actual is expected

    # Два фактора: полное декартово произведение выбранных классов
    # обеспечивает все пары (11 классов ID × 13 классов количества).
    @pytest.mark.parametrize("product_id, id_valid", ID_CLASSES)
    @pytest.mark.parametrize("quantity, quantity_valid", QUANTITY_CLASSES)
    def test_check_params_pairwise(self, product_id, id_valid, quantity, quantity_valid):
        expected = "Корректно" if id_valid and quantity_valid else "Некорректно"
        actual = CheckData.check_params(product_id, quantity)
        assert actual == expected


class TestProvidedJson:
    def test_is_valid_id(self, valid_id_case):
        assert CheckData.is_valid_id(valid_id_case["id"]) is valid_id_case["valid"]

    def test_is_valid_quantity(self, valid_quantity_case):
        assert CheckData.is_valid_quantity(valid_quantity_case["quantity"]) is valid_quantity_case["valid"]

    def test_check_params(self, check_params_case):
        assert CheckData.check_params(
            check_params_case["id"], check_params_case["quantity"]
        ) == check_params_case["status"]
