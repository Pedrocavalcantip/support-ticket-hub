import json
import logging

from app.core.logging_config import JsonFormatter


def test_json_formatter_inclui_campos_estruturados():
    record = logging.LogRecord(
        name="support_ticket_hub.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="http_request",
        args=(),
        exc_info=None,
    )
    record.method = "POST"
    record.route = "/tickets"
    record.status_code = 201
    record.duration_ms = 3.25

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["event"] == "http_request"
    assert payload["method"] == "POST"
    assert payload["route"] == "/tickets"
    assert payload["status_code"] == 201
    assert payload["duration_ms"] == 3.25
    assert payload["timestamp"]
