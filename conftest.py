import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
# Make the sibling aacode checkout (recommended) and this project importable.
for path in (ROOT.parent, ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# The 1.7.7 vendored framework copy is archived for reference only.
collect_ignore_glob = ["_legacy_vendored_1.7.7/*"]

pytest_plugins = ("pytest_asyncio",)


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as an asyncio test.")


@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()
