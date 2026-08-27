"""Клиент к API статуса заявок ipc.gov.cz.

Эндпоинт защищён reCAPTCHA v3: сервер валидирует токен серверно (без токена — 400).
Токен генерит только Google-скрипт в реальном браузере на домене ipc.gov.cz,
поэтому используем Playwright — открываем страницу формы, дёргаем grecaptcha.execute
её же site-key'ом, а сам статус-запрос шлём напрямую из контекста страницы (fetch),
чтобы не возиться с UI. Один прогрев браузера — много запросов.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from types import TracebackType
from typing import Optional

from playwright.sync_api import Page, sync_playwright

from .reference import Reference

STATUS_PAGE_URL = "https://ipc.gov.cz/en/status-of-your-application/"
API_PATH = "/api/ip/external/proceedings/state/cj/zov"
# Действие reCAPTCHA v3, которое использует сама форма (см. executeRecaptcha("proceedings")).
RECAPTCHA_ACTION = "proceedings"


class ProceedingNotFound(Exception):
    """Заявка с таким номером не найдена (ENTITY_NOT_EXIST)."""


class CheckError(Exception):
    """Прочая ошибка запроса статуса (сеть, капча, неожиданный ответ)."""


@dataclass
class ProceedingState:
    """Ответ API по одной заявке."""

    state: str            # INPROGRESS | APPROVED | <иное> (иное трактуем как решение принято)
    identification: str   # как сервер идентифицирует заявку (обычно номер)
    raw: dict             # сырой ответ на всякий случай


# JS-хелпер, выполняемый в контексте страницы формы.
# Достаёт свежий reCAPTCHA-токен через тот же grecaptcha, что и форма,
# затем шлёт POST на API и возвращает {ok, status, body}.
_FETCH_JS = """
async ({apiPath, action, query, siteKey}) => {
  const token = await new Promise((resolve, reject) => {
    if (!window.grecaptcha || !window.grecaptcha.execute) {
      reject('grecaptcha not loaded');
      return;
    }
    grecaptcha.ready(() => {
      grecaptcha.execute(siteKey, {action}).then(resolve).catch(reject);
    });
  });
  const url = apiPath + '?' + query;
  const resp = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({captcha: token}),
  });
  const text = await resp.text();
  return {status: resp.status, body: text};
}
"""

# JS для добывания site-key из уже загруженного grecaptcha-конфига страницы.
_SITEKEY_JS = """
() => {
  try {
    const cfg = window.___grecaptcha_cfg;
    if (!cfg || !cfg.clients) return null;
    for (const client of Object.values(cfg.clients)) {
      const stack = [client];
      while (stack.length) {
        const cur = stack.pop();
        if (!cur || typeof cur !== 'object') continue;
        if (typeof cur.sitekey === 'string') return cur.sitekey;
        for (const v of Object.values(cur)) {
          if (v && typeof v === 'object') stack.push(v);
        }
      }
    }
  } catch (e) {}
  return null;
}
"""


class IpcClient:
    """Держит открытый браузер и шлёт запросы статуса через контекст страницы формы."""

    def __init__(self, headless: bool = True, timeout_ms: int = 30_000) -> None:
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._pw = None
        self._browser = None
        self._page: Optional[Page] = None
        self._site_key: Optional[str] = None

    def __enter__(self) -> "IpcClient":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self._headless)
        self._page = self._browser.new_page()
        self._page.set_default_timeout(self._timeout_ms)
        self._page.goto(STATUS_PAGE_URL, wait_until="networkidle")
        self._site_key = self._resolve_site_key()
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()

    def _resolve_site_key(self) -> str:
        assert self._page is not None
        # grecaptcha грузится асинхронно — подождём, пока конфиг появится.
        self._page.wait_for_function("() => !!window.grecaptcha", timeout=self._timeout_ms)
        site_key = self._page.evaluate(_SITEKEY_JS)
        if not site_key:
            raise CheckError(
                "Не удалось достать reCAPTCHA site-key со страницы формы. "
                "Возможно, изменилась разметка сайта."
            )
        return site_key

    def check(self, ref: Reference, visa_number: str = "") -> ProceedingState:
        """Запросить статус одной заявки."""
        assert self._page is not None
        query = (
            f"idCj={ref.reference_number}"
            f"&database={ref.category}"
            f"&year={ref.year}"
            f"&zov={visa_number}"
        )
        result = self._page.evaluate(
            _FETCH_JS,
            {
                "apiPath": API_PATH,
                "action": RECAPTCHA_ACTION,
                "query": query,
                "siteKey": self._site_key,
            },
        )
        status = result["status"]
        try:
            body = json.loads(result["body"]) if result["body"] else {}
        except json.JSONDecodeError:
            raise CheckError(f"Неожиданный ответ ({status}): {result['body'][:200]!r}")

        if status == 200:
            return ProceedingState(
                state=body.get("state", ""),
                identification=body.get("identification", ""),
                raw=body,
            )

        message = body.get("message") if isinstance(body, dict) else None
        if message == "ENTITY_NOT_EXIST":
            raise ProceedingNotFound(str(ref))
        raise CheckError(f"HTTP {status}: {message or result['body'][:200]}")
