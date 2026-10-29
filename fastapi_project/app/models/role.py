from sqlmodel import SQLModel, Field, Relationship


class RoleData(SQLModel):
    name_role: str = Field(min_length=1, max_length=30, unique=True, index=True)


class Role(RoleData, table=True):
    __tablename__ = "roles"
    id_role: int | None = Field(default=None, primary_key=True)
    profiles: list["Profile"] = Relationship(back_populates="role")
