"""CLI для крона: проверить статусы заявок и напечатать изменения в stdout.

Номера заявок передаются позиционными аргументами. Каждый может быть в виде:
    OAM-12345/CC-2024              — просто заявка
    OAM-12345/CC-2024=ABCD12345    — заявка + номер визовой аппликации (zov), опционально

При изменении статуса относительно прошлого запуска строка «CHANGED …» уходит в stdout.
Крон сам разошлёт stdout по email через MAILTO. Первый запуск фиксирует базовый
статус и (по умолчанию) молчит — используй --notify-new чтобы печатать и его.
"""
import argparse
import sys
from pathlib import Path

from .client import CheckError, IpcClient, ProceedingNotFound
from .reference import Reference
from .state import StateStore

DEFAULT_STATE_PATH = Path(__file__).resolve().parent.parent / "state.json"


def _parse_entry(entry: str) -> tuple[Reference, str]:
    """'OAM-.../CC-2024' или 'OAM-.../CC-2024=ABCD12345' -> (Reference, visa_number)."""
    raw, _, visa = entry.partition("=")
    return Reference.parse(raw), visa.strip()


def _describe(state: str) -> str:
    """Человекочитаемое описание кода статуса."""
    return {
        "INPROGRESS": "в обработке",
        "APPROVED": "одобрено",
    }.get(state, f"решение принято ({state})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ipc_checker",
        description="Проверка статуса заявок на ipc.gov.cz с уведомлением об изменениях.",
    )
    parser.add_argument(
        "numbers",
        nargs="+",
        help="Номера заявок (OAM-.../CC-2024[=ZOV]), хотя бы один",
    )
    parser.add_argument(
        "--state",
        default=str(DEFAULT_STATE_PATH),
        help=f"Путь к JSON-стейту (по умолчанию {DEFAULT_STATE_PATH})",
    )
    parser.add_argument(
        "--notify-new",
        action="store_true",
        help="Печатать статус и при первом появлении номера (по умолчанию — молча запомнить)",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Показывать окно браузера (для отладки)",
    )
    args = parser.parse_args(argv)

    # Разбираем и валидируем заранее, чтобы не поднимать браузер зря.
    entries: list[tuple[Reference, str]] = []
    for raw in args.numbers:
        try:
            entries.append(_parse_entry(raw))
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

    store = StateStore(Path(args.state)).load()
    errors = 0

    with IpcClient(headless=not args.no_headless) as client:
        for ref, visa in entries:
            key = ref.canonical()
            try:
                result = client.check(ref, visa)
            except ProceedingNotFound:
                print(f"WARN: заявка {key} не найдена (ENTITY_NOT_EXIST)", file=sys.stderr)
                errors += 1
                continue
            except CheckError as exc:
                print(f"ERROR: {key}: {exc}", file=sys.stderr)
                errors += 1
                continue

            prev = store.get(key)
            store.set(key, result.state)

            if prev is None:
                if args.notify_new:
                    print(f"NEW     {key}: {_describe(result.state)}")
            elif prev != result.state:
                print(f"CHANGED {key}: {_describe(prev)} -> {_describe(result.state)}")

    store.save()

    # Есть ошибки, но стейт по успешным заявкам мы всё равно сохранили.
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
