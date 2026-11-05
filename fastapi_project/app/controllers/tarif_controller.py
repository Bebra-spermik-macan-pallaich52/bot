from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.controllers.telecom_common import commit
from app.models.client import Client
from app.models.tarif import Tarif, TarifData, TarifUpdate, TarifWithClientCount


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
