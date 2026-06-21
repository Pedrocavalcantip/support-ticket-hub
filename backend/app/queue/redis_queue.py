from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import redis


PENDING_KEY = "tickets:pending"
IN_PROGRESS_KEY = "tickets:in_progress"
CLOSED_KEY = "tickets:closed"
TICKET_KEY_PREFIX = "ticket:"

STATUS_OPEN = "OPEN"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_CLOSED = "CLOSED"

OLD_STATUS_MAP = {
    "aberto": STATUS_OPEN,
    "em_atendimento": STATUS_IN_PROGRESS,
    "fechado": STATUS_CLOSED,
}


_LUA_PEGAR = """
-- O Redis executa todo script Lua de forma atomica: enquanto este bloco roda,
-- nenhuma outra requisicao pode intercalar comandos entre o LPOP e a mudanca
-- de status. Assim, um ticket removido por um tecnico nao pode ser entregue a
-- outro tecnico simultaneamente.
local pending_key = KEYS[1]
local in_progress_key = KEYS[2]
local ticket_prefix = KEYS[3]

local tecnico = ARGV[1]
local timestamp = ARGV[2]

while true do
    -- LPOP retira exatamente o primeiro id da lista, preservando a ordem FIFO.
    local ticket_id = redis.call('LPOP', pending_key)
    if not ticket_id then
        return nil
    end

    local ticket_key = ticket_prefix .. ticket_id
    -- A verificacao ignora ids obsoletos sem interromper o consumo da fila.
    if redis.call('EXISTS', ticket_key) == 1
        and redis.call('HGET', ticket_key, 'status') == 'OPEN' then

        -- A atribuicao e o indice de atendimento sao atualizados antes de o
        -- script devolver o id, ainda dentro da mesma execucao atomica.
        redis.call('HSET', ticket_key,
            'status', 'IN_PROGRESS',
            'tecnico', tecnico,
            'timestamp_atendimento', timestamp
        )
        redis.call('HDEL', ticket_key, 'tecnico_responsavel')
        redis.call('SADD', in_progress_key, ticket_id)
        return ticket_id
    end
end
"""


class FilaTickets:
    """Gerencia a fila FIFO de chamados no Redis."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        decode_responses: bool = True,
    ):
        self._redis = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=decode_responses,
        )
        self._script_pegar = self._redis.register_script(_LUA_PEGAR)
        self._redis.ping()

    def abrir(self, ticket: dict[str, Any]) -> dict[str, str]:
        if not isinstance(ticket, dict):
            raise TypeError("ticket deve ser um dicionario")

        dados = self._normalizar_ticket(ticket)
        ticket_id = dados["ticket_id"]
        ticket_key = self._ticket_key(ticket_id)

        if self._redis.exists(ticket_key):
            raise ValueError(f"Ticket ja existe: {ticket_id}")

        pipe = self._redis.pipeline()
        pipe.hset(ticket_key, mapping=dados)
        pipe.rpush(PENDING_KEY, ticket_id)  # FIFO
        pipe.srem(IN_PROGRESS_KEY, ticket_id)
        pipe.srem(CLOSED_KEY, ticket_id)
        pipe.execute()

        return self._formatar_ticket(dados)

    def listar(self) -> list[dict[str, str]]:
        ids = self._redis.lrange(PENDING_KEY, 0, -1)
        if not ids:
            return []

        pipe = self._redis.pipeline()
        for ticket_id in ids:
            pipe.hgetall(self._ticket_key(ticket_id))
        tickets = pipe.execute()

        return [
            self._formatar_ticket(ticket)
            for ticket in tickets
            if ticket and ticket.get("status") == STATUS_OPEN
        ]

    def pegar(self, tecnico: str) -> dict[str, str] | None:
        tecnico_normalizado = self._validar_tecnico(tecnico)
        timestamp = self._agora()
        ticket_id = self._script_pegar(
            keys=[PENDING_KEY, IN_PROGRESS_KEY, TICKET_KEY_PREFIX],
            args=[tecnico_normalizado, timestamp],
        )

        if ticket_id is None:
            return None

        return self._formatar_ticket(self._redis.hgetall(self._ticket_key(ticket_id)))

    def fechar(self, ticket_id: str) -> bool:
        ticket_key = self._ticket_key(ticket_id)
        ticket = self._redis.hgetall(ticket_key)

        if not ticket:
            return False

        if ticket.get("status") != STATUS_IN_PROGRESS:
            return False

        pipe = self._redis.pipeline()
        pipe.hset(
            ticket_key,
            mapping={
                "status": STATUS_CLOSED,
                "timestamp_fechamento": self._agora(),
            },
        )
        pipe.lrem(PENDING_KEY, 0, ticket_id)
        pipe.srem(IN_PROGRESS_KEY, ticket_id)
        pipe.sadd(CLOSED_KEY, ticket_id)
        pipe.execute()

        return True

    # Wrappers mantidos para compatibilidade com o restante do backend atual.
    def abrir_ticket(self, usuario: str, descricao: str) -> dict[str, str]:
        return self.abrir({"usuario": usuario, "descricao": descricao})

    def listar_tickets(self, status: str = STATUS_OPEN) -> list[dict[str, str]]:
        status_normalizado = self._normalizar_status(status)

        if status_normalizado == STATUS_OPEN:
            return self.listar()

        index_key = {
            STATUS_IN_PROGRESS: IN_PROGRESS_KEY,
            STATUS_CLOSED: CLOSED_KEY,
        }.get(status_normalizado)

        if index_key is None:
            raise ValueError(
                "Status invalido. Use OPEN, IN_PROGRESS, CLOSED "
                "ou os nomes legados aberto, em_atendimento, fechado."
            )

        ids = self._redis.smembers(index_key)
        if not ids:
            return []

        pipe = self._redis.pipeline()
        for ticket_id in ids:
            pipe.hgetall(self._ticket_key(ticket_id))
        tickets = pipe.execute()

        return [
            self._formatar_ticket(ticket)
            for ticket in tickets
            if ticket and ticket.get("status") == status_normalizado
        ]

    def pegar_ticket(self, tecnico_id: str) -> dict[str, str] | None:
        return self.pegar(tecnico_id)

    def fechar_ticket(self, ticket_id: str, tecnico_id: str | None = None) -> bool:
        return self.fechar(ticket_id)

    def tamanho_fila(self) -> int:
        return self._redis.llen(PENDING_KEY)

    def limpar_tudo(self) -> None:
        keys = [PENDING_KEY, IN_PROGRESS_KEY, CLOSED_KEY]
        keys.extend(self._redis.keys(f"{TICKET_KEY_PREFIX}*"))
        if keys:
            self._redis.delete(*keys)

    def _normalizar_ticket(self, ticket: dict[str, Any]) -> dict[str, str]:
        dados = dict(ticket)
        self._validar_ticket(dados)

        ticket_id = dados.get("ticket_id") or dados.get("id") or str(uuid.uuid4())
        timestamp = dados.get("timestamp_abertura") or self._agora()
        tecnico = dados.get("tecnico", dados.get("tecnico_responsavel", ""))

        dados["ticket_id"] = str(ticket_id)
        dados["status"] = STATUS_OPEN
        dados["timestamp_abertura"] = str(timestamp)
        dados["tecnico"] = tecnico
        dados.pop("tecnico_responsavel", None)
        dados.setdefault("timestamp_atendimento", "")
        dados.setdefault("timestamp_fechamento", "")

        return {str(chave): self._valor_redis(valor) for chave, valor in dados.items()}

    def _validar_ticket(self, ticket: dict[str, Any]) -> None:
        usuario = ticket.get("usuario")
        descricao = ticket.get("descricao")

        if usuario is None or not str(usuario).strip():
            raise ValueError("usuario e obrigatorio")

        if descricao is None or not str(descricao).strip():
            raise ValueError("descricao e obrigatoria")

    def _validar_tecnico(self, tecnico: Any) -> str:
        if tecnico is None or not str(tecnico).strip():
            raise ValueError("tecnico e obrigatorio")

        return str(tecnico).strip()

    def _formatar_ticket(self, ticket: dict[str, str]) -> dict[str, str]:
        dados = dict(ticket)
        if "tecnico" not in dados and "tecnico_responsavel" in dados:
            dados["tecnico"] = dados["tecnico_responsavel"]
        dados.pop("tecnico_responsavel", None)
        return dados

    def _normalizar_status(self, status: str) -> str:
        if not status:
            return STATUS_OPEN

        status_normalizado = OLD_STATUS_MAP.get(status, status)
        return status_normalizado.upper()

    def _ticket_key(self, ticket_id: str) -> str:
        return f"{TICKET_KEY_PREFIX}{ticket_id}"

    def _agora(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _valor_redis(self, valor: Any) -> str:
        if valor is None:
            return ""

        if isinstance(valor, (str, int, float, bool)):
            return str(valor)

        return json.dumps(valor, ensure_ascii=False)
