# conftest.py — configuração global do pytest para a suite de testes
#
# asyncio_mode = "auto":  permite que fixtures async (como `sse_app`) sejam
# usadas em testes @pytest.mark.asyncio sem precisar marcar cada fixture
# individualmente.  Os testes síncronos em test_api.py e test_fila.py não são
# afetados — o pytest-asyncio ignora funções sync.

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "asyncio: marca um teste como coroutine a ser executada pelo pytest-asyncio",
    )
