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
