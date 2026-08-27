# pripraveno

Крон-скрипт: проверяет статус заявок на сайте
[ipc.gov.cz](https://ipc.gov.cz/en/status-of-your-application/) и шлёт письмо,
если статус изменился с прошлого запуска.

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
`(было …)` и на почту уходит письмо. Прошлые статусы хранятся в `state.json`
рядом с проектом.

Коды возврата: `0` — всё ок, `1` — были ошибки по отдельным заявкам (стейт по
успешным всё равно сохранён), `2` — невалидный формат номера.

## Уведомления на почту (SMTP)

Письмо шлётся напрямую из скрипта через SMTP (по умолчанию Gmail). Локальный MTA
и `MAILTO` в cron не нужны. Креды берутся из окружения — в код/git не попадают:

| Переменная          | Назначение                                       | По умолчанию     |
|---------------------|--------------------------------------------------|------------------|
| `IPC_SMTP_USER`     | логин SMTP (gmail-адрес отправителя)             | —                |
| `IPC_SMTP_PASSWORD` | **app-пароль** Google (не пароль аккаунта!)      | —                |
| `IPC_MAIL_TO`       | получатель                                        | `IPC_SMTP_USER`  |
| `IPC_SMTP_HOST`     | SMTP-хост                                          | `smtp.gmail.com` |
| `IPC_SMTP_PORT`     | порт STARTTLS                                      | `587`            |

App-пароль Google: <https://myaccount.google.com/apppasswords> (нужна включённая
2FA). Если `IPC_SMTP_USER`/`IPC_SMTP_PASSWORD` не заданы — письмо не шлётся,
изменения только печатаются в stdout.

## Cron

Скрипт шлёт письмо сам, поэтому `MAILTO` не нужен. Креды удобно держать в
отдельном файле (не в crontab) и подтягивать перед запуском. Пример — раз в 6 часов:

```cron
0 */6 * * * cd /home/esemi/development/pripraveno && set -a && . ./.env && set +a && .venv/bin/python -m ipc_checker "OAM-12345/CC-2024" >> cron.log 2>&1
```

где `.env` (в `.gitignore`) содержит:

```sh
IPC_SMTP_USER=esemiko@gmail.com
IPC_SMTP_PASSWORD=<app-пароль>
```
