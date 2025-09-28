import json
from pathlib import Path

TOKEN_FILE = Path("strava_tokens.json")


def load_tokens() -> dict:
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    return {}


def save_tokens(tokens: dict):
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
