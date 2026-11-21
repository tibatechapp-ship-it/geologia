"""Validated read-only engine catalog. Registry entries do not imply installed integrations."""
import json
from pathlib import Path

_PATH = Path(__file__).parent / "data" / "engines.json"


def _load() -> list[dict]:
    payload = json.loads(_PATH.read_text(encoding="utf-8"))
    cards = payload.get("engines")
    if not isinstance(cards, list):
        raise RuntimeError("engine registry must contain an engines list")
    ids = [card.get("engine_id") for card in cards]
    if any(not isinstance(item, str) or not item for item in ids):
        raise RuntimeError("engine registry contains an invalid engine_id")
    if len(ids) != len(set(ids)):
        raise RuntimeError("engine registry contains duplicate engine_id values")
    for card in cards:
        if card.get("status") != "planned" or card.get("license_status") != "unverified":
            raise RuntimeError("unverified engines must remain planned and license-unverified")
    return cards


ENGINES = _load()


def list_engines(domain: str | None = None) -> list[dict]:
    return [card for card in ENGINES if domain is None or card["domain"] == domain]


def get_engine(engine_id: str) -> dict | None:
    return next((card for card in ENGINES if card["engine_id"] == engine_id), None)
