import json
import os
from functools import lru_cache


@lru_cache(maxsize=1)
def load_schema():
    """Load the bundled GitLab CI JSON schema."""
    schema_path = os.path.join(os.path.dirname(__file__), "ci.json")
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise RuntimeError(f"Bundled schema not found at {schema_path}")
