from pydantic import BaseModel, Field

class AbrirTicketRequest(BaseModel):
    usuario: str = Field(..., min_length=1)
    descricao: str = Field(..., min_length=5)

class PegarTicketRequest(BaseModel):
    tecnico_id: str = Field(..., min_length=1)

class FecharTicketRequest(BaseModel):
    tecnico_id: str = Field(..., min_length=1)

class TicketResponse(BaseModel):
    ticket_id: str
    usuario: str
    descricao: str
    status: str
    timestamp_abertura: str
    tecnico_responsavel: str = ""
    timestamp_atendimento: str = ""

class FilaStatusResponse(BaseModel):
    tamanho: int
    mensagem: str