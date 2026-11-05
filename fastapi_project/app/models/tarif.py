from decimal import Decimal

from pydantic import ConfigDict, field_serializer, model_validator
from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel


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
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

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
