from app.entities import Client, ClientBirthdayRead, ClientUpdate, ClientWithTarif, Tarif, TarifData, TarifRead, TarifUpdate, TarifWithClientCount
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session
from sqlmodel import Session, func, select
from datetime import date
from decimal import Decimal
from sqlmodel import Session, select


def commit(session: Session) -> None:
    """Report uniqueness/FK conflicts, including concurrent changes, as HTTP 409."""
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "Конфликт данных: номер уже занят или запись связана с другими данными") from exc




class TarifController:
    @staticmethod
    def get(tarif_id: int, session: Session) -> Tarif:
        tarif = session.get(Tarif, tarif_id)
        if tarif is None:
            raise HTTPException(404, "Тариф не найден")
        return tarif

    @staticmethod
    def all(session: Session):
        return session.exec(select(Tarif).order_by(Tarif.id_tarif)).all()

    @staticmethod
    def add(data: TarifData, session: Session):
        tarif = Tarif.model_validate(data)
        session.add(tarif)
        commit(session)
        session.refresh(tarif)
        return tarif

    @staticmethod
    def update(tarif_id: int, data: TarifUpdate, session: Session):
        tarif = TarifController.get(tarif_id, session)
        tarif.sqlmodel_update(data.model_dump(exclude_unset=True))
        session.add(tarif)
        commit(session)
        session.refresh(tarif)
        return tarif

    @staticmethod
    def count(tarif_id: int, session: Session) -> int:
        TarifController.get(tarif_id, session)
        return session.exec(select(func.count(Client.number_phone)).where(Client.id_tarif == tarif_id)).one()

    @staticmethod
    def with_counts(session: Session):
        rows = session.exec(
            select(Tarif, func.count(Client.number_phone))
            .outerjoin(Client, Client.id_tarif == Tarif.id_tarif)
            .group_by(Tarif.id_tarif).order_by(Tarif.id_tarif)
        ).all()
        return [TarifWithClientCount(**tarif.model_dump(), client_count=count) for tarif, count in rows]

    @staticmethod
    def by_client(phone: str, session: Session):
        client = session.get(Client, phone)
        if client is None:
            raise HTTPException(404, "Клиент не найден")
        if client.id_tarif is None:
            raise HTTPException(404, "У клиента нет тарифа")
        return TarifController.get(client.id_tarif, session)

    @staticmethod
    def delete(tarif_id: int, session: Session):
        tarif = TarifController.get(tarif_id, session)
        if TarifController.count(tarif_id, session):
            raise HTTPException(409, "К тарифу подключены клиенты: сначала смените или отключите их тариф")
        session.delete(tarif)
        commit(session)





class ClientController:
    @staticmethod
    def get(phone: str, session: Session) -> Client:
        client = session.get(Client, phone)
        if client is None:
            raise HTTPException(404, "Клиент не найден")
        return client

    @staticmethod
    def by_prefix(phone: str, session: Session):
        return session.exec(select(Client).where(
            Client.number_phone.startswith(phone, autoescape=True)
        ).order_by(Client.number_phone)).all()

    @staticmethod
    def by_birthday(session: Session):
        clients = session.exec(select(Client).order_by(Client.date_birthday, Client.number_phone)).all()
        return [ClientBirthdayRead(
            full_name=" ".join(part for part in (c.lastname, c.firstname, c.patronymic_name) if part),
            date_birthday=c.date_birthday,
        ) for c in clients]

    @staticmethod
    def by_passport_year(year: int, session: Session):
        # "После года" excludes the whole specified year, including December 31.
        return session.exec(select(Client).where(
            Client.date_issue > date(year, 12, 31)
        ).order_by(Client.number_phone)).all()

    @staticmethod
    def with_tarif(session: Session, min_salary: Decimal | None = None):
        query = select(Client, Tarif).outerjoin(Tarif, Client.id_tarif == Tarif.id_tarif)
        if min_salary is not None:
            query = query.where(Tarif.salary > min_salary)
        rows = session.exec(query.order_by(Client.number_phone)).all()
        return [ClientWithTarif(**client.model_dump(), tarif=TarifRead.model_validate(tarif) if tarif else None)
                for client, tarif in rows]

    @staticmethod
    def update(phone: str, data: ClientUpdate, session: Session):
        client = ClientController.get(phone, session)
        changes = data.model_dump(exclude_unset=True)
        if changes.get("id_tarif") is not None:
            TarifController.get(changes["id_tarif"], session)
        client.sqlmodel_update(changes)
        session.add(client)
        commit(session)
        session.refresh(client)
        return client

    @staticmethod
    def delete(phone: str, session: Session):
        session.delete(ClientController.get(phone, session))
        commit(session)
