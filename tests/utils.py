""" test utils — shared resource loaders for the test suite.

Pure helpers only (no `TestClient`): the OpenAI-era server contract — including
`/health` and the lifespan boot — is covered portably in
`tests/test_server_contract.py` without Starlette's `TestClient`.
"""

import os
import json


def get_resource_path(name: str, extension: str) -> str:
    "get resources path"
    current_path = os.path.dirname(__file__)
    path = os.path.join(current_path, f"./resources/{name}")
    return f"{path}.{extension}"


def load_resource(name: str) -> dict:
    "load resource"
    result = {}

    with open(get_resource_path(name, "wav"), "br") as file:
        result["audio"] = file.read()

    with open(get_resource_path(name, "json"), "r", encoding="utf-8") as file:
        result["expected"] = json.load(file)

    return result
