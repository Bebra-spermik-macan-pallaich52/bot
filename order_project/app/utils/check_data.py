"""Проверка идентификатора и количества товара без изменения входных данных."""


def is_valid_id(product_id: str) -> bool:
    """Допускаются от 1 до 4 уникальных заглавных латинских букв."""
    return (
        isinstance(product_id, str)
        and 1 <= len(product_id) <= 4
        and all("A" <= char <= "Z" for char in product_id)
        and len(set(product_id)) == len(product_id)
    )


def is_valid_quantity(quantity: str) -> bool:
    """Принимает строку из ASCII-цифр или int > 0; bool и float запрещены.

    Аннотация str соответствует заданию; int поддерживается для JSON-кейсов.
    Пробелы, знаки и десятичная точка не допускаются. Ведущие нули допустимы.
    Верхняя граница количества в задании не установлена.
    """
    if isinstance(quantity, bool):
        return False
    if isinstance(quantity, int):
        return quantity > 0
    if not isinstance(quantity, str) or not quantity:
        return False
    # Не преобразуем в int: длинный корректный ввод не вызовет ValueError
    # из-за ограничения Python на число цифр при преобразовании строки.
    return all("0" <= char <= "9" for char in quantity) and any(
        char != "0" for char in quantity
    )


def check_params(product_id: str, quantity: str) -> str:
    """Возвращает «Корректно», только если оба параметра допустимы."""
    if is_valid_id(product_id) and is_valid_quantity(quantity):
        return "Корректно"
    return "Некорректно"


class CheckData:
    """Интерфейс со статическими методами из методички (без дублирования логики)."""

    is_valid_id = staticmethod(is_valid_id)
    is_valid_quantity = staticmethod(is_valid_quantity)
    check_params = staticmethod(check_params)
