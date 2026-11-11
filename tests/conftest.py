import os

import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        if "live" in item.keywords and os.getenv("RUN_LIVE") != "1":
            item.add_marker(pytest.mark.skip(reason="RUN_LIVE=1 enables real marketplace requests"))
        if "llm" in item.keywords and os.getenv("RUN_LLM") != "1":
            item.add_marker(pytest.mark.skip(reason="RUN_LLM=1 enables real paid model calls"))
