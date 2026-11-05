# REST API: клиенты и тарифы

Задание выполнено на FastAPI, SQLModel и PostgreSQL.
В API две сущности: `Client` и `Tarif`. Таблицы — `client` и `tarif`.

## Запуск в VS Code

Откройте папку `fastapi_project` в VS Code.

1. В PostgreSQL (например, через Query Tool в pgAdmin) создайте базу:

```sql
CREATE DATABASE telecom;
```

2. В терминале VS Code установите зависимости:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. Скопируйте `.env.example` в `.env`, если своего `.env` ещё нет.
   Укажите в `.env` своего пользователя и пароль PostgreSQL:

```dotenv
DATABASE_URL="postgresql+psycopg://DB_USER:DB_PASSWORD@localhost:5432/telecom"
```

Замените `DB_USER` и `DB_PASSWORD` своими значениями. Если пароль содержит
спецсимволы, кодируйте их в URL (например, `@` как `%40`).

4. Запустите API в терминале VS Code:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:main_app --reload
```

Откройте Swagger: `http://127.0.0.1:8000/api/v1/docs`.
Адрес работает на компьютере, где запущено приложение; терминал должен оставаться открытым.
Остановка — Ctrl+C.

Таблицы создаются автоматически при запуске. Сначала добавьте тариф через
`POST /tarifs`, затем клиента через `POST /clients`, указав полученный `id_tarif`.

На Linux/macOS используйте `python3` для создания окружения и
`.venv/bin/python` для установки зависимостей и запуска.

Все маршруты задания, примеры JSON и команды тестирования — в
[TELECOM_API.md](TELECOM_API.md).
