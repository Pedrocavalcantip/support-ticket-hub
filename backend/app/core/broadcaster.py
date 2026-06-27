from __future__ import annotations

import asyncio
import json
from typing import Set


class Broadcaster:
    """Gerencia os clientes SSE conectados e distribui eventos para todos eles.

    O servidor roda handlers de rota síncronos em uma thread pool. Para que esses
    handlers possam notificar clientes SSE (que vivem no event loop async), usamos
    `loop.call_soon_threadsafe`, que agenda o `put_nowait` de forma segura entre
    threads.
    """

    def __init__(self) -> None:
        self._clients: Set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def _set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Registra o event loop no startup da aplicação."""
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        """Cria e registra uma fila para um novo cliente SSE."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._clients.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove a fila de um cliente que desconectou."""
        self._clients.discard(q)

    def publish_sync(self, event: dict) -> None:
        """Publica um evento para todos os clientes conectados.

        Deve ser chamado de contexto síncrono (ex.: handlers de rota em threadpool).
        Usa `call_soon_threadsafe` para cruzar a fronteira sync→async com segurança.
        """
        if not self._clients or self._loop is None:
            return

        payload = json.dumps(event, ensure_ascii=False)
        for q in list(self._clients):
            try:
                self._loop.call_soon_threadsafe(q.put_nowait, payload)
            except asyncio.QueueFull:
                # Cliente lento — descarta o evento para não bloquear os outros.
                pass


broadcaster = Broadcaster()
