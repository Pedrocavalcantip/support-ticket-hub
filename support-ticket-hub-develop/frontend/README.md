- Tela de usuário para abrir chamado.
- Tela de técnico para visualizar a fila.
- Botão para técnico pegar próximo chamado.
- Integração com os endpoints definidos em docs/Contrato.md.

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