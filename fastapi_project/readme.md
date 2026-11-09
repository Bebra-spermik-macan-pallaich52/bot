# Клиенты и тарифы

FastAPI + PostgreSQL. Только задание из PDF: 8 операций с тарифами и 8 с клиентами.

## Запуск в VS Code (Windows)

1. Откройте папку `fastapi_project` в VS Code. В PostgreSQL через pgAdmin создайте базу:

```sql
CREATE DATABASE telecom;
```

2. В терминале VS Code:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. Рядом с `requirements.txt` создайте файл **`.env`** (не `.env.txt`).
   Скопируйте в него строку из `.env.example` и замените пользователя и пароль:

```dotenv
DATABASE_URL="postgresql+psycopg://DB_USER:DB_PASSWORD@localhost:5432/telecom"
```

`DB_USER` и `DB_PASSWORD` — ваши данные PostgreSQL. Символ `@` в пароле
записывается как `%40`, `#` как `%23`, `%` как `%25`. Не публикуйте `.env`.

4. Запустите:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:main_app --reload
```

После `Application startup complete` откройте:
**http://127.0.0.1:8000/api/v1/docs**.
Терминал должен оставаться открытым. Остановка — Ctrl+C.

Таблицы `client` и `tarif` создаются автоматически. Для заполнения клиентов
выполните `sql/example_data.sql` через Query Tool в базе `telecom`.
В задании нет POST для создания клиента, поэтому такой маршрут не добавлен.
Скрипт с учебными данными можно выполнить повторно: он не перезаписывает клиентов.

GET-запросы только читают данные. Номер телефона — ключ клиента:
он указывается в пути запроса и не изменяется при обновлении остальных полей.
В Swagger `Example Value` — пример, `Response body` после Execute — ответ базы.

На Linux/macOS: `python3` вместо `py`, `.venv/bin/python` вместо Windows-пути.

Описание соответствия заданию и тестов: [TELECOM_API.md](TELECOM_API.md).
