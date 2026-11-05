# REST API: клиенты и тарифы

Реализация задания «Документация к API: Управление клиентами и тарифами», версия 1.0.
Используется существующий FastAPI-проект: SQLModel, PostgreSQL, контроллеры,
сессия на запрос и основное приложение `app.main:main_app`.

## Запуск

Самый простой вариант — `python3 scripts/start.py` (Windows: `py scripts/start.py`).
Он создаёт отдельную базу `telecom`, её пароль и запускает API в Docker.
Пошаговое описание — в [readme.md](readme.md). Ниже описан ручной запуск.

Нужны Python 3.10+ и работающий PostgreSQL. Команды выполняются из `fastapi_project`.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Создайте пустую базу `telecom` в PostgreSQL, впишите строку подключения
в `.env` (не добавляйте этот файл в Git):

```dotenv
DATABASE_URL="postgresql+psycopg://DB_USER:DB_PASSWORD@localhost:5432/telecom"
```

Замените пользователя и пароль своими значениями. Затем:

```bash
.venv/bin/python -m uvicorn app.main:main_app --reload
```

Для Windows используйте `py -m venv .venv`, `Copy-Item .env.example .env`
и `.\.venv\Scripts\python.exe` вместо `.venv/bin/python`.

Базовый путь — `/api/v1`, порт по умолчанию — `8000`.
Swagger UI — `/api/v1/docs`, ReDoc — `/api/v1/redoc`, OpenAPI — `/api/v1/openapi.json`.
Таблицы создаются при запуске через `SQLModel.metadata.create_all`; существующие
таблицы эта команда не изменяет. Для изменения схемы уже существующей БД нужны миграции.

## Структура

- `app/models/client.py`, `app/models/tarif.py`: таблицы и отдельные схемы запросов/ответов.
- `app/controllers/client_controller.py`, `app/controllers/tarif_controller.py`: SQL-запросы и операции с данными.
- `app/controllers/telecom_common.py`: откат транзакций при конфликте целостности.
- `app/api/v1/client_api_router.py`, `app/api/v1/tarif_api_router.py`: HTTP-маршруты.
- `tests/test_telecom.py`: проверки HTTP-контракта, фильтров, обновлений и связей.

`tarif.id_tarif` — целочисленный первичный ключ, создаётся автоматически.
`client.number_phone` — строковый первичный ключ;
`client.id_tarif` — внешний ключ на `tarif.id_tarif`.

В API используются имена из текстовой документации PDF: `firstname`,
`patronymic_name`, `pasport_serial`, `pasport_number`. В диаграмме имя обозначено
как `first_name`; для единого HTTP-контракта выбрано `firstname` из примеров API.
Серия и номер паспорта — строки, поэтому начальные нули сохраняются.
Даты имеют формат `YYYY-MM-DD`.

Телефон содержит 5–15 цифр с необязательным `+`, без пробелов и скобок.
`internet`, `count_minutes`, `count_sms` — неотрицательные целые числа.
`salary` хранится в БД как `NUMERIC(12, 2)` и возвращается JSON-числом;
в запросах принимается число или десятичная строка с максимум двумя знаками после точки.
Пустые имена, отрицательные значения, некорректные даты и неизвестные поля отклоняются с 422.

## Маршруты из задания

Все пути ниже указаны относительно `/api/v1`, без завершающего `/`.

| Метод | Путь | Результат |
| --- | --- | --- |
| GET | `/tarifs` | Все тарифы |
| GET | `/tarifs/by-client/{phone}` | Тариф клиента по номеру телефона |
| GET | `/tarifs/stats/client-count` | Список `{tarif_name, client_count}` |
| GET | `/tarifs/{id}/client-count` | `{tarif_id, count}` |
| PUT | `/tarifs/{id}` | Обновление переданных полей тарифа |
| POST | `/tarifs` | Создание тарифа, 201 |
| DELETE | `/tarifs/{id_tarif}` | Удаление тарифа, 204 без тела |
| GET | `/tarifs/with-client-count` | Все поля тарифов и `client_count` |
| GET | `/clients/search/phone?phone=%2B7` | Поиск по началу номера; поля `number_phone`, `lastname`, `firstname` |
| GET | `/clients/sorted-by-birthday` | Список `{full_name, date_birthday}` по возрастанию даты рождения |
| GET | `/clients/search/passport-year?year=2015` | Клиенты с паспортом, выданным начиная с 2016-01-01 |
| GET | `/clients/search/tarif-cost?minSalary=300` | Клиенты с тарифом **строго дороже** 300 |
| PUT | `/clients/{phone}` | Обновление переданных полей клиента |
| DELETE | `/clients/{phone}` | Удаление клиента, 204 без тела |
| PATCH | `/clients/tarif?phone=%2B79001234567&id_tarif=1` | Назначение/смена тарифа; `{message: "Тариф клиента успешно изменён"}` |

Дополнительно реализованы необходимые для наполнения и просмотра данных операции:

| Метод | Путь | Результат |
| --- | --- | --- |
| POST | `/clients` | Создать клиента, 201 |
| GET | `/clients` | Все клиенты |
| GET | `/clients/{phone}` | Клиент по номеру телефона |
| GET | `/clients/with-tarif` | Все клиенты с информацией о тарифе через SQL LEFT JOIN |

`GET /clients/with-tarif` и поиск по стоимости возвращают поля клиента
и вложенный объект `tarif`. У клиента без тарифа `tarif: null`.
Статистика строится через `LEFT JOIN` и `COUNT(client.number_phone)`:
тарифы без клиентов присутствуют с количеством `0`.

## Уточнения документации

- Опечатка `PATCH / /clients/tarif` исправлена на `/clients/tarif`.
  `phone` и `id_tarif` передаются как query-параметры, согласно примеру URL в PDF.
- Тариф удаляется по **id_tarif** из пути, согласно описанию параметра;
  упоминание номера телефона в заголовке пункта 1.7 противоречит этому маршруту.
- `PUT` меняет только переданные поля, как указано в PDF. Непереданные значения сохраняются;
  пустой объект оставляет запись без изменений.
- Клиента можно создать без тарифа: `id_tarif` допускает `null`.
  `PUT /clients/{phone}` с `{"id_tarif": null}` отключает тариф;
  `PATCH /clients/tarif` назначает существующий тариф.
- `patronymic_name` также допускает `null`. Другие поля нельзя обнулить через `PUT`.
- Номер телефона можно изменить через `PUT`, если новый номер свободен.
- Удаление тарифа, используемого клиентами, возвращает 409. Сначала смените
  или отключите тариф у этих клиентов. Внешний ключ защищает и от конкурентного удаления.
- Поиск «после года» исключает весь указанный год; цена сравнивается через `>`.
- Символ `+` в query-параметре нужно кодировать как `%2B`, иначе он может стать пробелом.
  Swagger и HTTP-клиенты с аргументом `params` делают это автоматически.

Коды ошибок: **404** — клиент или тариф не найден (в том числе отсутствует
назначенный тариф); **409** — занятый телефон или конфликт связей;
**422** — некорректные входные данные; **500** — внутренняя ошибка БД.
При ошибке транзакция откатывается, SQL и параметры подключения в ответ не попадают.

## Пример проверки через Swagger

1. Создайте тариф через `POST /tarifs`:

```json
{
  "tarif_name": "Новый тариф",
  "internet": 50,
  "count_minutes": 500,
  "count_sms": 100,
  "salary": 600
}
```

2. Создайте клиента через `POST /clients`. В `id_tarif` укажите **полученный**
   идентификатор (в примере — `1`):

```json
{
  "number_phone": "+79001234567",
  "id_tarif": 1,
  "lastname": "Иванов",
  "firstname": "Иван",
  "patronymic_name": "Иванович",
  "date_birthday": "1995-10-20",
  "pasport_serial": "0012",
  "pasport_number": "000123",
  "date_issue": "2016-01-01"
}
```

3. Проверьте `/clients/with-tarif`, поиск по цене `minSalary=500`,
   поиск по году `year=2015`, статистику и сортировку.
4. Измените клиента через `PUT /clients/+79001234567` с телом
   `{"lastname": "Петров"}`. Остальные поля сохранятся.
5. Удалите клиента, затем его тариф. Оба удаления вернут 204 без тела.

## Автоматические тесты

```bash
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m pytest tests -q
```

По умолчанию тесты используют временную SQLite в памяти с включёнными внешними ключами.
Для проверки на PostgreSQL создайте отдельную пустую БД, имя которой заканчивается
на `_test`, и задайте `TEST_DATABASE_URL`:

```bash
TEST_DATABASE_URL='postgresql+psycopg://DB_USER:DB_PASSWORD@localhost:5432/telecom_test' \
  .venv/bin/python -m pytest tests -q
```

На Windows PowerShell сначала задайте `$env:TEST_DATABASE_URL`, затем запустите pytest.
Пользователю тестовой БД нужно право создавать схемы. Каждый тест использует отдельную
схему со случайным именем, удаляемую после завершения. Рабочая `DATABASE_URL` из `.env`
не используется для тестов.

Проверяются маршруты задания, JOIN, нулевые счётчики, границы года и цены,
назначение/отключение тарифа, сохранение полей при обновлении, смена номера,
конфликты, ошибки валидации, Swagger/OpenAPI и отсутствие лишних маршрутов и таблиц.
