# Shariat Bot

Shariat Bot — комплексный сервис для мусульманской общины: Telegram‑бот на `aiogram 3`, связанный с FastAPI‑backend, административными веб‑панелями (React/Vue) и Nginx‑шлюзом. Хранение в PostgreSQL, кэш — Redis, фоновые задачи/очереди — TaskIQ / NATS. Всё завернуто в Docker.

## Архитектура

- `backend/` — FastAPI‑служба: языки, переводы, загрузка богословских материалов, админ‑эндпоинты.
- `bot/` — Telegram‑бот: диалоги, регистрация, интеграция с ИИ (Fireworks).
- `frontends/react-admin` и `frontends/vue-portal` — админ‑панель и портал.
- `nginx/` — конфигурация edge‑прокси.
- `docker-compose.yml` — оркестрация (PostgreSQL, Redis, приложения).

Поддерживаемые языки бота: ru, en, ar. В БД есть таблица `languages`, переводы, а у пользователя есть `language_id`.

## Конфигурация окружения

1. Скопируйте `bot/.env.example` в `bot/.env` и заполните.
2. Для локальной разработки `POSTGRES_HOST`/`POSTGRES__HOST` и `REDIS_HOST` можно поставить `localhost` и открыть порты из `docker-compose.yml`.
3. Переменные вида `SECTION__KEY` подхватываются Dynaconf и переопределяют соответствующие поля в `bot/config/settings.toml`.

Ключевые переменные окружения (см. также `bot/.env.example`):

- `ENV_FOR_DYNACONF=development` — профиль настроек Dynaconf
- `BOT_TOKEN` — токен Telegram‑бота
- `ADMIN_IDS`, `ADMINS_CHAT` — админские аккаунты/чат для нотификаций
- `POSTGRES_DB`/`POSTGRES_NAME`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD` — доступ к БД
- `POSTGRES__HOST`, `POSTGRES__PORT` — nested‑настройки для Dynaconf
- `REDIS_*` — хост/порт/креды Redis
- `BACKEND__BASE_URL`, `BACKEND__ADMIN_EMAIL`, `BACKEND__ADMIN_PASSWORD` — доступ бота к admin API backend
- `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL`, `AI_FIREWORKS_ACCOUNT` — доступ к Fireworks

## Регистрация пользователей в боте

- Незарегистрированному пользователю показывается приветствие на трёх языках и инлайн‑кнопки выбора языка.
- После выбора языка запускается FSM‑регистрация: имя → e‑mail → телефон → «Поделиться контактом» для подтверждения номера.
- После успешной регистрации показывается главное меню. В `users` сохраняются `full_name`, `email`, `phone_number`, флаги `phone_verified/email_verified`.
- Пользователи синхронизируются в админку (`POST /admin/users`).

## Миграции (Alembic) при деплое через GitHub Actions

Миграции сделаны идемпотентными (везде используем `IF NOT EXISTS`), поэтому безопасно запускать их на уже частично заполненных БД.

Рекомендуемый запуск миграций — сразу после обновления сервисов:

1) Добавьте шаг в `.github/workflows/dev-deploy.yml` в секцию SSH‑deploy после `up -d`:

```
docker compose -f compose.yaml exec -T bot alembic upgrade head
```

2) Если база уже содержит часть объектов (ошибки DuplicateTable/DuplicateColumn), просто повторный запуск пройдет успешно благодаря `IF NOT EXISTS`.

3) Частые вопросы:
- Ошибка `integer out of range` при регистрации — примените миграцию, переводящую `users.user_id` в BIGINT (входит в `head`).
- Колонки `email_verified/phone_verified` отсутствуют — примените `alembic upgrade head` (теперь добавляются безопасно).

## Ручной запуск миграций на dev‑сервере

```
ssh ssh vpsShariat
cd /opt/project
docker compose -f compose.yaml exec -T bot alembic upgrade head
```

Проверка наличия таблиц/колонок:

```
docker compose -f compose.yaml exec -T postgres \
  psql -U postgres -d postgres -c "SELECT to_regclass('public.languages'), to_regclass('public.translation_keys'), to_regclass('public.translations');"

docker compose -f compose.yaml exec -T postgres \
  psql -U postgres -d postgres -c "SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name in ('language_id','email_verified','phone_verified','full_name','email','phone_number');"
```

## Сбор и валидация богословских материалов

1) Источники фиксируем (путь/ссылка, язык, тематика). Загружаем через админ‑панель или `POST /admin/documents` (multipart): тема (`topic`), язык (`language`), файл (`file`).
2) Допускаются только проверенные материалы: на стороне ответственного богослова проходит рецензирование (минимум два ревьюера при спорных вопросах). Результат — «готово к публикации» или «требует исправлений».
3) После загрузки файл доступен в списке документов, можно обновить/заменить/удалить.
4) В боте документы выбираются по теме и языку (приоритет — язык пользователя, затем дефолт/английский, иначе первый доступный).

Минимальные требования к файлам: PDF/DOCX, корректная кодировка, понятные названия.

