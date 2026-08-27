"""Разбор референс-номера заявки формата OAM-12345[-6]/CC-2024.

Формат подсмотрен в бандле сайта:
    to_string:   `${oam}-${referenceNumber}${suffix ? '-'+suffix : ''}/${category}-${year}`
    from_string: split('/') -> [left, right]; left.split('-') -> [oam, ref, suffix];
                 right.split('-') -> [category, year]
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Полный номер: OAM-<цифры>[-<суффикс>]/<2 буквы>-<4 цифры>
_FULL_RE = re.compile(
    r"^OAM-(?P<ref>\d+)(?:-(?P<suffix>[^/]+))?/(?P<category>[A-Z]{2})-(?P<year>\d{4})$"
)


@dataclass(frozen=True)
class Reference:
    """Разобранный номер заявки."""

    reference_number: str  # idCj в API
    category: str          # database в API (напр. CC)
    year: str              # year в API
    suffix: str = ""       # additionalSuffix, в запрос статуса не идёт

    @classmethod
    def parse(cls, raw: str) -> "Reference":
        """Разобрать строку вида 'OAM-12345/CC-2024' или 'OAM-12345-6/CC-2024'."""
        raw = raw.strip()
        m = _FULL_RE.match(raw)
        if not m:
            raise ValueError(
                f"Неверный формат номера {raw!r}. "
                f"Ожидается OAM-<цифры>[-<суффикс>]/<2 буквы>-<4 цифры>, "
                f"например OAM-12345/CC-2024"
            )
        return cls(
            reference_number=m.group("ref"),
            category=m.group("category"),
            year=m.group("year"),
            suffix=m.group("suffix") or "",
        )

    def canonical(self) -> str:
        """Обратно в каноничную строку (как показывает сайт)."""
        suffix = f"-{self.suffix}" if self.suffix else ""
        return f"OAM-{self.reference_number}{suffix}/{self.category}-{self.year}"

    def __str__(self) -> str:  # noqa: D105
        return self.canonical()
