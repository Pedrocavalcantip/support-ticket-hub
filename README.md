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
- **Frontend Web**: HTML, CSS e JavaScript puro nesta entrega, sem framework, para testar
  o fluxo de usuário e técnico. Nas próximas entregas pretendemos usar Next.js.

## Justificativa tecnológica

A entrega pede um servidor rodando com um framework (não mais socket puro), um estado central
em memória e validações de formato. Cada escolha abaixo foi pensada pra encaixar nessas peças.

**FastAPI.** É um framework web de Python, então já cumpre o "não usar socket puro". A gente
escolheu ele porque define as rotas de forma enxuta e tipada, e a validação de entrada vem de
graça junto, pelo Pydantic. Isso atende direto o requisito de validações básicas de formato:
declarar que `usuario` e `descricao` são obrigatórios já faz o servidor recusar entrada inválida.
Além disso o FastAPI gera sozinho a documentação interativa (Swagger, em `/docs`), o que ajuda a
equipe a enxergar e testar o protocolo sem precisar de outra ferramenta. Como o time já trabalha
com Python, a curva de aprendizado é curta.

**Redis.** O ponto central da entrega é guardar o estado em memória, e o Redis é justamente um
banco em memória, então ele *é* esse estado central. O que pesou bastante é que as estruturas
dele casam com o nosso modelo sem precisar inventar nada: uma List dá a fila FIFO (`RPUSH` pra
entrar no fim, `LPOP` pra sair do começo), um Hash guarda os dados de cada chamado e Sets servem
de índice por status. E o mais importante: ele executa scripts Lua de forma atômica, o que
resolve a exclusividade exigida (dois técnicos nunca pegam o mesmo chamado) sem a gente ter que
implementar trava na mão. A sugestão do enunciado era BullMQ, que é do mundo Node; como o backend
é Python, usar o Redis direto entrega a mesma fila de um jeito mais simples pra nós.

**Docker Compose.** Sobe o backend e o Redis juntos com um comando só, sempre na porta fixada
(8000) e igual na máquina de todo mundo do grupo. Isso evita o clássico "na minha máquina
funciona" e ainda facilita rodar os testes dentro do container.

**Frontend em HTML, CSS e JavaScript puro (nesta entrega).** Como esta fase é de arquitetura e
escopo, o foco é o servidor, o estado e o protocolo; a tela entra como um complemento pra provar
que o contrato funciona de ponta a ponta. HTML puro não tem etapa de build, abre direto no
navegador e é rápido de mexer, o que é perfeito pra um esqueleto. Já dá pra exercitar o fluxo
inteiro (abrir, pegar e fechar chamado) sem montar um projeto de frontend completo.

**Next.js (próximas entregas).** Conforme o sistema crescer, manter a interface em HTML puro vai
ficando trabalhoso. O Next.js (em cima do React) traz componentização, roteamento e uma forma
mais organizada de lidar com estado, deixando a tela mais sustentável quando tiver mais fluxos.
Ele também facilita a atualização em tempo real (por exemplo via WebSocket, que já tem uma base no
backend) no lugar do polling que usamos agora. E essa troca é tranquila justamente por causa da
arquitetura: como o backend expõe uma API HTTP/JSON desacoplada da tela, dá pra começar simples
agora com HTML e migrar pro Next.js depois mexendo só no cliente, sem tocar no servidor.

## Arquitetura

O sistema é dividido em três partes: a interface web, o servidor da aplicação e o Redis,
que guarda o estado. O frontend nunca fala direto com o Redis; ele só conhece a API HTTP.
Quem traduz uma requisição em operações na fila é o backend, organizado em camadas.

```mermaid
flowchart LR
    FE["Frontend<br/>(HTML/CSS/JS)"]

    subgraph servidor["Servidor (porta 8000)"]
        API["API FastAPI<br/>rotas + validacao"]
        SVC["Servico<br/>ticket_service"]
        FILA["FilaTickets<br/>regras da fila"]
    end

    RD[("Redis<br/>estado em memoria")]

    FE -- "HTTP / JSON" --> API
    API --> SVC
    SVC --> FILA
    FILA -- "comandos + script Lua" --> RD
```

### Elementos

- **Frontend (telas)**: HTML, CSS e JavaScript puro, sem framework. Tem a tela do usuário
  (abrir chamado) e a do técnico (pegar e fechar chamado, acompanhar a fila). Conversa com a
  API por HTTP trocando JSON e não acessa o Redis diretamente.
- **API FastAPI (porta 8000)**: é a porta de entrada. Recebe as requisições, valida o formato
  com Pydantic, separa os perfis (quais rotas o usuário e o técnico usam) e responde em JSON.
  Sobe na porta fixa 8000, com `/health` para teste e `/docs` com a documentação automática.
- **Camada de serviço (`ticket_service`)**: fica entre as rotas e a fila. As rotas não mexem
  no Redis direto, elas chamam o serviço, que chama a fila. Isso mantém a API desacoplada da
  implementação do armazenamento.
- **Fila (`FilaTickets`, em `queue/redis_queue.py`)**: onde mora a lógica da fila. Faz
  abrir/listar/pegar/fechar traduzindo para operações no Redis, garante a ordem FIFO e a
  exclusividade (um chamado nunca vai para dois técnicos) através de um script Lua atômico.
- **Redis**: o estado central em memória. Guarda a fila numa List, os dados de cada chamado
  num Hash e índices por status em Sets.

### Fluxo de uma requisição

- **Abrir** (usuário): `POST /tickets` → serviço → `FilaTickets.abrir` → o chamado entra no
  fim da fila (`RPUSH`) e seus dados vão para um Hash, com status `OPEN`.
- **Pegar** (técnico): `PATCH /tickets/next` → `FilaTickets.pegar` → um script Lua faz o
  `LPOP` e marca como `IN_PROGRESS` numa operação só, então dois técnicos nunca pegam o mesmo.
- **Fechar** (técnico): `PATCH /tickets/{id}/close` → `FilaTickets.fechar` → o chamado vira
  `CLOSED`.

O detalhamento da fila, dos perfis, do protocolo e da estratégia de concorrência está nas
seções abaixo.

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

Também dá pra rodar o backend direto, num ambiente virtual. Nesse caso é preciso ter um Redis
no ar, porque a API conecta nele assim que inicia (a forma mais simples é subir só o Redis com
`docker compose up -d redis`).

No Linux ou macOS:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

No Windows (PowerShell):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

O servidor sobe em `http://127.0.0.1:8000`, com `/health` para teste e `/docs` com a
documentação interativa.

## Entrega 2 — Comunicação e Core

### Teste de concorrência

Para testar a concorrência com HTTP + Redis, suba o projeto com Docker Compose na raiz do
repositório:

```bash
docker compose up --build
```

Com a API rodando em `http://localhost:8000` e as dependências do backend instaladas, execute o
teste de carga em outro terminal:

```bash
python backend/scripts/load_test.py --base-url http://localhost:8000 --tickets 50 --technicians 10
```

Exemplo do tipo de saída esperada:

```text
=== Teste de concorrencia HTTP + Redis ===
API: http://localhost:8000
Tickets solicitados para criacao: 50
Tecnicos concorrentes: 10

Resumo:
- Tickets criados: 50/50
- Requisicoes de consumo feitas por tecnicos: 60
- Tickets atribuidos: 50
- Respostas de fila vazia: 10
- Duplicidade de ticket_id: NAO
- Tickets abertos ao final (GET /tickets): 0
- Tempo total de execucao: 0.42s

Status final: SUCESSO
```

O teste cria vários chamados simultaneamente usando `POST /tickets` e depois simula vários
técnicos consumindo a fila em paralelo com `PATCH /tickets/next`. No final, consulta
`GET /tickets` e verifica se nenhum `ticket_id` foi entregue para dois técnicos diferentes.
Se a API não estiver no ar, o script mostra uma mensagem orientando a rodar
`docker compose up --build`, sem despejar traceback desnecessário.

### Logs operacionais

O backend escreve os logs da aplicação no console em formato JSON, com um evento por linha.
Toda requisição HTTP registra `timestamp`, nível, método, rota, IP do cliente, código de status e
tempo de resposta em milissegundos. Exceções inesperadas também são registradas com o evento
`http_request_failed` antes de serem tratadas pelo servidor.

As operações principais da fila geram os seguintes eventos:

| Evento | Nível | Situação |
|---|---|---|
| `ticket_created` | `INFO` | usuário abriu e enfileirou um chamado |
| `ticket_assigned` | `INFO` | técnico retirou o próximo chamado da fila |
| `ticket_closed` | `INFO` | chamado em atendimento foi fechado |
| `empty_queue` | `WARNING` | técnico tentou consumir uma fila vazia |
| `invalid_ticket_close` | `WARNING` | tentativa de fechar ticket inexistente ou fora de atendimento |

Os logs aparecem diretamente no terminal usado para subir a aplicação:

```bash
docker compose up --build
```

Também é possível acompanhá-los em outro terminal:

```bash
docker compose logs -f backend
```

O teste de carga da seção anterior gera várias linhas de criação, atribuição, fila vazia e
requisições concorrentes. Trecho real capturado no console durante a validação com Docker:

```json
{"timestamp":"2026-06-21T18:19:10.643600+00:00","level":"INFO","logger":"support_ticket_hub.app.services.ticket_service","event":"ticket_created","ticket_id":"4f1d66b8-e5ce-4d6a-9a67-ab585c011007","usuario":"validacao-logs"}
{"timestamp":"2026-06-21T18:19:19.287204+00:00","level":"INFO","logger":"support_ticket_hub.app.services.ticket_service","event":"ticket_assigned","ticket_id":"4f1d66b8-e5ce-4d6a-9a67-ab585c011007","tecnico":"tecnico-validacao"}
{"timestamp":"2026-06-21T18:18:29.597943+00:00","level":"WARNING","logger":"support_ticket_hub.app.services.ticket_service","event":"empty_queue","tecnico":"tecnico-load-002"}
{"timestamp":"2026-06-21T18:19:29.116837+00:00","level":"WARNING","logger":"support_ticket_hub.app.services.ticket_service","event":"invalid_ticket_close","ticket_id":"ticket-inexistente"}
{"timestamp":"2026-06-21T18:19:29.218545+00:00","level":"INFO","logger":"support_ticket_hub.app.services.ticket_service","event":"ticket_closed","ticket_id":"4f1d66b8-e5ce-4d6a-9a67-ab585c011007"}
{"timestamp":"2026-06-21T18:19:29.219032+00:00","level":"INFO","logger":"support_ticket_hub.app.main","event":"http_request","method":"PATCH","route":"/tickets/{ticket_id}/close","client_ip":"172.18.0.1","status_code":200,"duration_ms":1.78}
```

### Frontend

As telas ficam na pasta `frontend/` e são HTML, CSS e JavaScript puro, sem framework e sem
etapa de build. Com o backend no ar, basta abrir `frontend/index.html` no navegador. Se o
navegador travar algo por estar abrindo via `file://`, sirva a pasta como site estático:

```bash
cd frontend
python -m http.server 3000
```

e acesse `http://localhost:3000`.

São três arquivos:

- **`index.html`**: página única com as duas áreas (usuário e técnico) juntas, boa pra testar o
  fluxo inteiro.
- **`usuario.html`**: só a parte do usuário, que abre chamado.
- **`tecnico.html`**: só a parte do técnico, que pega e fecha chamado e acompanha a fila.

Toda a comunicação é por HTTP/JSON com a API em `http://127.0.0.1:8000` (o backend libera CORS,
por isso as telas funcionam até abrindo o arquivo direto). A fila de chamados abertos se atualiza
sozinha a cada 3 segundos (um `GET /tickets` em loop). Os chamados que o técnico está atendendo
ficam salvos no `localStorage` do navegador, então recarregar a página não perde o que estava em
atendimento naquela aba — mas a fonte da verdade é sempre o Redis, no backend.

Isso aqui é o esqueleto da Entrega 1: servidor respondendo na porta certa, fila enfileirando e
o frontend já consumindo a API. Os refinamentos vêm nas próximas entregas.

## Demonstração

Os prints abaixo foram tirados com o sistema rodando (backend e Redis no Docker, e o frontend
servido localmente).

### Tela do usuário — abrir chamado

![Tela do usuário](docs/img/01-usuario.png)

O usuário informa o nome e a descrição do problema e clica em "Abrir Chamado". Isso dispara um
`POST /tickets` e o chamado entra no fim da fila com status `OPEN`.

### Página única (usuário + técnico)

![Página index com a fila](docs/img/02-index-fila.png)

A `index.html` junta as duas áreas numa tela só, boa pra testar o fluxo inteiro. A fila de
chamados abertos, à direita, se atualiza sozinha a cada 3 segundos (`GET /tickets`).

### Tela do técnico — fila de chamados

![Tela do técnico com a fila](docs/img/03-tecnico-fila.png)

O técnico vê os chamados em ordem de chegada. Ao clicar em "Pegar Próximo Chamado", o primeiro
da fila é atribuído a ele através de `PATCH /tickets/next`.

### Tela do técnico — chamados em atendimento

![Chamados em atendimento](docs/img/05-tecnico-atendimento.png)

Cada chamado que o técnico pega vira um card próprio, com seu botão "Fechar Chamado"
(`PATCH /tickets/{id}/close`). Dá pra ter vários em atendimento ao mesmo tempo, refletindo o
que o backend permite (vários `IN_PROGRESS`).

### Documentação automática da API (Swagger)

![Swagger em /docs](docs/img/04-swagger.png)

O FastAPI gera essa documentação interativa em `http://127.0.0.1:8000/docs`. Ela lista todos os
endpoints e os schemas de entrada e saída (`TicketCreate`, `TicketAssign`, `TicketResponse`) e
ainda dá pra testar as rotas direto por ali.

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
├── docs/
│   ├── img/              # prints das telas usados neste README
│   ├── Contrato.md       # protocolo (também descrito aqui no README)
│   └── Arquitetura.md    # arquitetura (também descrita aqui no README)
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

## Protocolo de comunicação

A comunicação é toda por HTTP, trocando JSON nos dois sentidos. O servidor sobe na porta 8000,
então a base das URLs é `http://127.0.0.1:8000`. A separação de perfis aparece no protocolo: o
usuário só abre chamado e o técnico consome a fila (pega e fecha).

### Formato do chamado (TicketResponse)

Toda resposta que devolve um chamado usa o mesmo formato:

| Campo | Descrição |
|---|---|
| `ticket_id` | identificador único do chamado (gerado pelo servidor) |
| `usuario` | quem abriu |
| `descricao` | texto do problema |
| `status` | `OPEN`, `IN_PROGRESS` ou `CLOSED` |
| `timestamp_abertura` | data/hora de abertura (ISO 8601, UTC) |
| `tecnico` | técnico que pegou (vazio enquanto ninguém pegou) |
| `timestamp_atendimento` | quando o técnico pegou (vazio antes disso) |
| `timestamp_fechamento` | quando foi fechado (vazio antes disso) |

### Rotas

**`POST /tickets`** — abrir chamado (perfil Usuário)

Corpo: `{ "usuario": "joao", "descricao": "Notebook nao liga" }`

Resposta `201 Created` com o ticket recém-criado (status `OPEN`). Os dois campos são
obrigatórios; o servidor faz `strip()` e recusa string vazia ou só com espaços (responde `422`
apontando o campo).

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

**`GET /tickets`** — listar chamados abertos (qualquer perfil)

Resposta `200 OK` com a lista de chamados em status `OPEN`, na ordem de chegada. Se não houver
nenhum, devolve `[]`.

**`PATCH /tickets/next`** — pegar o próximo (perfil Técnico)

Corpo: `{ "tecnico": "maria" }`

Pega o primeiro da fila, marca como `IN_PROGRESS` e devolve `200 OK` com o ticket. Se a fila
estiver vazia, responde `404 Not Found`. Essa é a operação crítica da exclusividade: a retirada é
atômica no Redis (script Lua), então dois técnicos nunca recebem o mesmo chamado.

**`PATCH /tickets/{ticket_id}/close`** — fechar (perfil Técnico)

Fecha um chamado que está em atendimento. Resposta `200 OK`:

```json
{ "ticket_id": "8f3c1b2a-...", "status": "CLOSED" }
```

Se o ticket não existir ou não estiver em atendimento, responde `400 Bad Request`.

**`GET /health`** — serve só para testar se o servidor está no ar. Responde `{ "status": "ok" }`.

### Exemplo de uso (curl)

```bash
# usuario abre um chamado
curl -X POST http://127.0.0.1:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"usuario": "joao", "descricao": "Notebook nao liga"}'

# tecnico pega o proximo da fila
curl -X PATCH http://127.0.0.1:8000/tickets/next \
  -H "Content-Type: application/json" \
  -d '{"tecnico": "maria"}'

# tecnico fecha (use o ticket_id retornado acima)
curl -X PATCH http://127.0.0.1:8000/tickets/<ticket_id>/close
```

### Códigos de resposta

| Situação | Código |
|---|---|
| Chamado aberto com sucesso | 201 |
| Listagem, pegar ou fechar com sucesso | 200 |
| Fila vazia ao tentar pegar o próximo | 404 |
| Fechar um ticket inexistente ou que não está em atendimento | 400 |
| Corpo inválido (campo obrigatório faltando ou vazio) | 422 |

## Testes

Os testes ficam em `backend/tests` e usam o pytest. O `test_fila.py` cobre as regras centrais:

- abertura de ticket válido, timestamps ISO 8601 em UTC e rejeição de campos vazios;
- listagem e consumo em ordem FIFO;
- atribuição e fechamento com as mudanças de estado esperadas;
- fila vazia, ticket inexistente e fechamento em estado inválido;
- rejeição de técnico vazio sem retirar o ticket da fila;
- exclusividade com dois técnicos concorrendo pelo mesmo ticket;
- respostas HTTP `404`, `400` e `422` para operações inválidas.

Os testes da fila precisam de um Redis acessível; se não houver nenhum, são pulados em vez de
falhar. O `test_logging.py` valida que os logs são JSON e contêm os campos estruturados de
requisição, sem depender do Redis.

Com o stack do Docker no ar:

```bash
docker compose exec backend python -m pytest -v
```

Ou localmente, com o ambiente virtual ativado e um Redis rodando:

```bash
cd backend
python -m pytest -v
```

Na validação com Docker, a suíte completa terminou com `22 passed`. O teste concorrente de
exclusividade também foi repetido 10 vezes, sempre entregando o ticket para apenas um técnico.
