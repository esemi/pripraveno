"""Хранение прошлых статусов в JSON-файле рядом со скриптом."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


class StateStore:
    """Простое key->value хранилище: канон. номер заявки -> последний state."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: Dict[str, str] = {}

    def load(self) -> "StateStore":
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                # Битый стейт — считаем, что истории нет; перепишется на save.
                self._data = {}
        return self

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value

    def save(self) -> None:
        # Атомарная запись через временный файл рядом.
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp.replace(self._path)
