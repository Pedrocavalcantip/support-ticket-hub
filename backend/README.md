# Backend

API do projeto **support-ticket-hub**, feita com FastAPI.

## Rodar com Docker (jeito mais facil)

Precisa do Docker e do Docker Compose instalados. Na raiz do projeto:

```bash
docker compose up --build
```

Isso sobe o Redis e o backend juntos. A API fica em http://127.0.0.1:8000 e a
documentacao automatica em http://127.0.0.1:8000/docs. Para parar, use `docker compose down`.

As instrucoes abaixo, com ambiente virtual, sao uma alternativa caso voce nao queira usar
Docker. Nesse caso voce precisa de um Redis rodando por conta propria, porque a API conecta
no Redis assim que inicia. Da pra subir so o Redis com `docker compose up -d redis`.

## Requisitos

- Python 3.11 ou superior
- Git

## Como rodar no Linux/macOS

Clone o projeto e entre na pasta do backend:

```bash
git clone <URL_DO_REPOSITORIO>
cd support-ticket-hub/backend
```

Crie e ative o ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instale as dependencias:

```bash
pip install -r requirements.txt
```

Rode a API:

```bash
uvicorn app.main:app --reload
```

## Como rodar no Windows PowerShell

Clone o projeto e entre na pasta do backend:

```powershell
git clone <URL_DO_REPOSITORIO>
cd support-ticket-hub\backend
```

Crie e ative o ambiente virtual:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Instale as dependencias:

```powershell
pip install -r requirements.txt
```

Rode a API:

```powershell
uvicorn app.main:app --reload
```

## Testando

Com o servidor rodando, acesse:

```text
http://127.0.0.1:8000/health
```

A resposta esperada e:

```json
{"status":"ok"}
```

A documentacao automatica do FastAPI fica em:

```text
http://127.0.0.1:8000/docs
```

## Testes

Os testes ficam em `backend/tests` e usam o pytest. Os testes do core em `test_fila.py` precisam
de um Redis acessivel; se nao houver nenhum, sao pulados em vez de falhar. Eles cobrem abertura,
timestamps, FIFO, consumo, fechamento, entradas invalidas e exclusividade concorrente. O
`test_api.py` valida as respostas HTTP 404, 400 e 422. O
`test_logging.py` nao depende do Redis. Com o stack do Docker no ar:

```bash
docker compose exec backend python -m pytest -v
```

Ou localmente, com o ambiente virtual ativado e um Redis rodando:

```bash
cd backend
python -m pytest -v
```

## Observacao para VS Code

Se aparecer erro no import do FastAPI, selecione o interpretador Python do ambiente virtual:

```text
backend/.venv/bin/python
```
