# Arquitetura

## Visão geral

O sistema é dividido entre clientes HTTP, servidor da aplicação e Redis, que guarda a fila.
O cliente principal da Entrega 2 é o terminal; o frontend é opcional. O fluxo é sempre o mesmo:

```
Terminal/curl ou frontend  --HTTP/JSON-->  FastAPI  -->  ticket_service  -->  FilaTickets  -->  Redis
```

Os clientes nunca falam direto com o Redis. Eles só conhecem a API HTTP. Quem traduz uma
requisição em operações na fila é o backend, em camadas: a rota recebe e valida, o serviço
chama a fila, e a fila mexe no Redis.

## Decisão tecnológica e justificativa

A sugestão do enunciado era usar algo como BullMQ com Redis, RabbitMQ ou equivalente. A
gente escolheu **FastAPI + Redis**, que se encaixa na mesma ideia (servidor com framework
e fila em memória) e é mais direto para o que a equipe já conhece.

- **FastAPI** para o servidor. É um framework leve, fácil de organizar em rotas e já gera
  a documentação interativa em `/docs` de graça, o que ajuda a equipe a testar a API sem
  precisar de outras ferramentas. Usamos ele em vez de socket puro, como pede a entrega.
- **Redis** para a fila. Ele guarda tudo em memória e tem os tipos de dado que a gente
  precisa (lista para a ordem FIFO, hash para os dados do chamado). O mais importante é
  que ele permite rodar um script de forma atômica, o que resolve o problema de dois
  técnicos pegarem o mesmo chamado sem precisar de lock manual no Python.
- **Docker Compose** para subir backend e Redis juntos, deixando o ambiente igual para
  todo mundo do grupo.

## Concorrência HTTP

A Entrega 2 usa requisições HTTP independentes, sem conexão persistente. As rotas síncronas são
executadas pelo FastAPI/Starlette em uma thread pool, permitindo atender requisições HTTP
simultâneas. Cada requisição registra método, rota, IP, status e duração nos logs estruturados.
O estado compartilhado fica no Redis, e a operação crítica de consumo é protegida pelo Lua.

## Estado central em memória

O estado fica todo no Redis, organizado assim:

- `tickets:pending` (List): a fila em si, com os ids dos chamados na ordem de chegada.
  Abrir um chamado faz um `RPUSH` no fim e pegar faz um `LPOP` do começo, o que dá o
  comportamento FIFO.
- `ticket:<id>` (Hash): os dados de cada chamado, incluindo os campos pedidos no
  enunciado (`ticket_id`, `usuario`, `descricao`, `status`, `timestamp_abertura`) mais os
  campos de controle (`tecnico`, `timestamp_atendimento`, `timestamp_fechamento`).
- `tickets:in_progress` e `tickets:closed` (Set): índices auxiliares para achar
  rapidamente os chamados que estão em atendimento ou já fechados.

O status de cada chamado anda por três estados: `OPEN` -> `IN_PROGRESS` -> `CLOSED`.

## Exclusividade

O caso de dois técnicos disputando o mesmo chamado é tratado na hora de pegar. Em vez de
fazer "ler a fila, escolher o primeiro e marcar" em passos separados (onde daria para dar
errado no meio), a fila usa um script Lua que o Redis executa de uma vez só. Enquanto ele
roda, nada mais acontece no Redis, então a retirada é indivisível. Resultado: um chamado
em atendimento nunca cai para dois técnicos.

## Estrutura de pastas do backend

```
backend/app/
  main.py        -> sobe o FastAPI e registra as rotas
  api/           -> rotas HTTP (tickets.py)
  schemas/       -> modelos de entrada/saida com validacao (Pydantic)
  services/      -> camada que liga as rotas a fila
  queue/         -> FilaTickets, a implementacao em cima do Redis
  core/          -> configuracao (host/porta do Redis)
```

## Relação com o que a Entrega 2 pede

- Servidor multicliente: FastAPI responde requisições HTTP concorrentes na porta 8000.
- Comandos no terminal: abertura, consumo e fechamento são acessíveis por `curl`.
- Estado central em memória: fila e tickets ficam no Redis.
- Exclusividade: o `pegar` atômico com Lua impede atribuição duplicada.
- Logs operacionais: requisições e operações são emitidas em JSON no console.
- Testes: core, API, concorrência e logging são executados com pytest.
- Protocolo detalhado: ver [Contrato.md](Contrato.md).
