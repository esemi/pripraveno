"""CLI для крона: проверить статусы заявок, вывести их в stdout и слать в Telegram
при изменении статуса.

Номера заявок передаются позиционными аргументами. Каждый может быть в виде:
    OAM-12345/CC-2024              — просто заявка
    OAM-12345/CC-2024=ABCD12345    — заявка + номер визовой аппликации (zov), опционально

Каждый прогон печатает текущий статус каждой заявки в stdout. Если статус
какой-то заявки изменился относительно прошлого запуска — уходит сообщение в
Telegram (в личку через бота, --bot-token/--chat-id). Без этих аргументов
изменения только печатаются в stdout.
"""
import argparse
import sys
from pathlib import Path

from .client import CheckError, IpcClient, ProceedingNotFound
from .notify import TelegramNotifier
from .reference import Reference
from .state import StateStore

STATE_PATH = Path(__file__).resolve().parent.parent / "state.json"


def _parse_entry(entry: str) -> tuple[Reference, str]:
    """'OAM-.../CC-2024' или 'OAM-.../CC-2024=ABCD12345' -> (Reference, visa_number)."""
    raw, _, visa = entry.partition("=")
    return Reference.parse(raw), visa.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ipc_checker",
        description="Проверка статуса заявок на ipc.gov.cz.",
    )
    parser.add_argument(
        "numbers",
        nargs="+",
        help="Номера заявок (OAM-.../CC-2024[=ZOV]), хотя бы один",
    )
    parser.add_argument(
        "--bot-token",
        help="Токен Telegram-бота для уведомлений об изменении статуса",
    )
    parser.add_argument(
        "--chat-id",
        help="Telegram chat_id получателя (личка)",
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

    store = StateStore(STATE_PATH).load()
    errors = 0
    changes: list[str] = []  # только реально изменившиеся заявки — для Telegram

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

            if prev is not None and prev != result.state:
                line = f"{key}: {result.state} (было {prev})"
                changes.append(line)
                print(line)
            else:
                print(f"{key}: {result.state}")

    store.save()

    if changes:
        _notify(changes, args.bot_token, args.chat_id)

    # Есть ошибки, но стейт по успешным заявкам мы всё равно сохранили.
    return 1 if errors else 0


def _notify(changes: list[str], bot_token: str | None, chat_id: str | None) -> None:
    """Отправить сообщение об изменениях в Telegram; без токена/chat_id или при
    ошибке — не падать."""
    if not (bot_token and chat_id):
        print(
            "INFO: статус изменился, но --bot-token/--chat-id не заданы — "
            "уведомление в Telegram не отправлено",
            file=sys.stderr,
        )
        return

    text = "IPC: изменился статус заявки\n\n" + "\n".join(changes)
    try:
        TelegramNotifier(bot_token, chat_id).send(text)
    except Exception as exc:  # noqa: BLE001 — уведомление не должно ронять прогон
        print(f"ERROR: не удалось отправить в Telegram: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
