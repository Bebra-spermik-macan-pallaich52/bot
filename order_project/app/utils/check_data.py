"""Правила проверки заказа и совместимый функциональный интерфейс."""

import re


class CheckData:
    """Валидация без исправления или преобразования пользовательского ввода."""

    @staticmethod
    def is_valid_id(product_id: str) -> bool:
        """ID: от одной до четырёх различных букв английского алфавита A–Z."""
        if not isinstance(product_id, str):
            return False
        if re.fullmatch(r"[A-Z]{1,4}", product_id) is None:
            return False
        return len(set(product_id)) == len(product_id)

    @staticmethod
    def is_valid_quantity(quantity: str) -> bool:
        """Положительный int либо строка ASCII-цифр с ненулевым значением.

        Дополнительно к str принимаем int из JSON. bool и float запрещены.
        Ведущие нули разрешены; знаки, пробелы и дробная часть — нет.
        Проверка строки не ограничена максимальной длиной int-конвертации.
        """
        if isinstance(quantity, str):
            return re.fullmatch(r"0*[1-9][0-9]*", quantity) is not None
        if isinstance(quantity, bool):
            return False
        if isinstance(quantity, int):
            return quantity > 0
        return False

    @staticmethod
    def check_params(product_id: str, quantity: str) -> str:
        """Согласует результаты двух независимых проверок."""
        checks = (
            CheckData.is_valid_id(product_id),
            CheckData.is_valid_quantity(quantity),
        )
        return "Корректно" if all(checks) else "Некорректно"


# Оба способа импорта из задания используют одну реализацию.
is_valid_id = CheckData.is_valid_id
is_valid_quantity = CheckData.is_valid_quantity
check_params = CheckData.check_params
