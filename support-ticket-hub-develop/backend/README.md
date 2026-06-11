# Backend

API do projeto **support-ticket-hub**, feita com FastAPI.

## Requisitos

- Python 3.12 ou superior
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

## Observacao para VS Code

Se aparecer erro no import do FastAPI, selecione o interpretador Python do ambiente virtual:

```text
backend/.venv/bin/python
```
