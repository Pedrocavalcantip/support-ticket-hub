"""
fila.py — Módulo de Fila de Tickets no Redis
Equipe 13 — Sistema de Tickets de Suporte Técnico
CIN0143 - Introdução aos Sistemas Distribuídos e Redes de Computadores / UFPE

Responsável: Pessoa 1 (Fila/Redis)
Escopo: modelagem de dados e métodos de acesso ao Redis.
         NÃO contém rotas HTTP, lógica de frontend ou infraestrutura Docker.

Estrutura de chaves no Redis
─────────────────────────────
  tickets:queue          → List  (FIFO)  — armazena ticket_ids na ordem de chegada
  tickets:data:<id>      → Hash          — campos do ticket
  tickets:status:aberto  → Set           — ids com status "aberto"
  tickets:status:em_atendimento → Set    — ids com status "em_atendimento"
  tickets:status:fechado → Set           — ids com status "fechado"

A atomicidade no pegar_ticket() é garantida por um script Lua que executa
LPOP + atualização de status em uma única operação indivisível no Redis,
eliminando race conditions mesmo sob carga concorrente.
"""

import json
import uuid
import threading
from datetime import datetime, timezone

import redis


# ─────────────────────────────────────────────
# Constantes de chaves Redis
# ─────────────────────────────────────────────
QUEUE_KEY = "tickets:queue"                         # List FIFO de ticket_ids
DATA_KEY_PREFIX = "tickets:data:"                   # Hash por ticket
STATUS_SET = {
    "aberto":          "tickets:status:aberto",
    "em_atendimento":  "tickets:status:em_atendimento",
    "fechado":         "tickets:status:fechado",
}

# ─────────────────────────────────────────────
# Script Lua — coração da concorrência
# ─────────────────────────────────────────────
# Executa atomicamente no Redis:
#   1. Retira o ticket_id mais antigo da fila (LPOP)
#   2. Se a fila estava vazia, retorna nil imediatamente
#   3. Move o id do set "aberto" para "em_atendimento"
#   4. Atualiza os campos status e tecnico_responsavel no Hash do ticket
#   5. Retorna o ticket_id escolhido
#
# KEYS[1] = QUEUE_KEY
# KEYS[2] = STATUS_SET["aberto"]
# KEYS[3] = STATUS_SET["em_atendimento"]
# KEYS[4] = prefixo "tickets:data:" (concatenado com o id dentro do script)
# ARGV[1] = tecnico_id
# ARGV[2] = timestamp ISO do início do atendimento
_LUA_PEGAR_TICKET = """
local ticket_id = redis.call('LPOP', KEYS[1])
if not ticket_id then
    return nil
end

-- move o id entre os sets de status
redis.call('SREM', KEYS[2], ticket_id)
redis.call('SADD', KEYS[3], ticket_id)

-- atualiza o hash do ticket
local data_key = KEYS[4] .. ticket_id
redis.call('HSET', data_key,
    'status',             'em_atendimento',
    'tecnico_responsavel', ARGV[1],
    'timestamp_atendimento', ARGV[2]
)

return ticket_id
"""


class FilaTickets:
    """
    Gerencia a fila de chamados de suporte usando Redis como backend.

    Thread-safety
    ─────────────
    As operações de escrita críticas (pegar_ticket) são atômicas via Lua.
    Para uso em workers assíncronos (FastAPI/asyncio), prefira instanciar
    um cliente redis.asyncio.Redis separado — esta classe usa o cliente
    síncrono redis-py, adequado para threads independentes ou testes diretos.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        decode_responses: bool = True,
    ):
        """
        Conecta ao Redis e pré-compila o script Lua.

        Parâmetros
        ──────────
        host, port, db  : coordenadas do servidor Redis
        decode_responses: retorna strings Python em vez de bytes brutos
        """
        self._redis = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=decode_responses,
        )
        # Pré-registra o script no Redis; retorna um callable otimizado
        self._script_pegar = self._redis.register_script(_LUA_PEGAR_TICKET)

        # Testa a conexão imediatamente para falhar rápido na inicialização
        self._redis.ping()

    # ─────────────────────────────────────────
    # Método 1 — abrir_ticket
    # ─────────────────────────────────────────
    def abrir_ticket(self, usuario: str, descricao: str) -> dict:
        """
        Cria um novo chamado e o insere no fim da fila (FIFO).

        Parâmetros
        ──────────
        usuario  : identificador do usuário que abre o chamado
        descricao: texto livre descrevendo o problema

        Retorno
        ───────
        Dicionário com todos os campos do ticket criado.

        Estrutura Redis criada
        ──────────────────────
        - RPUSH  tickets:queue          ← insere no fim (posição mais nova)
        - HSET   tickets:data:<id>      ← persiste os campos
        - SADD   tickets:status:aberto  ← indexa para listagem rápida
        """
        ticket_id = str(uuid.uuid4())
        agora = datetime.now(timezone.utc).isoformat()

        ticket = {
            "ticket_id":         ticket_id,
            "usuario":           usuario,
            "descricao":         descricao,
            "status":            "aberto",
            "timestamp_abertura": agora,
            # Campos preenchidos posteriormente pelo pegar_ticket:
            "tecnico_responsavel":   "",
            "timestamp_atendimento": "",
        }

        data_key = DATA_KEY_PREFIX + ticket_id

        # Pipeline agrupa os três comandos numa única ida/volta à rede,
        # mas NÃO garante atomicidade — é suficiente para a criação porque
        # o ticket ainda não está visível a técnicos antes do RPUSH.
        pipe = self._redis.pipeline()
        pipe.hset(data_key, mapping=ticket)
        pipe.rpush(QUEUE_KEY, ticket_id)                    # entra no fim da fila
        pipe.sadd(STATUS_SET["aberto"], ticket_id)          # indexado como "aberto"
        pipe.execute()

        return ticket

    # ─────────────────────────────────────────
    # Método 2 — pegar_ticket  ★ CRÍTICO ★
    # ─────────────────────────────────────────
    def pegar_ticket(self, tecnico_id: str) -> dict | None:
        """
        Retira atomicamente o ticket mais antigo da fila e o marca
        como "em_atendimento" pelo técnico informado.

        A atomicidade é garantida pelo script Lua registrado no __init__:
        nenhum outro processo pode pegar o mesmo ticket entre o LPOP
        e a atualização de status — o Redis executa o script inteiro
        sem interrupções.

        Parâmetros
        ──────────
        tecnico_id: identificador único do técnico que está pegando o chamado

        Retorno
        ───────
        Dicionário completo do ticket (com status já "em_atendimento"),
        ou None se a fila estiver vazia.
        """
        agora = datetime.now(timezone.utc).isoformat()

        ticket_id = self._script_pegar(
            keys=[
                QUEUE_KEY,
                STATUS_SET["aberto"],
                STATUS_SET["em_atendimento"],
                DATA_KEY_PREFIX,          # prefixo — o script concatena com ticket_id
            ],
            args=[tecnico_id, agora],
        )

        if ticket_id is None:
            return None  # fila vazia

        # Lê o hash atualizado e devolve como dicionário Python
        data_key = DATA_KEY_PREFIX + ticket_id
        return self._redis.hgetall(data_key)

    # ─────────────────────────────────────────
    # Método 3 — fechar_ticket
    # ─────────────────────────────────────────
    def fechar_ticket(self, ticket_id: str, tecnico_id: str) -> bool:
        """
        Marca um ticket "em_atendimento" como "fechado".

        Valida que apenas o técnico responsável pode fechar o chamado.

        Retorno: True se fechado com sucesso, False caso contrário.
        """
        data_key = DATA_KEY_PREFIX + ticket_id
        ticket = self._redis.hgetall(data_key)

        if not ticket:
            return False  # ticket não existe

        if ticket.get("status") != "em_atendimento":
            return False  # só pode fechar o que está em atendimento

        if ticket.get("tecnico_responsavel") != tecnico_id:
            return False  # técnico errado

        agora = datetime.now(timezone.utc).isoformat()

        pipe = self._redis.pipeline()
        pipe.hset(data_key, mapping={
            "status":             "fechado",
            "timestamp_fechamento": agora,
        })
        pipe.srem(STATUS_SET["em_atendimento"], ticket_id)
        pipe.sadd(STATUS_SET["fechado"], ticket_id)
        pipe.execute()

        return True

    # ─────────────────────────────────────────
    # Método 4 — listar_tickets
    # ─────────────────────────────────────────
    def listar_tickets(self, status: str = "aberto") -> list[dict]:
        """
        Retorna todos os tickets com o status informado.

        Parâmetros
        ──────────
        status: "aberto" (padrão) | "em_atendimento" | "fechado"

        Implementação
        ─────────────
        Usa o Set de índice para iterar apenas sobre os ids relevantes,
        evitando um scan completo no Redis.
        """
        if status not in STATUS_SET:
            raise ValueError(f"Status inválido: '{status}'. Use: {list(STATUS_SET)}")

        ids = self._redis.smembers(STATUS_SET[status])

        if not ids:
            return []

        # Pipeline para buscar todos os hashes de uma vez
        pipe = self._redis.pipeline()
        for tid in ids:
            pipe.hgetall(DATA_KEY_PREFIX + tid)
        tickets = pipe.execute()

        # Filtra resultados vazios (ticket deletado manualmente do Redis)
        return [t for t in tickets if t]

    # ─────────────────────────────────────────
    # Utilitários de manutenção
    # ─────────────────────────────────────────
    def tamanho_fila(self) -> int:
        """Retorna quantos tickets estão aguardando na fila (status aberto)."""
        return self._redis.llen(QUEUE_KEY)

    def limpar_tudo(self) -> None:
        """
        Remove TODOS os dados de tickets do Redis.
        Use apenas em ambiente de desenvolvimento/testes.
        """
        keys = self._redis.keys("tickets:*")
        if keys:
            self._redis.delete(*keys)


# ═══════════════════════════════════════════════════════════════
# Bloco de testes locais
# Execute:  python fila.py
# Requisito: Redis rodando em localhost:6379
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import time

    SEP = "─" * 60

    print(SEP)
    print("TESTE DA FilaTickets — Sistemas Distribuídos / UFPE")
    print(SEP)

    fila = FilaTickets()
    fila.limpar_tudo()
    print("✓ Redis conectado e dados limpos.\n")

    # ── Teste 1: Abertura de chamados ────────────────────────────
    print("[ TESTE 1 ] Abrindo 3 chamados...")
    t1 = fila.abrir_ticket("ana",    "Computador não liga após atualização")
    t2 = fila.abrir_ticket("bruno",  "Erro 500 no sistema de RH")
    t3 = fila.abrir_ticket("carla",  "VPN desconecta a cada 5 minutos")

    print(f"  Ticket 1 → id={t1['ticket_id'][:8]}...  usuário={t1['usuario']}")
    print(f"  Ticket 2 → id={t2['ticket_id'][:8]}...  usuário={t2['usuario']}")
    print(f"  Ticket 3 → id={t3['ticket_id'][:8]}...  usuário={t3['usuario']}")
    print(f"  Tamanho da fila: {fila.tamanho_fila()} (esperado: 3)\n")

    # ── Teste 2: Listagem de abertos ─────────────────────────────
    print("[ TESTE 2 ] Listando tickets abertos...")
    abertos = fila.listar_tickets("aberto")
    print(f"  Total encontrado: {len(abertos)} (esperado: 3)")
    for t in abertos:
        print(f"  → [{t['status']}] {t['usuario']}: {t['descricao'][:40]}")
    print()

    # ── Teste 3: Técnico pega o primeiro chamado ──────────────────
    print("[ TESTE 3 ] Técnico 'tech_01' pega o próximo chamado...")
    pego = fila.pegar_ticket("tech_01")
    print(f"  Ticket obtido: id={pego['ticket_id'][:8]}...")
    print(f"  Usuário: {pego['usuario']} | Status: {pego['status']}")
    print(f"  Técnico: {pego['tecnico_responsavel']}")
    assert pego["usuario"] == "ana", "ERRO: deveria ser o ticket da Ana (FIFO)!"
    assert pego["status"] == "em_atendimento"
    print(f"  Tamanho da fila após pegar: {fila.tamanho_fila()} (esperado: 2)\n")

    # ── Teste 4: Fila vazia retorna None ─────────────────────────
    print("[ TESTE 4 ] Esgotando a fila com tech_02 e tech_03...")
    fila.pegar_ticket("tech_02")  # pega Bruno
    fila.pegar_ticket("tech_03")  # pega Carla
    resultado_vazio = fila.pegar_ticket("tech_04")  # fila vazia
    print(f"  Retorno com fila vazia: {resultado_vazio} (esperado: None)")
    assert resultado_vazio is None
    print()

    # ── Teste 5: Fechar ticket ────────────────────────────────────
    print("[ TESTE 5 ] Fechando o ticket de Bruno (tech_02)...")
    fechou = fila.fechar_ticket(t2["ticket_id"], "tech_02")
    print(f"  Resultado do fechamento: {fechou} (esperado: True)")
    assert fechou is True

    # Técnico errado não deve conseguir fechar
    nao_fechou = fila.fechar_ticket(t1["ticket_id"], "tech_ERRADO")
    print(f"  Técnico errado tentando fechar: {nao_fechou} (esperado: False)")
    assert nao_fechou is False
    print()

    # ── Teste 6: Concorrência — dois técnicos, um ticket ─────────
    print("[ TESTE 6 ] TESTE DE CONCORRÊNCIA — 2 técnicos, 1 ticket na fila")
    fila.limpar_tudo()
    fila.abrir_ticket("daniel", "Impressora não imprime em PDF")

    resultados = {}
    erros = []

    def tentar_pegar(nome_tecnico):
        try:
            ticket = fila.pegar_ticket(nome_tecnico)
            resultados[nome_tecnico] = ticket
        except Exception as e:
            erros.append(str(e))

    # Dispara as duas threads quase simultaneamente
    t_a = threading.Thread(target=tentar_pegar, args=("tech_A",))
    t_b = threading.Thread(target=tentar_pegar, args=("tech_B",))
    t_a.start(); t_b.start()
    t_a.join();  t_b.join()

    pegou_a = resultados.get("tech_A")
    pegou_b = resultados.get("tech_B")

    vencedor = "tech_A" if pegou_a else "tech_B" if pegou_b else "NENHUM"
    perdedor_resultado = pegou_b if vencedor == "tech_A" else pegou_a

    print(f"  tech_A recebeu: {'ticket ✓' if pegou_a else 'None (fila vazia)'}")
    print(f"  tech_B recebeu: {'ticket ✓' if pegou_b else 'None (fila vazia)'}")
    print(f"  Vencedor: {vencedor}")
    print(f"  Perdedor recebeu None: {perdedor_resultado is None} (esperado: True)")

    # A invariante fundamental: exatamente 1 técnico pegou o ticket
    assert (pegou_a is None) != (pegou_b is None), \
        "FALHA CRÍTICA: dois técnicos pegaram o mesmo ticket!"
    print("  ✓ Race condition prevenida com sucesso pelo script Lua!\n")

    # ── Resumo final ─────────────────────────────────────────────
    print(SEP)
    print("Todos os testes passaram. fila.py está correto e thread-safe.")
    print(SEP)
