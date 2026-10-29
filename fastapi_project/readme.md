# Практика: FastAPI и PostgreSQL

Работа выполнена на основе выданного `project.zip` и последовательности из PDF.
Python 3.10 или новее. Используются FastAPI, Uvicorn, SQLModel, PostgreSQL и Argon2.

## Установка и запуск на Windows

Откройте терминал в папке `fastapi_project` (рядом с `requirements.txt`).

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

В PostgreSQL через pgAdmin или psql создайте базу:

```sql
CREATE DATABASE practice_api;
```

Скопируйте `.env.example` в `.env` и укажите свои данные подключения:

```powershell
Copy-Item .env.example .env
```

```dotenv
DATABASE_URL="postgresql+psycopg://DB_USER:DB_PASSWORD@localhost:5432/practice_api"
```

Замените `DB_USER` и `DB_PASSWORD` на пользователя и пароль PostgreSQL,
при необходимости измените хост, порт и имя БД. Спецсимволы в пароле URL
нужно кодировать (например, `@` как `%40`). `.env` исключён из Git.

Запустите приложение:

```powershell
.\.venv\Scripts\python.exe -m app.main
```

Либо с автоматической перезагрузкой при разработке:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:main_app --reload
```

При занятом порте добавьте `--port 8001` к команде Uvicorn.
Остановка — Ctrl+C. На Linux/macOS создайте окружение командой
`python3 -m venv .venv`, далее используйте `.venv/bin/python`.

Таблицы `roles` и `profiles` создаются при запуске, подключения освобождаются
при остановке. PostgreSQL должен быть запущен заранее.

## Документация и порядок проверки

При запуске `main_app` документация доступна в браузере на локальном порту 8000:

- Swagger UI: `/api/v1/docs`;
- ReDoc: `/api/v1/redoc`;
- OpenAPI: `/api/v1/openapi.json`.

Сначала создайте роль через `POST /api/v1/roles/`:

```json
{"name_role": "student"}
```

Затем создайте профиль через `POST /api/v1/profiles/`.
В `role_id` укажите **полученный `id_role`**, а не произвольное число:

```json
{
  "first_name": "Иван",
  "second_name": "Петров",
  "patronymic": null,
  "role_id": 1,
  "email": "ivan@example.com",
  "password": "Example-pass-1"
}
```

`POST /api/v1/profiles/authenticate` принимает `email` и `password` в JSON.
При успехе возвращается профиль, при неверных данных — 401.
Пароль хранится как Argon2-хеш и не включается в ответы API.
`PUT` обновляет профиль целиком: передайте все нужные поля и пароль;
если пароль остался прежним, его хеш сохраняется, иначе создаётся новый.

## Выполненные методы

Все маршруты ниже имеют префикс `/api/v1`.

| Метод контроллера ролей | HTTP-маршрут |
| --- | --- |
| `add_role` | `POST /roles/` |
| `get_role_by_id` | `GET /roles/{role_id}` |
| `get_all_roles` | `GET /roles/` |
| `update_role` | `PUT /roles/{role_id}` |
| `delete_role` | `DELETE /roles/{role_id}` |
| `get_role_by_name` | `GET /roles/by-name/{name_role}` |
| `count_roles` | `GET /roles/count` |
| `get_roles_paginated` | `GET /roles/paginated?offset=0&limit=10` |
| `search_roles` | `GET /roles/search?substring=stu` |
| `get_roles_sorted` | `GET /roles/sorted?descending=false` |
| `delete_all_roles` | `DELETE /roles/` |

| Метод контроллера профилей | HTTP-маршрут |
| --- | --- |
| `add_profile` | `POST /profiles/` |
| `get_profile_by_id` | `GET /profiles/{profile_id}` |
| `get_all_profiles` | `GET /profiles/` |
| `update_profile` | `PUT /profiles/{profile_id}` |
| `delete_profile` | `DELETE /profiles/{profile_id}` |
| `authenticate` | `POST /profiles/authenticate` |
| `get_profiles_by_role` | `GET /profiles/by-role/{role_id}` |

Сессия передаётся в контроллер через `Depends(get_session)` и закрывается
после запроса. Ошибки транзакции приводят к откату. Дубликат имени роли
проверяется при добавлении и обновлении (кроме самой изменяемой роли).
Дубликаты возвращают 409, отсутствующие записи — 404, неверный формат
запроса — 422, нарушение целостности — 400, ошибки БД — 500.
Роль с существующими профилями удалить нельзя: сначала удалите или
переназначьте профили. Массовое удаление возвращает число удалённых ролей.

## Уточнения к примерам PDF

- Модели импортируются до `create_all`, чтобы SQLModel создал обе таблицы.
- `security.py` содержит `hash_password` и `verify_password`; `utils.py`
  сохраняет старые имена функций из архива.
- `main_app` монтирует `app_v1` по `/api/v1`. Пути документации внутри
  дочернего приложения относительные, поэтому префикс не дублируется.
- Lifespan основного приложения управляет БД: FastAPI не запускает lifespan
  смонтированного приложения автоматически. Для отдельного запуска
  `uvicorn app.main:app_v1 --reload` тоже поддерживается lifespan;
  в этом режиме пути идут без `/api/v1`, документация находится на `/docs`.

Проверено с настоящим PostgreSQL: все 18 операций, 63 HTTP-проверки,
дубликаты, отсутствующие записи, внешние ключи, пагинация, сортировка,
поиск, массовое удаление, хеширование и изменение пароля, Swagger и OpenAPI.
