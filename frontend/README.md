# Frontend

As telas são feitas em HTML, CSS e JavaScript puro, sem framework e sem etapa de build.
Cada arquivo `.html` já traz o estilo e o script dentro dele, então é só abrir no navegador.
Toda a comunicação com o servidor é por HTTP, mandando e recebendo JSON, batendo na API que
roda em `http://127.0.0.1:8000`. O backend libera CORS, por isso as telas funcionam mesmo
abrindo o arquivo direto.

## Telas

- **`index.html`**: página única com as duas áreas juntas (usuário e técnico). Serve pra
  testar o fluxo inteiro numa tela só.
- **`usuario.html`**: só a parte do usuário, que abre chamado.
- **`tecnico.html`**: só a parte do técnico, que pega e fecha chamado e acompanha a fila.

## O que cada ação faz no backend

A separação de perfis do protocolo aparece direto aqui: o usuário só abre, o técnico
consome. Cada botão dispara uma chamada à API:

| Ação na tela | Requisição |
|---|---|
| Abrir chamado (usuário) | `POST /tickets` com `{ usuario, descricao }` |
| Listar a fila de abertos | `GET /tickets` |
| Pegar o próximo (técnico) | `PATCH /tickets/next` com `{ tecnico }` |
| Fechar um chamado (técnico) | `PATCH /tickets/{id}/close` |

Antes de enviar um chamado, o frontend valida se o usuário foi preenchido e se a descrição
tem pelo menos 5 caracteres. No backend, a regra principal do protocolo é recusar campos
obrigatórios vazios.

O detalhe de cada rota (payload, resposta e erros) está em
[../docs/Contrato.md](../docs/Contrato.md).

## Como a tela se comporta

- **Fila atualizando sozinha**: a lista de chamados abertos é recarregada a cada 3 segundos
  (um `GET /tickets` em loop), então quando alguém abre um chamado ele aparece pros técnicos
  sem precisar dar refresh.
- **Chamados em atendimento em lista**: quando o técnico pega um chamado, ele vira um card na
  área "Chamados em Atendimento", cada um com seu próprio botão de fechar. Dá pra ter vários
  ao mesmo tempo, refletindo o que o backend permite (vários `IN_PROGRESS`). Pegar o próximo
  não substitui nem fecha o anterior.
- **Memória da sessão**: os chamados que o técnico está atendendo (e o ID dele) ficam salvos
  no `localStorage` do navegador, então recarregar a página não perde o que estava em
  atendimento naquela tela.

Vale lembrar que esse "em atendimento" guardado no navegador é só uma visão local daquela
aba. A fonte da verdade é sempre o Redis, no backend.

## Como rodar

Com o backend no ar (veja o [README principal](../README.md)), basta abrir
`frontend/index.html` no navegador. Se o navegador travar alguma coisa por estar abrindo via
`file://`, sirva a pasta como site estático:

```bash
cd frontend
python -m http.server 3000
```

e acesse `http://localhost:3000`.
