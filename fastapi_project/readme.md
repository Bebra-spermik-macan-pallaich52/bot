# REST API: клиенты и тарифы

Учебное API по заданию Client / Tarif. В Swagger доступны только клиенты и тарифы.
Отдельная PostgreSQL-база `telecom` содержит таблицы `client` и `tarif`.

## Быстрый запуск с новой базой

Установите и запустите Docker Desktop (или Docker Engine с Compose v2 на Linux).
Также нужен Python 3.10+. Из корня репозитория:

```powershell
cd fastapi_project
py scripts/start.py
```

На Linux/macOS вместо `py` используйте `python3`:

```bash
python3 scripts/start.py
```

Скрипт автоматически:

1. Создаёт случайный пароль в локальном `.env.docker`, если файла ещё нет.
2. Собирает образ API и запускает отдельную PostgreSQL 17 с базой `telecom`.
3. Создаёт таблицы `client` и `tarif` через SQLModel.
4. Ждёт готовности БД и API и проверяет HTTP-ответы.

Откройте Swagger на своём компьютере: `http://127.0.0.1:8000/api/v1/docs`.
Создайте тариф через `POST /tarifs`, затем клиента через `POST /clients`.
База создаётся пустой. Python-зависимости API устанавливаются внутри контейнера.
Если порт занят, используйте `py scripts/start.py --port 8001` и порт 8001 в адресе.

Пароль и данные сохраняются между запусками: повторный запуск той же команды
не пересоздаёт базу. `.env.docker` исключён из Git и Docker-образа.
PostgreSQL доступен только API внутри сети Compose; API публикуется на локальном интерфейсе.

Просмотр состояния и логов (из `fastapi_project`):

```bash
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs --tail=50 api
```

Остановка с сохранением данных:

```bash
docker compose --env-file .env.docker down
```

Не удаляйте `.env.docker` при существующей базе: пароль в ней уже установлен.
Не добавляйте `-v` к `down`, если хотите сохранить данные в Docker volume.

## Разработка без Docker

Создайте отдельную БД в своём PostgreSQL:

```sql
CREATE DATABASE telecom;
```

Создайте venv, установите `requirements.txt`, скопируйте `.env.example` в `.env`
и укажите свою строку `DATABASE_URL`. Затем из `fastapi_project` запустите:

```bash
python -m uvicorn app.main:main_app --reload
```

Подробные команды, все маршруты, JSON-примеры и тестирование — в
[TELECOM_API.md](TELECOM_API.md).

## Облачная среда разработки

Используйте `python3 scripts/start.py --cloud`: override `compose.cloud.yaml`
передаёт системные CA-сертификаты на этапе сборки. Проверка TLS остаётся включённой.
Для нового экземпляра среды повторите запуск: работающие процессы не являются
частью снимка. Для облачной настройки используйте существующий checkout,
отдельный Git worktree не нужен.
