from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.db.session import get_session
from app.controllers.profile_controller import ProfileController as Profiles
from app.models.profile import Profile, ProfileInput, ProfileRead, LoginData

router = APIRouter(prefix="/profiles", tags=["Profiles"])


@router.get("/", response_model=list[ProfileRead])
def get_all_profiles(session: Session = Depends(get_session)):
    return Profiles.get_all_profiles(session)


@router.post("/", response_model=ProfileRead, status_code=201)
def add_profile(profile: ProfileInput, session: Session = Depends(get_session)):
    return Profiles.add_profile(Profile.model_validate(profile), session)


@router.post("/authenticate", response_model=ProfileRead)
def authenticate(data: LoginData, session: Session = Depends(get_session)):
    result = Profiles.authenticate(data.email, data.password, session)
    if result is None:
        raise HTTPException(401, "Неверный email или пароль")
    return result


@router.get("/by-role/{role_id}", response_model=list[ProfileRead])
def get_profiles_by_role(role_id: int, session: Session = Depends(get_session)):
    return Profiles.get_profiles_by_role(role_id, session)


@router.get("/{profile_id}", response_model=ProfileRead)
def get_profile_by_id(profile_id: int, session: Session = Depends(get_session)):
    result = Profiles.get_profile_by_id(profile_id, session)
    if result is None:
        raise HTTPException(404, "Профиль не найден")
    return result


@router.put("/{profile_id}", response_model=ProfileRead)
def update_profile(profile_id: int, profile: ProfileInput, session: Session = Depends(get_session)):
    result = Profiles.update_profile(profile_id, Profile.model_validate(profile), session)
    if result is None:
        raise HTTPException(404, "Профиль не найден")
    return result


@router.delete("/{profile_id}")
def delete_profile(profile_id: int, session: Session = Depends(get_session)):
    if not Profiles.delete_profile(profile_id, session):
        raise HTTPException(404, "Профиль не найден")
    return {"message": f"Профиль с id={profile_id} удалён"}
