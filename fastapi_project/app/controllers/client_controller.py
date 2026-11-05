from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session, select

from app.controllers.tarif_controller import TarifController
from app.controllers.telecom_common import commit
from app.models.client import Client, ClientBirthdayRead, ClientData, ClientUpdate, ClientWithTarif
from app.models.tarif import Tarif, TarifRead


class ClientController:
    @staticmethod
    def get(phone: str, session: Session) -> Client:
        client = session.get(Client, phone)
        if client is None:
            raise HTTPException(404, "Клиент не найден")
        return client

    @staticmethod
    def all(session: Session):
        return session.exec(select(Client).order_by(Client.number_phone)).all()

    @staticmethod
    def add(data: ClientData, session: Session):
        if session.get(Client, data.number_phone):
            raise HTTPException(409, "Клиент с таким номером телефона уже существует")
        if data.id_tarif is not None:
            TarifController.get(data.id_tarif, session)
        client = Client.model_validate(data)
        session.add(client)
        commit(session)
        session.refresh(client)
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
        new_phone = changes.get("number_phone", phone)
        if new_phone != phone and session.get(Client, new_phone):
            raise HTTPException(409, "Клиент с таким номером телефона уже существует")
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
