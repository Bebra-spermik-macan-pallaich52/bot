from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from app.db.session import get_session
from app.controllers.role_controller import RoleController as Roles
from app.models.role import Role, RoleData

router = APIRouter(prefix="/roles", tags=["Roles"])


@router.get("/", response_model=list[Role])
def get_all_roles(session: Session = Depends(get_session)):
    return Roles.get_all_roles(session)


@router.post("/", response_model=Role, status_code=201)
def add_role(role: RoleData, session: Session = Depends(get_session)):
    return Roles.add_role(Role.model_validate(role), session)


@router.get("/count", response_model=int)
def count_roles(session: Session = Depends(get_session)):
    return Roles.count_roles(session)


@router.get("/by-name/{name_role}", response_model=Role)
def get_role_by_name(name_role: str, session: Session = Depends(get_session)):
    role = Roles.get_role_by_name(name_role, session)
    if role is None:
        raise HTTPException(404, "Роль не найдена")
    return role


@router.get("/paginated", response_model=list[Role])
def get_roles_paginated(offset: int = Query(0, ge=0), limit: int = Query(10, ge=1),
                        session: Session = Depends(get_session)):
    return Roles.get_roles_paginated(session, offset, limit)


@router.get("/search", response_model=list[Role])
def search_roles(substring: str, session: Session = Depends(get_session)):
    return Roles.search_roles(substring, session)


@router.get("/sorted", response_model=list[Role])
def get_roles_sorted(descending: bool = False, session: Session = Depends(get_session)):
    return Roles.get_roles_sorted(session, descending)


@router.delete("/", response_model=int)
def delete_all_roles(session: Session = Depends(get_session)):
    return Roles.delete_all_roles(session)


@router.get("/{role_id}", response_model=Role)
def get_role_by_id(role_id: int, session: Session = Depends(get_session)):
    role = Roles.get_role_by_id(role_id, session)
    if role is None:
        raise HTTPException(404, "Роль не найдена")
    return role


@router.put("/{role_id}", response_model=Role)
def update_role(role_id: int, role: RoleData, session: Session = Depends(get_session)):
    result = Roles.update_role(role_id, Role.model_validate(role), session)
    if result is None:
        raise HTTPException(404, "Роль не найдена")
    return result


@router.delete("/{role_id}")
def delete_role(role_id: int, session: Session = Depends(get_session)):
    if not Roles.delete_role(role_id, session):
        raise HTTPException(404, "Роль не найдена")
    return {"message": f"Роль с id={role_id} удалена"}
