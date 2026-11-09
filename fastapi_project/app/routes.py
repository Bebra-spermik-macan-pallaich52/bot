from typing import Annotated
from fastapi import APIRouter, Depends, Path, Response
from sqlmodel import Session
from app.operations import TarifController as Tarifs
from app.database import get_session
from app.entities import TarifClientCount, TarifCount, TarifData, TarifRead, TarifUpdate, TarifWithClientCount
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, Response
from app.operations import ClientController as Clients
from app.entities import ClientBirthdayRead, ClientData, ClientPhoneRead, ClientUpdate, ClientWithTarif, TarifAssignmentResult


tarif_router = APIRouter(prefix="/tarifs", tags=["Tarif"])
SessionDep = Annotated[Session, Depends(get_session)]
TarifId = Annotated[int, Path(ge=1)]


@tarif_router.get("", response_model=list[TarifRead], summary="Список тарифов")
def list_tarifs(session: SessionDep):
    return Tarifs.all(session)


@tarif_router.post("", response_model=TarifRead, status_code=201, summary="Создать тариф")
def create_tarif(data: TarifData, session: SessionDep):
    return Tarifs.add(data, session)


@tarif_router.get("/by-client/{phone}", response_model=TarifRead, summary="Тариф клиента по номеру телефона")
def tarif_by_client(phone: str, session: SessionDep):
    return Tarifs.by_client(phone, session)


@tarif_router.get("/stats/client-count", response_model=list[TarifClientCount], summary="Количество клиентов на каждом тарифе")
def tarif_stats(session: SessionDep):
    return [TarifClientCount(tarif_name=t.tarif_name, client_count=t.client_count) for t in Tarifs.with_counts(session)]


@tarif_router.get("/with-client-count", response_model=list[TarifWithClientCount], summary="Тарифы с количеством клиентов")
def tarifs_with_count(session: SessionDep):
    return Tarifs.with_counts(session)


@tarif_router.get("/{id}/client-count", response_model=TarifCount, summary="Количество клиентов на заданном тарифе")
def tarif_count(id: TarifId, session: SessionDep):
    return TarifCount(tarif_id=id, count=Tarifs.count(id, session))


@tarif_router.put("/{id}", response_model=TarifRead, summary="Обновить указанные поля тарифа")
def update_tarif(id: TarifId, data: TarifUpdate, session: SessionDep):
    return Tarifs.update(id, data, session)


@tarif_router.delete("/{id_tarif}", status_code=204, summary="Удалить тариф без подключённых клиентов")
def delete_tarif(id_tarif: TarifId, session: SessionDep):
    Tarifs.delete(id_tarif, session)
    return Response(status_code=204)




client_router = APIRouter(prefix="/clients", tags=["Client"])
SessionDep = Annotated[Session, Depends(get_session)]


@client_router.get("/search/phone", response_model=list[ClientPhoneRead], summary="Поиск по началу номера телефона")
def clients_by_phone(session: SessionDep, phone: str = Query(min_length=1, max_length=16, examples=["+7"], pattern=r"^\+?[0-9]+$")):
    return Clients.by_prefix(phone, session)


@client_router.get("/sorted-by-birthday", response_model=list[ClientBirthdayRead], summary="ФИО и даты рождения по возрастанию")
def clients_by_birthday(session: SessionDep):
    return Clients.by_birthday(session)


@client_router.get("/search/passport-year", response_model=list[ClientData], summary="Паспорт выдан после заданного года")
def clients_by_passport_year(session: SessionDep, year: int = Query(ge=1, le=9999)):
    return Clients.by_passport_year(year, session)


@client_router.get("/search/tarif-cost", response_model=list[ClientWithTarif], summary="Стоимость тарифа строго выше указанной суммы")
def clients_by_tarif_cost(session: SessionDep, minSalary: Decimal = Query(ge=0, max_digits=12, decimal_places=2)):
    return Clients.with_tarif(session, minSalary)


@client_router.get("/with-tarif", response_model=list[ClientWithTarif], summary="Клиенты с тарифами через JOIN")
def clients_with_tarif(session: SessionDep):
    return Clients.with_tarif(session)


@client_router.patch("/tarif", response_model=TarifAssignmentResult, summary="Назначить или сменить тариф клиента")
def assign_tarif(session: SessionDep, phone: str = Query(min_length=1), id_tarif: int = Query(ge=1)):
    Clients.update(phone, ClientUpdate(id_tarif=id_tarif), session)
    return TarifAssignmentResult(message="Тариф клиента успешно изменён")


@client_router.put("/{phone}", response_model=ClientData, summary="Обновить указанные поля клиента")
def update_client(phone: str, data: ClientUpdate, session: SessionDep):
    return Clients.update(phone, data, session)


@client_router.delete("/{phone}", status_code=204, summary="Удалить клиента по номеру телефона")
def delete_client(phone: str, session: SessionDep):
    Clients.delete(phone, session)
    return Response(status_code=204)
