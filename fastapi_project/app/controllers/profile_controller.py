from sqlmodel import Session, select
from app.models.profile import Profile
from app.core.security import hash_password, verify_password


class ProfileController:
    @staticmethod
    def add_profile(profile: Profile, session: Session) -> Profile:
        if session.exec(select(Profile).where(Profile.email == profile.email)).first():
            raise ValueError("Профиль с таким email уже существует")
        profile.password = hash_password(profile.password)
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return profile

    @staticmethod
    def get_profile_by_id(profile_id: int, session: Session) -> Profile | None:
        return session.get(Profile, profile_id)

    @staticmethod
    def get_all_profiles(session: Session) -> list[Profile]:
        return list(session.exec(select(Profile)).all())

    @staticmethod
    def update_profile(profile_id: int, profile: Profile, session: Session) -> Profile | None:
        current = session.get(Profile, profile_id)
        if current is None:
            return None
        duplicate = session.exec(select(Profile).where(
            Profile.email == profile.email, Profile.id_users != profile_id
        )).first()
        if duplicate:
            raise ValueError("Профиль с таким email уже существует")
        for field in ("first_name", "second_name", "patronymic", "role_id", "email"):
            setattr(current, field, getattr(profile, field))
        if not verify_password(profile.password, current.password):
            current.password = hash_password(profile.password)
        session.commit()
        session.refresh(current)
        return current

    @staticmethod
    def delete_profile(profile_id: int, session: Session) -> bool:
        profile = session.get(Profile, profile_id)
        if profile is None:
            return False
        session.delete(profile)
        session.commit()
        return True

    @staticmethod
    def authenticate(email: str, password: str, session: Session) -> Profile | None:
        profile = session.exec(select(Profile).where(Profile.email == email)).first()
        if profile and verify_password(password, profile.password):
            return profile
        return None

    @staticmethod
    def get_profiles_by_role(role_id: int, session: Session) -> list[Profile]:
        return list(session.exec(select(Profile).where(Profile.role_id == role_id)).all())
