"""Запуск из корня проекта: python -m app.main."""

from app.utils.check_data import check_params


def main() -> None:
    try:
        product_id = input("Идентификатор товара: ")
        quantity = input("Количество товара: ")
    except (EOFError, KeyboardInterrupt):
        print("\nВвод отменён.")
        return
    print(check_params(product_id, quantity))


if __name__ == "__main__":
    main()
