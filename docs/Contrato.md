# Protocolo de comunicação

Este documento descreve como o frontend conversa com o servidor. A comunicação é feita
por HTTP, trocando JSON nos dois sentidos. O servidor sobe na porta 8000, então a base
das URLs é `http://127.0.0.1:8000`.

A ideia é simples: o usuário abre chamados, esses chamados entram numa fila e o técnico
vai consumindo essa fila um por vez. Por isso as rotas estão separadas por perfil.

## Como o ticket é representado

Toda resposta que devolve um chamado usa o mesmo formato. Os campos são:

- `ticket_id`: identificador único do chamado (gerado pelo servidor).
- `usuario`: quem abriu.
- `descricao`: texto do problema.
- `status`: `OPEN`, `IN_PROGRESS` ou `CLOSED`.
- `timestamp_abertura`: data/hora em que o chamado foi aberto (ISO 8601, UTC).
- `tecnico`: técnico que pegou o chamado (vazio enquanto ninguém pegou).
- `timestamp_atendimento`: quando o técnico pegou (vazio antes disso).
- `timestamp_fechamento`: quando foi fechado (vazio antes disso).

Exemplo:

```json
{
  "ticket_id": "8f3c1b2a-...",
  "usuario": "joao",
  "descricao": "Notebook nao liga",
  "status": "OPEN",
  "timestamp_abertura": "2026-06-14T18:20:00+00:00",
  "tecnico": "",
  "timestamp_atendimento": "",
  "timestamp_fechamento": ""
}
```

## Rotas

### Abrir chamado (perfil Usuário)

`POST /tickets`

Corpo:

```json
{ "usuario": "joao", "descricao": "Notebook nao liga" }
```

Resposta `201 Created` com o ticket recém-criado (formato acima, status `OPEN`).

Os dois campos são obrigatórios. O servidor faz `strip()` e recusa string vazia ou só
com espaços. Se o formato estiver errado, o FastAPI/Pydantic responde `422` explicando
qual campo falhou.

### Listar chamados abertos (qualquer perfil)

`GET /tickets`

Resposta `200 OK` com uma lista de tickets que estão na fila (status `OPEN`), na ordem
de chegada. Se não tiver nenhum, devolve lista vazia.

### Pegar o próximo chamado (perfil Técnico)

`PATCH /tickets/next`

Corpo:

```json
{ "tecnico": "maria" }
```

Pega o primeiro chamado da fila, marca como `IN_PROGRESS` e devolve `200 OK` com o
ticket. Se a fila estiver vazia, responde `404 Not Found`.

Essa operação é a parte crítica da exclusividade: a retirada acontece de forma atômica
no Redis (script Lua), então dois técnicos chamando `next` ao mesmo tempo nunca recebem
o mesmo chamado. Um pega o primeiro, o outro pega o seguinte.

### Fechar chamado (perfil Técnico)

`PATCH /tickets/{ticket_id}/close`

Fecha um chamado que está em atendimento. Resposta `200 OK`:

```json
{ "ticket_id": "8f3c1b2a-...", "status": "CLOSED" }
```

Se o ticket não existir ou não estiver em atendimento, responde `400 Bad Request`.

### Saúde do servidor

`GET /health` responde `{ "status": "ok" }`. Serve só para testar se o servidor está no
ar.

## Resumo dos códigos de resposta

| Situação | Código |
|---|---|
| Chamado aberto com sucesso | 201 |
| Listagem / pegou / fechou com sucesso | 200 |
| Fila vazia ao tentar pegar | 404 |
| Tentou fechar ticket inexistente ou que não estava em atendimento | 400 |
| Corpo inválido (campo faltando ou vazio) | 422 |
