import json
from pathlib import Path

TOKEN_FILE = Path("strava_tokens.json")


def load_tokens() -> dict:
    if TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE, "r") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            # If file is corrupted, return empty dict and let save_tokens recreate it
            return {}
    return {}


def save_tokens(tokens: dict):
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
