from __future__ import annotations

import argparse
import asyncio
import sys
import time
from collections import defaultdict
from typing import Any

try:
    import httpx
except ModuleNotFoundError:
    print("Dependencia 'httpx' nao encontrada.")
    print("Instale as dependencias do backend com:")
    print("  python -m pip install -r backend/requirements.txt")
    sys.exit(1)


DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TICKETS = 50
DEFAULT_TECHNICIANS = 10
DEFAULT_TIMEOUT = 10.0


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use um numero inteiro positivo") from exc

    if number <= 0:
        raise argparse.ArgumentTypeError("use um numero maior que zero")

    return number


def positive_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use um numero positivo") from exc

    if number <= 0:
        raise argparse.ArgumentTypeError("use um numero maior que zero")

    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Teste de carga concorrente para a API HTTP de tickets."
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"URL base da API. Padrao: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--tickets",
        type=positive_int,
        default=DEFAULT_TICKETS,
        help=f"Quantidade de tickets a criar. Padrao: {DEFAULT_TICKETS}",
    )
    parser.add_argument(
        "--technicians",
        type=positive_int,
        default=DEFAULT_TECHNICIANS,
        help=f"Quantidade de tecnicos concorrentes. Padrao: {DEFAULT_TECHNICIANS}",
    )
    parser.add_argument(
        "--timeout",
        type=positive_float,
        default=DEFAULT_TIMEOUT,
        help=f"Timeout por requisicao, em segundos. Padrao: {DEFAULT_TIMEOUT}",
    )
    return parser


def decode_json(response: httpx.Response) -> tuple[Any | None, str]:
    if not response.content:
        return None, ""

    try:
        return response.json(), ""
    except ValueError:
        return None, "resposta nao e JSON valido"


def payload_summary(payload: Any) -> str:
    if isinstance(payload, dict):
        detail = payload.get("detail")
        return str(detail if detail is not None else payload)

    if isinstance(payload, list):
        return f"lista com {len(payload)} itens"

    if payload is None:
        return "sem corpo de resposta"

    return str(payload)


def request_error_result(
    operation: str,
    index: int,
    exc: httpx.RequestError,
) -> dict[str, Any]:
    return {
        "operation": operation,
        "index": index,
        "status_code": 0,
        "ticket_id": "",
        "technician": "",
        "empty_queue": False,
        "request_error": True,
        "error": f"{type(exc).__name__}: {exc}",
    }


async def get_pending_tickets(client: httpx.AsyncClient) -> dict[str, Any]:
    try:
        response = await client.get("/tickets")
    except httpx.RequestError as exc:
        result = request_error_result("GET /tickets", 0, exc)
        result["tickets"] = []
        return result

    payload, json_error = decode_json(response)
    result = {
        "operation": "GET /tickets",
        "index": 0,
        "status_code": response.status_code,
        "tickets": [],
        "request_error": False,
        "error": "",
    }

    if response.status_code != 200:
        result["error"] = (
            f"HTTP {response.status_code} em GET /tickets: {payload_summary(payload)}"
        )
        return result

    if json_error:
        result["error"] = json_error
        return result

    if not isinstance(payload, list):
        result["error"] = "GET /tickets nao retornou uma lista"
        return result

    result["tickets"] = payload
    return result


async def create_ticket(client: httpx.AsyncClient, index: int) -> dict[str, Any]:
    payload = {
        "usuario": f"usuario-load-{index:03d}",
        "descricao": f"Chamado criado pelo teste de carga concorrente #{index:03d}",
    }

    try:
        response = await client.post("/tickets", json=payload)
    except httpx.RequestError as exc:
        return request_error_result("POST /tickets", index, exc)

    response_payload, json_error = decode_json(response)
    result = {
        "operation": "POST /tickets",
        "index": index,
        "status_code": response.status_code,
        "ticket_id": "",
        "technician": "",
        "empty_queue": False,
        "request_error": False,
        "error": "",
    }

    if response.status_code != 201:
        result["error"] = (
            f"HTTP {response.status_code} em POST /tickets: "
            f"{payload_summary(response_payload)}"
        )
        return result

    if json_error:
        result["error"] = json_error
        return result

    if not isinstance(response_payload, dict):
        result["error"] = "POST /tickets nao retornou um objeto JSON"
        return result

    ticket_id = response_payload.get("ticket_id")
    if not ticket_id:
        result["error"] = "POST /tickets retornou 201 sem ticket_id"
        return result

    result["ticket_id"] = str(ticket_id)
    return result


async def consume_ticket(
    client: httpx.AsyncClient,
    index: int,
    technician: str,
) -> dict[str, Any]:
    try:
        response = await client.patch("/tickets/next", json={"tecnico": technician})
    except httpx.RequestError as exc:
        result = request_error_result("PATCH /tickets/next", index, exc)
        result["technician"] = technician
        return result

    response_payload, json_error = decode_json(response)
    result = {
        "operation": "PATCH /tickets/next",
        "index": index,
        "status_code": response.status_code,
        "ticket_id": "",
        "technician": technician,
        "empty_queue": False,
        "request_error": False,
        "error": "",
    }

    if response.status_code == 404:
        result["empty_queue"] = True
        return result

    if response.status_code != 200:
        result["error"] = (
            f"HTTP {response.status_code} em PATCH /tickets/next: "
            f"{payload_summary(response_payload)}"
        )
        return result

    if json_error:
        result["error"] = json_error
        return result

    if not isinstance(response_payload, dict):
        result["error"] = "PATCH /tickets/next nao retornou um objeto JSON"
        return result

    ticket_id = response_payload.get("ticket_id")
    if not ticket_id:
        result["error"] = "PATCH /tickets/next retornou 200 sem ticket_id"
        return result

    result["ticket_id"] = str(ticket_id)
    return result


def has_request_error(results: list[dict[str, Any]]) -> bool:
    return any(result.get("request_error") for result in results)


def first_request_error(results: list[dict[str, Any]]) -> str:
    for result in results:
        if result.get("request_error"):
            return str(result.get("error", "erro de conexao"))
    return "erro de conexao"


def print_api_unavailable(base_url: str, detail: str) -> None:
    print(f"Nao foi possivel conectar na API em {base_url}.")
    print("Verifique se o backend e o Redis estao rodando com:")
    print("  docker compose up --build")
    print(f"Detalhe: {detail}")


def print_failures(title: str, failures: list[dict[str, Any]], limit: int = 5) -> None:
    if not failures:
        return

    print(f"\n{title}:")
    for failure in failures[:limit]:
        index = failure.get("index", "?")
        error = failure.get("error") or f"HTTP {failure.get('status_code')}"
        print(f"  - #{index}: {error}")

    remaining = len(failures) - limit
    if remaining > 0:
        print(f"  - ... mais {remaining} falha(s)")


def duplicate_ticket_ids(
    consume_results: list[dict[str, Any]],
) -> dict[str, list[str]]:
    technicians_by_ticket: dict[str, list[str]] = defaultdict(list)

    for result in consume_results:
        ticket_id = result.get("ticket_id")
        if ticket_id:
            technicians_by_ticket[str(ticket_id)].append(
                str(result.get("technician", ""))
            )

    return {
        ticket_id: technicians
        for ticket_id, technicians in technicians_by_ticket.items()
        if len(technicians) > 1
    }


def ticket_ids_from_state(tickets: list[Any]) -> set[str]:
    ids: set[str] = set()
    for ticket in tickets:
        if isinstance(ticket, dict) and ticket.get("ticket_id"):
            ids.add(str(ticket["ticket_id"]))
    return ids


async def run_load_test(args: argparse.Namespace) -> int:
    base_url = args.base_url.rstrip("/")
    started_at = time.perf_counter()
    max_connections = max(20, args.tickets + args.technicians + 10)

    limits = httpx.Limits(
        max_connections=max_connections,
        max_keepalive_connections=max_connections,
    )
    timeout = httpx.Timeout(args.timeout)

    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=timeout,
        limits=limits,
        trust_env=False,
    ) as client:
        initial_state = await get_pending_tickets(client)
        if initial_state.get("request_error"):
            print_api_unavailable(base_url, str(initial_state.get("error")))
            return 2

        if initial_state.get("error"):
            print(str(initial_state["error"]))
            return 1

        initial_pending = len(initial_state["tickets"])

        create_tasks = [
            create_ticket(client, index)
            for index in range(1, args.tickets + 1)
        ]
        create_results = await asyncio.gather(*create_tasks)

        if has_request_error(create_results):
            print_api_unavailable(base_url, first_request_error(create_results))
            return 2

        consumption_requests = initial_pending + args.tickets + args.technicians
        consume_tasks = []
        for index in range(1, consumption_requests + 1):
            technician_number = ((index - 1) % args.technicians) + 1
            technician = f"tecnico-load-{technician_number:03d}"
            consume_tasks.append(consume_ticket(client, index, technician))

        consume_results = await asyncio.gather(*consume_tasks)

        if has_request_error(consume_results):
            print_api_unavailable(base_url, first_request_error(consume_results))
            return 2

        final_state = await get_pending_tickets(client)
        if final_state.get("request_error"):
            print_api_unavailable(base_url, str(final_state.get("error")))
            return 2

    elapsed = time.perf_counter() - started_at

    created_ok = [
        result
        for result in create_results
        if result["status_code"] == 201 and result["ticket_id"] and not result["error"]
    ]
    create_failures = [
        result
        for result in create_results
        if result["status_code"] != 201 or result["error"]
    ]

    assigned = [
        result
        for result in consume_results
        if result["status_code"] == 200 and result["ticket_id"] and not result["error"]
    ]
    empty_queue = [
        result
        for result in consume_results
        if result["status_code"] == 404 and result["empty_queue"] and not result["error"]
    ]
    consume_failures = [
        result
        for result in consume_results
        if result["status_code"] not in (200, 404) or result["error"]
    ]

    duplicates = duplicate_ticket_ids(consume_results)
    created_ids = {result["ticket_id"] for result in created_ok}
    final_tickets = final_state.get("tickets", [])
    final_pending_ids = ticket_ids_from_state(final_tickets)
    created_still_pending = sorted(created_ids & final_pending_ids)

    final_state_error = str(final_state.get("error", ""))
    success = (
        len(created_ok) == args.tickets
        and not create_failures
        and not consume_failures
        and not duplicates
        and not final_state_error
        and not created_still_pending
    )

    print("=== Teste de concorrencia HTTP + Redis ===")
    print(f"API: {base_url}")
    print(f"Tickets solicitados para criacao: {args.tickets}")
    print(f"Tecnicos concorrentes: {args.technicians}")
    if initial_pending:
        print(f"Tickets que ja estavam abertos antes do teste: {initial_pending}")

    print("\nResumo:")
    print(f"- Tickets criados: {len(created_ok)}/{args.tickets}")
    print(f"- Requisicoes de consumo feitas por tecnicos: {len(consume_results)}")
    print(f"- Tickets atribuidos: {len(assigned)}")
    print(f"- Respostas de fila vazia: {len(empty_queue)}")
    print(f"- Duplicidade de ticket_id: {'SIM' if duplicates else 'NAO'}")
    print(f"- Tickets abertos ao final (GET /tickets): {len(final_tickets)}")
    print(f"- Tempo total de execucao: {elapsed:.2f}s")

    if duplicates:
        print("\nDuplicidades encontradas:")
        for ticket_id, technicians in list(duplicates.items())[:5]:
            technicians_text = ", ".join(technicians)
            print(f"  - {ticket_id}: {technicians_text}")

    if created_still_pending:
        print("\nTickets criados pelo teste que ainda ficaram na fila:")
        for ticket_id in created_still_pending[:5]:
            print(f"  - {ticket_id}")
        remaining = len(created_still_pending) - 5
        if remaining > 0:
            print(f"  - ... mais {remaining} ticket(s)")

    print_failures("Falhas na criacao de tickets", create_failures)
    print_failures("Falhas no consumo de tickets", consume_failures)

    if final_state_error:
        print(f"\nFalha ao consultar estado final da fila: {final_state_error}")

    print(f"\nStatus final: {'SUCESSO' if success else 'FALHA'}")
    return 0 if success else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        return asyncio.run(run_load_test(args))
    except KeyboardInterrupt:
        print("\nExecucao interrompida pelo usuario.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
