from sqlmodel import Session, select, delete, func
from app.models.role import Role


class RoleController:
    @staticmethod
    def add_role(role: Role, session: Session) -> Role:
        if RoleController.get_role_by_name(role.name_role, session):
            raise ValueError("Роль с таким именем уже существует")
        session.add(role)
        session.commit()
        session.refresh(role)
        return role

    @staticmethod
    def get_role_by_id(role_id: int, session: Session) -> Role | None:
        return session.get(Role, role_id)

    @staticmethod
    def get_all_roles(session: Session) -> list[Role]:
        return list(session.exec(select(Role)).all())

    @staticmethod
    def update_role(role_id: int, role: Role, session: Session) -> Role | None:
        current = session.get(Role, role_id)
        if current is None:
            return None
        duplicate = session.exec(select(Role).where(
            Role.name_role == role.name_role, Role.id_role != role_id
        )).first()
        if duplicate:
            raise ValueError("Роль с таким именем уже существует")
        current.name_role = role.name_role
        session.commit()
        session.refresh(current)
        return current

    @staticmethod
    def delete_role(role_id: int, session: Session) -> bool:
        role = session.get(Role, role_id)
        if role is None:
            return False
        session.delete(role)
        session.commit()
        return True

    @staticmethod
    def get_role_by_name(name_role: str, session: Session) -> Role | None:
        return session.exec(select(Role).where(Role.name_role == name_role)).first()

    @staticmethod
    def count_roles(session: Session) -> int:
        return session.exec(select(func.count()).select_from(Role)).one()

    @staticmethod
    def get_roles_paginated(session: Session, offset: int = 0, limit: int = 10) -> list[Role]:
        return list(session.exec(select(Role).order_by(Role.id_role).offset(offset).limit(limit)).all())

    @staticmethod
    def search_roles(substring: str, session: Session) -> list[Role]:
        return list(session.exec(select(Role).where(Role.name_role.contains(substring, autoescape=True))).all())

    @staticmethod
    def get_roles_sorted(session: Session, descending: bool = False) -> list[Role]:
        order = Role.name_role.desc() if descending else Role.name_role
        return list(session.exec(select(Role).order_by(order)).all())

    @staticmethod
    def delete_all_roles(session: Session) -> int:
        result = session.exec(delete(Role))
        session.commit()
        return result.rowcount
