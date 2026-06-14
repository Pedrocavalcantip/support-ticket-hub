from pydantic import BaseModel, Field, field_validator


class TicketCreate(BaseModel):
    usuario: str = Field(..., min_length=1)
    descricao: str = Field(..., min_length=1)

    @field_validator("usuario", "descricao")
    @classmethod
    def nao_pode_ser_vazio(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("campo obrigatorio")
        return valor


class TicketAssign(BaseModel):
    tecnico: str = Field(..., min_length=1)

    @field_validator("tecnico")
    @classmethod
    def tecnico_nao_pode_ser_vazio(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("tecnico e obrigatorio")
        return valor


class TicketResponse(BaseModel):
    ticket_id: str
    usuario: str
    descricao: str
    status: str
    timestamp_abertura: str
    tecnico: str = ""
    timestamp_atendimento: str = ""
    timestamp_fechamento: str = ""
