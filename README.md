# pripraveno

Крон-скрипт: проверяет статус заявок на сайте
[ipc.gov.cz](https://ipc.gov.cz/en/status-of-your-application/) и шлёт сообщение
в Telegram, если статус изменился с прошлого запуска.

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

Каждый прогон печатает текущий статус каждой заявки в stdout (`state` как есть,
без перевода). Если статус изменился с прошлого запуска — строка помечается
`(было …)` и в Telegram уходит сообщение. Прошлые статусы хранятся в `state.json`
рядом с проектом.

Коды возврата: `0` — всё ок, `1` — были ошибки по отдельным заявкам (стейт по
успешным всё равно сохранён), `2` — невалидный формат номера.

## Уведомления в Telegram

Сообщение шлётся напрямую из скрипта через Bot API (в личку). Нужны два аргумента:

| Аргумент      | Назначение                                    |
|---------------|-----------------------------------------------|
| `--bot-token` | токен бота от [@BotFather](https://t.me/BotFather) |
| `--chat-id`   | твой chat_id (личка с ботом)                  |

Свой `chat_id`: напиши боту `/start`, затем
`https://api.telegram.org/bot<TOKEN>/getUpdates` — id в `message.chat.id`.

Если `--bot-token`/`--chat-id` не заданы — уведомление не шлётся, изменения
только печатаются в stdout.

## Cron

Пример — раз в 6 часов (токен светится в crontab/ps, храни файл crontab закрытым):

```cron
0 */6 * * * cd /home/esemi/development/pripraveno && .venv/bin/python -m ipc_checker "OAM-12345/CC-2024" --bot-token 123456:ABC... --chat-id 12345678 >> cron.log 2>&1
```
