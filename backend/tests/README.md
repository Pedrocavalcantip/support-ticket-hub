# Testes do backend

A suíte usa pytest e cobre:

- abertura, timestamps ISO 8601 em UTC e validação dos campos do ticket;
- listagem e retirada em ordem FIFO;
- atribuição e fechamento de chamados;
- fila vazia e tentativas inválidas;
- técnico vazio sem consumo do ticket;
- exclusividade quando dois técnicos disputam o mesmo chamado;
- respostas HTTP `404`, `400` e `422` para operações inválidas;
- formato JSON dos logs estruturados.

Com o Docker Compose em execução, rode na raiz do repositório:

```bash
docker compose exec backend python -m pytest -v
```
