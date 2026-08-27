# pripraveno

Крон-скрипт: проверяет статус заявок на сайте
[ipc.gov.cz](https://ipc.gov.cz/en/status-of-your-application/) и уведомляет
(печатает в stdout), если статус изменился с прошлого запуска.

## Как это работает

Форма статуса на сайте — SPA поверх скрытого API:

```
POST /api/ip/external/proceedings/state/cj/zov
     ?idCj={referenceNumber}&database={category}&year={year}&zov={visaNumber}
Content-Type: application/json
body: {"captcha": "<recaptcha-v3-token>"}
```

Ответ: `{ "state": "INPROGRESS" | "APPROVED" | <иное>, "identification": "..." }`.
Не найдено → `{ "message": "ENTITY_NOT_EXIST" }`.

Эндпоинт защищён **reCAPTCHA v3** — сервер валидирует токен, без него отдаёт `400`.
Токен генерит только Google-скрипт в реальном браузере на домене ipc.gov.cz,
поэтому скрипт поднимает headless-Chromium через Playwright: открывает страницу
формы, тем же `grecaptcha` и site-key'ом добывает свежий токен, а сам статус-запрос
шлёт напрямую из контекста страницы (`fetch`). Один прогрев браузера — все номера
за один заход.

## Формат номера заявки

```
OAM-<цифры>[-<суффикс>]/<2 буквы>-<4 цифры>
```

Примеры: `OAM-12345/CC-2024`, `OAM-12345-6/CC-2024`.

Опционально можно добавить номер визовой аппликации (ZOV) через `=`:

```
OAM-12345/CC-2024=ABCD12345
```

## Установка

Нужен **Python 3.14+** (на 3.12 этой машины сломан `_json` — сегфолтит на битом
JSON; проект использует venv на 3.14).

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
```

## Запуск

Номера заявок — позиционными аргументами (хотя бы один):

```bash
.venv/bin/python -m ipc_checker "OAM-12345/CC-2024" "OAM-777/AB-2023"
```

Прошлые статусы хранятся в `state.json` рядом с проектом (путь меняется `--state`).
При изменении статуса печатается строка `CHANGED …` в stdout. Первый запуск молча
запоминает базовый статус — добавь `--notify-new`, чтобы печатать и его.

Коды возврата: `0` — всё ок, `1` — были ошибки по отдельным заявкам (стейт по
успешным всё равно сохранён), `2` — невалидный формат номера.

## Cron

Крон сам разошлёт stdout по email через `MAILTO`. Пример — раз в 6 часов:

```cron
MAILTO=esemiko@gmail.com
0 */6 * * * cd /home/esemi/development/pripraveno && .venv/bin/python -m ipc_checker "OAM-12345/CC-2024"
```
