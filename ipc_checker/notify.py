"""Отправка уведомления об изменении статусов в Telegram (в личку через бота).

Токен бота и chat_id передаются в конструктор (из CLI-аргументов). Отправка —
через Bot API sendMessage. Никаких внешних зависимостей: только stdlib.
"""
import json
import urllib.error
import urllib.request


class TelegramNotifier:
    """Слать сообщения в Telegram через Bot API."""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send(self, text: str) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = json.dumps({"chat_id": self.chat_id, "text": text}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise RuntimeError(f"Telegram API HTTP {exc.code}: {detail}") from exc
        if not body.get("ok"):
            raise RuntimeError(f"Telegram API вернул ошибку: {body}")
