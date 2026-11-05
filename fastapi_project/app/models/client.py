from datetime import date
from typing import Annotated

from pydantic import ConfigDict, StringConstraints, model_validator
from sqlmodel import Field, SQLModel

from app.models.tarif import TarifRead

Phone = Annotated[str, StringConstraints(pattern=r"^\+?[0-9]{5,15}$")]


class ClientData(SQLModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    number_phone: Phone = Field(min_length=5, max_length=16)
    id_tarif: int | None = Field(default=None, foreign_key="tarif.id_tarif", ondelete="RESTRICT", ge=1, index=True)
    lastname: str = Field(min_length=1, max_length=100)
    firstname: str = Field(min_length=1, max_length=100)
    patronymic_name: str | None = Field(default=None, min_length=1, max_length=100)
    date_birthday: date
    pasport_serial: str = Field(min_length=1, max_length=20)
    pasport_number: str = Field(min_length=1, max_length=20)
    date_issue: date


class Client(ClientData, table=True):
    __tablename__ = "client"

    number_phone: str = Field(primary_key=True, max_length=16)


class ClientUpdate(SQLModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    number_phone: Phone | None = Field(default=None, min_length=5, max_length=16)
    id_tarif: int | None = Field(default=None, ge=1)
    lastname: str | None = Field(default=None, min_length=1, max_length=100)
    firstname: str | None = Field(default=None, min_length=1, max_length=100)
    patronymic_name: str | None = Field(default=None, min_length=1, max_length=100)
    date_birthday: date | None = None
    pasport_serial: str | None = Field(default=None, min_length=1, max_length=20)
    pasport_number: str | None = Field(default=None, min_length=1, max_length=20)
    date_issue: date | None = None

    @model_validator(mode="after")
    def reject_null(self):
        required = self.model_fields_set - {"id_tarif", "patronymic_name"}
        if any(getattr(self, name) is None for name in required):
            raise ValueError("Обязательные поля клиента не могут быть null")
        return self


class ClientPhoneRead(SQLModel):
    number_phone: str
    lastname: str
    firstname: str


class ClientBirthdayRead(SQLModel):
    full_name: str
    date_birthday: date


class ClientWithTarif(ClientData):
    tarif: TarifRead | None


class TarifAssignmentResult(SQLModel):
    message: str
