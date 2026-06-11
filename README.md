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

- [Backend](backend/README.md)

## Divisão inicial
- Hugo: fila Redis.
- Pedro: servidor/API e integração.
- Davi: frontend.
- Coutinho: DevOps, testes e documentação.

## Estrutura da fila no Redis

| Chave | Tipo | Função |
|---|---|---|
| `tickets:queue` | List | Fila FIFO — ticket_ids em ordem de chegada |
| `tickets:data:<uuid>` | Hash | Campos do ticket (ticket_id, usuario, descricao, status, timestamp_abertura) |
| `tickets:status:aberto` | Set | Índice de tickets aguardando atendimento |
| `tickets:status:em_atendimento` | Set | Índice de tickets sendo atendidos |
| `tickets:status:fechado` | Set | Índice de tickets encerrados |

## Perfis e permissões

| Perfil | Operações permitidas |
|---|---|
| **Usuário** | Abrir chamado (`POST /tickets`) |
| **Técnico** | Pegar chamado (`POST /tickets/pegar`), Fechar chamado (`POST /tickets/{id}/fechar`) |
| **Qualquer** | Listar tickets (`GET /tickets`), Ver status da fila (`GET /tickets/fila/status`) |

## Estratégia de concorrência

O método `pegar_ticket` usa um **script Lua atômico** executado diretamente no Redis. O Redis garante que nenhuma outra operação ocorre enquanto o script roda, impedindo que dois técnicos retirem o mesmo chamado da fila simultaneamente — mesmo que as requisições cheguem ao mesmo tempo.

## Endpoints da API

| Método | Rota | Perfil | Descrição |
|---|---|---|---|
| POST | `/tickets` | Usuário | Abre um novo chamado |
| POST | `/tickets/pegar` | Técnico | Pega o próximo chamado da fila |
| POST | `/tickets/{id}/fechar` | Técnico | Fecha um chamado em atendimento |
| GET | `/tickets?status=aberto` | Qualquer | Lista tickets por status |
| GET | `/tickets/fila/status` | Qualquer | Retorna tamanho da fila |