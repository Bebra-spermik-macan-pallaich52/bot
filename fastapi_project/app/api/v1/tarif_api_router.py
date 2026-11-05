from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response
from sqlmodel import Session

from app.controllers.tarif_controller import TarifController as Tarifs
from app.db.session import get_session
from app.models.tarif import TarifClientCount, TarifCount, TarifData, TarifRead, TarifUpdate, TarifWithClientCount

router = APIRouter(prefix="/tarifs", tags=["Tarif"])
SessionDep = Annotated[Session, Depends(get_session)]
TarifId = Annotated[int, Path(ge=1)]


@router.get("", response_model=list[TarifRead], summary="Список тарифов")
def list_tarifs(session: SessionDep):
    return Tarifs.all(session)


@router.post("", response_model=TarifRead, status_code=201, summary="Создать тариф")
def create_tarif(data: TarifData, session: SessionDep):
    return Tarifs.add(data, session)


@router.get("/by-client/{phone}", response_model=TarifRead, summary="Тариф клиента по номеру телефона")
def tarif_by_client(phone: str, session: SessionDep):
    return Tarifs.by_client(phone, session)


@router.get("/stats/client-count", response_model=list[TarifClientCount], summary="Количество клиентов на каждом тарифе")
def tarif_stats(session: SessionDep):
    return [TarifClientCount(tarif_name=t.tarif_name, client_count=t.client_count) for t in Tarifs.with_counts(session)]


@router.get("/with-client-count", response_model=list[TarifWithClientCount], summary="Тарифы с количеством клиентов")
def tarifs_with_count(session: SessionDep):
    return Tarifs.with_counts(session)


@router.get("/{id}/client-count", response_model=TarifCount, summary="Количество клиентов на заданном тарифе")
def tarif_count(id: TarifId, session: SessionDep):
    return TarifCount(tarif_id=id, count=Tarifs.count(id, session))


@router.put("/{id}", response_model=TarifRead, summary="Обновить указанные поля тарифа")
def update_tarif(id: TarifId, data: TarifUpdate, session: SessionDep):
    return Tarifs.update(id, data, session)


@router.delete("/{id_tarif}", status_code=204, summary="Удалить тариф без подключённых клиентов")
def delete_tarif(id_tarif: TarifId, session: SessionDep):
    Tarifs.delete(id_tarif, session)
    return Response(status_code=204)
