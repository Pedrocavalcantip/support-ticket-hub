# support-ticket-hub

Sistema distribuído de fila de chamados de suporte técnico.

## Enunciado

[Equipe 13] — Sistema de Tickets de Suporte Técnico (Sugestão: Sockets / BullMQ com
Redis / RabbitMQ ou equivalente)
● Modelar a fila sequencial de chamados em memória em ordem de prioridade de chegada (FIFO), com campos: {ticket_id, usuario, descricao, status, timestamp_abertura}.
● Definir o design do protocolo textual separando permissões: perfil Usuário (pode abrir chamado) e perfil Técnico (pode consumir/fechar chamado).
● Escrever as validações conceituais de exclusividade: garantir que um chamado marcado como "em atendimento" não possa ser atribuído a um segundo técnico simultaneamente.
● Configurar a escuta TCP/fila com o framework escolhido (BullMQ+Redis, RabbitMQ ou equivalente) e testar o enfileiramento básico de uma mensagem.
● Documentar no README: estrutura da fila, diferenciação de perfis, tecnologia escolhida e justificativa.

## Tecnologias escolhidas

- **FastAPI**: servidor da aplicação e endpoints HTTP.
- **Redis**: armazenamento da fila de chamados.
- **Docker Compose**: execução dos serviços.
- **Frontend Web**: interface para usuários e técnicos.

## Justificativa tecnológica

O FastAPI foi escolhido por facilitar a criação de uma API simples, organizada e documentável.

O Redis foi escolhido por ser adequado para filas em memória, permitindo operações rápidas e controle da ordem dos chamados.

O Docker Compose será usado para padronizar a execução do backend e do Redis.

## Como rodar

### Com Docker (mais fácil)

Com Docker e Docker Compose instalados, na raiz do projeto:

```bash
docker compose up --build
```

Isso sobe o Redis e o backend juntos. A API fica na porta fixa **8000**: dá pra testar em
`http://127.0.0.1:8000/health` e ver todos os endpoints em `http://127.0.0.1:8000/docs`.
Para parar, use `docker compose down`.

### Sem Docker

Dá pra rodar o backend num ambiente virtual. O passo a passo está em
[backend/README.md](backend/README.md). Nesse caso é preciso ter um Redis rodando, porque a
API conecta nele assim que inicia.

### Frontend

As telas são HTML puro, na pasta `frontend/`. Com o backend no ar, abra `frontend/index.html`
no navegador (ou sirva a pasta com `python -m http.server`). A área do usuário abre chamados e
a área do técnico pega e fecha os chamados da fila.

Isso aqui é o esqueleto da Entrega 1: servidor respondendo na porta certa, fila enfileirando e
o frontend já consumindo a API. Os refinamentos vêm nas próximas entregas.

## Estrutura de pastas

```
support-ticket-hub/
├── backend/              # API FastAPI + fila no Redis
│   ├── app/
│   │   ├── main.py       # sobe o servidor e registra as rotas
│   │   ├── api/          # rotas HTTP (tickets)
│   │   ├── schemas/      # validação de entrada/saída (Pydantic)
│   │   ├── services/     # camada entre as rotas e a fila
│   │   ├── queue/        # FilaTickets, implementação em cima do Redis
│   │   ├── core/         # configuração (host/porta do Redis)
│   │   └── websocket/    # base de WebSocket (uso futuro)
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/             # telas HTML do usuário e do técnico
├── docs/                 # Contrato.md (protocolo) e Arquitetura.md
├── docker-compose.yml
└── README.md
```

## Validações básicas

A entrada é validada já na borda da API, pelos schemas do Pydantic em `backend/app/schemas`.
`usuario` e `descricao` são obrigatórios e não podem ser vazios nem só espaços (passam por
`strip()`). Se o corpo da requisição vier errado, o servidor responde `422` apontando o campo.
Além disso, fechar um chamado só funciona se ele estiver em atendimento, senão retorna erro.

## Estrutura da fila no Redis

A fila é guardada inteiramente no Redis. A ordem de chegada (FIFO) é mantida por uma
lista, e cada chamado em si fica num hash separado. Além disso temos dois sets que
funcionam como índice para saber rapidamente quais tickets estão em atendimento ou já
fechados. Os campos exigidos pelo enunciado (`ticket_id`, `usuario`, `descricao`,
`status`, `timestamp_abertura`) ficam todos no hash do ticket.

| Chave | Tipo | Função |
|---|---|---|
| `tickets:pending` | List | Fila FIFO com os ticket_ids aguardando atendimento, na ordem de chegada |
| `ticket:<id>` | Hash | Dados do chamado (ticket_id, usuario, descricao, status, timestamp_abertura, etc.) |
| `tickets:in_progress` | Set | Índice dos chamados que algum técnico já pegou |
| `tickets:closed` | Set | Índice dos chamados encerrados |

O status de um chamado passa por três valores ao longo da vida dele: `OPEN` (acabou de
ser aberto e está na fila), `IN_PROGRESS` (um técnico pegou) e `CLOSED` (foi fechado).

## Perfis e permissões

Separamos quem pode fazer o quê em dois perfis. O **Usuário** só consegue abrir chamado.
O **Técnico** é quem consome a fila: pega o próximo da vez e depois fecha. Listar os
chamados abertos qualquer um pode fazer, já que é só leitura.

| Perfil | O que pode fazer |
|---|---|
| Usuário | Abrir chamado (`POST /tickets`) |
| Técnico | Pegar o próximo da fila (`PATCH /tickets/next`) e fechar um chamado (`PATCH /tickets/{id}/close`) |
| Qualquer | Listar os chamados abertos (`GET /tickets`) |

## Estratégia de concorrência

O ponto mais delicado é garantir que dois técnicos não peguem o mesmo chamado ao mesmo
tempo. Para isso o método `pegar` não faz a retirada em vários passos no Python, e sim
através de um script Lua que roda dentro do próprio Redis. Enquanto esse script executa,
o Redis não deixa nenhuma outra operação acontecer, então a sequência "tira o primeiro
da fila e marca como em atendimento" vira uma coisa indivisível. Mesmo que duas
requisições cheguem no mesmo instante, uma vai pegar o chamado e a outra vai pegar o
próximo (ou nenhum, se a fila esvaziar).

## Endpoints da API

| Método | Rota | Perfil | Descrição |
|---|---|---|---|
| POST | `/tickets` | Usuário | Abre um novo chamado |
| GET | `/tickets` | Qualquer | Lista os chamados abertos |
| PATCH | `/tickets/next` | Técnico | Pega o próximo chamado da fila |
| PATCH | `/tickets/{id}/close` | Técnico | Fecha um chamado em atendimento |

O detalhamento completo do protocolo (payloads, respostas e códigos de erro) está em
[docs/Contrato.md](docs/Contrato.md). A visão de arquitetura está em
[docs/Arquitetura.md](docs/Arquitetura.md).