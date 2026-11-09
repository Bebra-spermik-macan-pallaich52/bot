from decimal import Decimal
from pydantic import ConfigDict, field_serializer, model_validator
from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel
from datetime import date
from typing import Annotated
from pydantic import ConfigDict, StringConstraints, model_validator


class TarifData(SQLModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tarif_name: str = Field(min_length=1, max_length=100)
    internet: int = Field(ge=0)
    count_minutes: int = Field(ge=0)
    count_sms: int = Field(ge=0)
    salary: Decimal = Field(ge=0, max_digits=12, decimal_places=2)

    @field_serializer("salary", when_used="json")
    def serialize_salary(self, value: Decimal) -> float:
        return float(value)


class Tarif(TarifData, table=True):
    __tablename__ = "tarif"
    __table_args__ = (
        CheckConstraint("internet >= 0 AND count_minutes >= 0 AND count_sms >= 0 AND salary >= 0"),
    )

    id_tarif: int | None = Field(default=None, primary_key=True)


class TarifRead(TarifData):
    id_tarif: int


class TarifUpdate(SQLModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, json_schema_extra={"example": {"salary": 600}})

    tarif_name: str | None = Field(default=None, min_length=1, max_length=100)
    internet: int | None = Field(default=None, ge=0)
    count_minutes: int | None = Field(default=None, ge=0)
    count_sms: int | None = Field(default=None, ge=0)
    salary: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)

    @model_validator(mode="after")
    def reject_null(self):
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Поля тарифа не могут быть null")
        return self


class TarifClientCount(SQLModel):
    tarif_name: str
    client_count: int


class TarifCount(SQLModel):
    tarif_id: int
    count: int


class TarifWithClientCount(TarifRead):
    client_count: int





Phone = Annotated[str, StringConstraints(pattern=r"^\+?[0-9]{5,15}$")]


class ClientData(SQLModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    number_phone: Phone = Field(min_length=5, max_length=16, schema_extra={"examples": ["+79001234567"]})
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
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, json_schema_extra={"example": {"lastname": "Петров"}})

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
    number_phone: str = Field(schema_extra={"examples": ["+79001234567"]})
    lastname: str
    firstname: str


class ClientBirthdayRead(SQLModel):
    full_name: str
    date_birthday: date


class ClientWithTarif(ClientData):
    tarif: TarifRead | None


class TarifAssignmentResult(SQLModel):
    message: str
