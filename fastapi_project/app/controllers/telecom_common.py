from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session


def commit(session: Session) -> None:
    """Report uniqueness/FK conflicts, including concurrent changes, as HTTP 409."""
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "Конфликт данных: номер уже занят или запись связана с другими данными") from exc
