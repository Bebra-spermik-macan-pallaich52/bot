from sqlmodel import SQLModel, Field, Relationship
from .role import Role


class ProfileData(SQLModel):
    first_name: str | None = Field(default=None, max_length=50)
    second_name: str | None = Field(default=None, max_length=50)
    patronymic: str | None = Field(default=None, max_length=50)
    role_id: int = Field(default=1, foreign_key="roles.id_role")
    email: str = Field(min_length=1, max_length=30, unique=True)


class ProfileInput(ProfileData):
    password: str = Field(min_length=1, max_length=200)


class Profile(ProfileInput, table=True):
    __tablename__ = "profiles"
    id_users: int | None = Field(default=None, primary_key=True)
    role: Role | None = Relationship(back_populates="profiles")


class ProfileRead(ProfileData):
    id_users: int


class LoginData(SQLModel):
    email: str
    password: str
