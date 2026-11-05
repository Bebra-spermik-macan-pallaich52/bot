from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlmodel import Session

from app.controllers.client_controller import ClientController as Clients
from app.db.session import get_session
from app.models.client import ClientBirthdayRead, ClientData, ClientPhoneRead, ClientUpdate, ClientWithTarif, TarifAssignmentResult

router = APIRouter(prefix="/clients", tags=["Client"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("", response_model=list[ClientData], summary="Список клиентов")
def list_clients(session: SessionDep):
    return Clients.all(session)


@router.post("", response_model=ClientData, status_code=201, summary="Создать клиента")
def create_client(data: ClientData, session: SessionDep):
    return Clients.add(data, session)


@router.get("/search/phone", response_model=list[ClientPhoneRead], summary="Поиск по началу номера телефона")
def clients_by_phone(session: SessionDep, phone: str = Query(min_length=1, max_length=16, pattern=r"^\+?[0-9]+$")):
    return Clients.by_prefix(phone, session)


@router.get("/sorted-by-birthday", response_model=list[ClientBirthdayRead], summary="ФИО и даты рождения по возрастанию")
def clients_by_birthday(session: SessionDep):
    return Clients.by_birthday(session)


@router.get("/search/passport-year", response_model=list[ClientData], summary="Паспорт выдан после заданного года")
def clients_by_passport_year(session: SessionDep, year: int = Query(ge=1, le=9999)):
    return Clients.by_passport_year(year, session)


@router.get("/search/tarif-cost", response_model=list[ClientWithTarif], summary="Стоимость тарифа строго выше указанной суммы")
def clients_by_tarif_cost(session: SessionDep, minSalary: Decimal = Query(ge=0, max_digits=12, decimal_places=2)):
    return Clients.with_tarif(session, minSalary)


@router.get("/with-tarif", response_model=list[ClientWithTarif], summary="Клиенты с тарифами через JOIN")
def clients_with_tarif(session: SessionDep):
    return Clients.with_tarif(session)


@router.patch("/tarif", response_model=TarifAssignmentResult, summary="Назначить или сменить тариф клиента")
def assign_tarif(session: SessionDep, phone: str = Query(min_length=1), id_tarif: int = Query(ge=1)):
    Clients.update(phone, ClientUpdate(id_tarif=id_tarif), session)
    return TarifAssignmentResult(message="Тариф клиента успешно изменён")


@router.get("/{phone}", response_model=ClientData, summary="Клиент по номеру телефона")
def get_client(phone: str, session: SessionDep):
    return Clients.get(phone, session)


@router.put("/{phone}", response_model=ClientData, summary="Обновить указанные поля клиента")
def update_client(phone: str, data: ClientUpdate, session: SessionDep):
    return Clients.update(phone, data, session)


@router.delete("/{phone}", status_code=204, summary="Удалить клиента по номеру телефона")
def delete_client(phone: str, session: SessionDep):
    Clients.delete(phone, session)
    return Response(status_code=204)
