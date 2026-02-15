
# Ummanet Telegram Bot

Telegram bot service of the Ummanet project, written in Python with `aiogram`.


You can learn how to develop telegram bots using the `aiogram` framework in the following courses (in Russian):
1. <a href="https://stepik.org/course/120924/">Телеграм-боты на Python и AIOgram</a>
2. <a href="https://stepik.org/a/153850?utm_source=kmsint_github">Телеграм-боты на Python: продвинутый уровень</a>

## About the template

### Used technology
* Python 3.12;
* aiogram 3.x (Asynchronous Telegram Bot framework);
* aiogram_dialog (GUI framework for telegram bot);
* dynaconf (Configuration Management for Python);
* taskiq (Async Distributed Task Manager);
* fluentogram (Internationalization tool in the Fluent paradigm);
* Docker and Docker Compose (containerization);
* PostgreSQL (database);
* NATS (queue and FSM storage);
* Redis (cache, taskiq result backend);
* Alembic (database migrations with raw SQL).

### Bot versioning
* The current bot version is stored in `bot/config/settings.toml` under the `BOT_VERSION` key.
* Update the version automatically with `python scripts/bump_bot_version.py` (options `--part major|minor|patch`, default is patch).
* The `/start` command greets the user and shows the deployed version for quick diagnostics.

### Structure

```
📁 aiogram_bot_template/
├── 📁 alembic/
│   ├── 📁 versinos/
│   │   ├── 1541bb8a3f26_.py
│   │   └── b20e5643d3bd_.py
│   ├── env.py
│   └── script.py.mako
├── 📁 app/
│   ├── 📁 bot/
│   │   ├── 📁 dialogs/
│   │   │   ├── 📁 flows/
│   │   │   │   ├── 📁 settings/
│   │   │   │   │   ├── dialogs.py
│   │   │   │   │   ├── getters.py
│   │   │   │   │   ├── handlers.py
│   │   │   │   │   ├── keyboards.py
│   │   │   │   │   └── states.py
│   │   │   │   ├── 📁 start/
│   │   │   │   │   ├── dialogs.py
│   │   │   │   │   ├── getters.py
│   │   │   │   │   ├── handlers.py
│   │   │   │   │   └── states.py
│   │   │   │   └── __init__.py
│   │   │   └── 📁 widgets/
│   │   │       └── i18n.py
│   │   ├── 📁 enums/
│   │   │   ├── actions.py
│   │   │   └── roles.py
│   │   ├── 📁 filters/
│   │   │   └── dialog_filters.py
│   │   ├── 📁 handlers/
│   │   │   ├── __init__.py
│   │   │   ├── commands.py
│   │   │   └── errors.py
│   │   ├── 📁 i18n/
│   │   │   └── translator_hub.py
│   │   ├── 📁 keyboards/
│   │   │   ├── links_kb.py
│   │   │   └── menu_button.py
│   │   ├── 📁 middlewares/
│   │   │   ├── database.py
│   │   │   ├── get_user.py
│   │   │   ├── i18n.py
│   │   │   └── shadow_ban.py
│   │   ├── 📁 states/
│   │   │   └── states.py
│   │   ├── __init__.py
│   │   └── bot.py
│   ├── 📁 infrastructure/
│   │   ├── 📁 cache/
│   │   │   └── connect_to_redis.py
│   │   ├── 📁 database/
│   │   │   ├── 📁 connection/
│   │   │   │   ├── base.py
│   │   │   │   ├── connect_to_pg.py
│   │   │   │   └── psycopg_connection.py
│   │   │   ├── 📁 models/
│   │   │   │   └── users.py
│   │   │   ├── 📁 query/
│   │   │   │   └── results.py
│   │   │   ├── 📁 tables/
│   │   │   │   ├── 📁 enums/
│   │   │   │   │   ├── base.py
│   │   │   │   │   └── users.py
│   │   │   │   ├── base.py
│   │   │   │   └── users.py
│   │   │   ├── 📁 views/
│   │   │   │   └── views.py
│   │   │   └── db.py
│   │   └── 📁 storage/
│   │       ├── 📁 storage/
│   │       │   └── nats_storage.py
│   │       └── nats_connect.py
│   └── 📁 services/
│       ├── 📁 delay_service/
│       │   ├── 📁 models/
│       │   │   └── delayed_messages.py
│       │   ├── consumer.py
│       │   ├── publisher.py
│       │   └── start_consumer.py
│       └── 📁 scheduler/
│           ├── taskiq_broker.py
│           └── tasks.py
├── 📁 config/
│   ├── config.py
│   └── settings.toml
├── 📁 locales/
│   ├── 📁 en/
│   │   ├── 📁 LC_MESSAGES/
│   │   │   └── txt.ftl
│   │   └── 📁 static/
│   └── 📁 ru/
│       ├── 📁 LC_MESSAGES/
│       │   └── txt.ftl
│       └── 📁 static/
├── 📁 nats_broker/
│   ├── 📁 config/
│   │   └── server.conf
│   └── 📁 migrations/
│       └── create_stream.py
├── .env
├── .env.example
├── .gitignore
├── alembic.ini
├── docker-compose.example
├── docker-compose.yml
├── main.py
├── pyproject.toml
├── README.md
└── uv.lock
```

## Installation

1. Clone the repository to your local machine via HTTPS:

```bash
git clone https://github.com/Ummanetwork/Ummanet.git
```
or via SSH:
```bash
git clone git@github.com:Ummanetwork/Ummanet.git
```

2. Create a `docker-compose.yml` file in the root of the project and copy the code from the `docker-compose.example` file into it.

3. Create a `.env` file in the root of the project and copy the code from the `.env.example` file into it. Replace the required secrets (BOT_TOKEN, ADMINS_CHAT, etc).

4. Run `docker-compose.yml` with `docker compose up` command. You need docker and docker-compose installed on your local machine.
   > Для локальной отладки без Docker можно пропустить шаги 2–4 и настроить сервисы вручную — подробности в разделе «Debug без Docker» ниже.

5. Create a virtual environment in the project root and activate it.

6. Install the required libraries in the virtual environment:
```bash
pip install -r requirements-dev.txt
```
For a minimal runtime environment without developer tools, use:
```bash
pip install -r requirements.txt
```
7. Write SQL code in the `upgrade` and `downgrade` functions to create a database schema. See example in file `alembic/versions/1541bb8a3f26_.py`.

8. If required, create additional empty migrations with the command:
```bash
alembic revision
```
and fill them with SQL code.

9. Apply database migrations using the command:
```bash
alembic upgrade head
```

10. Run `create_stream.py` to create NATS stream for delayed messages service:
```bash
python3 -m nats_broker.migrations.create_stream
```

11. If you want to use the Taskiq broker for background tasks as well as the Taskiq scheduler, add your tasks to the `tasks.py` module and start the worker first:
```bash
taskiq worker app.services.scheduler.taskiq_broker:broker -fsd
```
and then the scheduler:
```bash
taskiq scheduler app.services.scheduler.taskiq_broker:scheduler
```

12. Run `main.py` to check the functionality of the template.

13. You can fill the template with the functionality you need.

### Debug без Docker

Если нужно запускать бота напрямую из IDE или терминала:

1. Скопируйте `bot/.env.example` в `bot/.env` и пропишите реальные токены/доступы.
2. Убедитесь, что PostgreSQL доступен по параметрам из `bot/config/settings.toml` (в dev-профиле используется `localhost:5453`). При необходимости подправьте хост/порт и креды.
3. В `bot/config/settings.toml` в секции `[development.features]` оставьте `ENABLE_NATS = false` и `ENABLE_TASKIQ = false`. Так бот будет использовать встроенное хранилище состояний и не будет подключаться к NATS/Taskiq.
4. Активируйте виртуальное окружение и установите зависимости:
   ```bash
   pip install -r requirements-dev.txt
   ```
5. Запускайте бота напрямую (из корня проекта):
   ```bash
   python bot/main.py
   ```

Команды, зависящие от NATS/Taskiq, будут отключены до тех пор, пока вы не вернёте их в конфигурации.

## Developer tools

For convenient interaction with nats-server you need to install nats cli tool. For macOS you can do this through the homebrew package manager. Run the commands:
```bash
brew tap nats-io/nats-tools
brew install nats-io/nats-tools/nats
```
For linux:
```bash
curl -sf https://binaries.nats.dev/nats-io/natscli/nats@latest | sh
sudo mv nats /usr/local/bin/
```
After this you can check the NATS version with the command:
```bash
nats --version
```

## TODO

1. Add mailing service
2. Set up a CICD pipeline using Docker and GitHub Actions
