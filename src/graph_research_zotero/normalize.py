from __future__ import annotations

import re
from typing import Any


def unwrap_singleton(obj: Any) -> Any:
    while isinstance(obj, dict) and len(obj) == 1:
        if "data" in obj:
            obj = obj["data"]
        elif "item" in obj:
            obj = obj["item"]
        else:
            break
    return obj


def field(data: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        value = data.get(name)
        if value not in (None, "", []):
            return value
    nested = data.get("data")
    if isinstance(nested, dict):
        for name in names:
            value = nested.get(name)
            if value not in (None, "", []):
                return value
    return default


def normalize_doi(value: Any) -> str:
    if not value:
        return ""
    doi = str(value).strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)
    return doi.strip().lower()


def normalize_authors(creators: Any) -> list[str]:
    if not isinstance(creators, list):
        return []
    result: list[str] = []
    for creator in creators:
        if isinstance(creator, str):
            name = creator.strip()
        elif isinstance(creator, dict):
            if creator.get("name"):
                name = str(creator["name"]).strip()
            else:
                first = str(creator.get("firstName", "")).strip()
                last = str(creator.get("lastName", "")).strip()
                name = " ".join(part for part in (first, last) if part)
        else:
            continue
        if name:
            result.append(name)
    return result


def normalize_tags(tags: Any) -> list[str]:
    if not isinstance(tags, list):
        return []
    result: list[str] = []
    for tag in tags:
        if isinstance(tag, str):
            value = tag
        elif isinstance(tag, dict):
            value = str(tag.get("tag", ""))
        else:
            continue
        value = value.strip()
        if value:
            result.append(value)
    return result


def normalize_year(value: Any) -> int | None:
    if value is None:
        return None
    match = re.search(r"\b(18|19|20|21)\d{2}\b", str(value))
    return int(match.group(0)) if match else None


def extract_item_key(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    for key in ("itemKey", "key"):
        value = item.get(key)
        if value:
            return str(value)
    nested = item.get("data")
    if isinstance(nested, dict):
        for key in ("itemKey", "key"):
            value = nested.get(key)
            if value:
                return str(value)
    return None


def extract_item_keys(payload: Any) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    def visit(obj: Any) -> None:
        if isinstance(obj, dict):
            key = extract_item_key(obj)
            if key and key not in seen:
                seen.add(key)
                out.append(key)
            for name in ("data", "items", "results"):
                if name in obj:
                    visit(obj[name])
        elif isinstance(obj, list):
            for child in obj:
                visit(child)

    visit(payload)
    return out
