"""Параметризованные фикстуры из исходных JSON преподавателя."""

import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent / "data"


def load_cases(filename):
    with (DATA_DIR / filename).open(encoding="utf-8") as file:
        rows = json.load(file)
    return [pytest.param(row, id=f"json-{i + 1}") for i, row in enumerate(rows)]


@pytest.fixture(params=load_cases("is_valid_id_test_cases.json"))
def valid_id_case(request):
    return request.param


@pytest.fixture(params=load_cases("is_valid_quantity_test_cases.json"))
def valid_quantity_case(request):
    return request.param


@pytest.fixture(params=load_cases("check_params_test_cases.json"))
def check_params_case(request):
    return request.param
