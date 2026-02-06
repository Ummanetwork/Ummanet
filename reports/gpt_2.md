Сергей, давай сделаем **одну команду‑проверку**, которая уверенно отвечает на два вопроса:

1. *Запущены ли на dev‑сервере контейнеры из **текущего коммита**?*
2. *Живы ли ключевые эндпоинты и нет ли петли редиректов на /admin/?*

Ниже — самодостаточный bash‑скрипт. Он:

* по SSH заходит на dev‑сервер, перечисляет контейнеры вашего `compose.yaml`,
* вытаскивает из **image‑label** `org.opencontainers.image.revision` **точный git‑SHA** сборки (этот лейбл автоматически проставляет `docker/metadata-action@v5`),
* сравнивает его с ожидаемым SHA (обычно `git rev-parse HEAD`),
* (опционально) сверяет **хэш nginx.conf** в контейнере с локальным из репозитория,
* делает HTTP‑smoke‑тесты `/health` и `/admin/` и показывает коды, финальный URL и число редиректов.

> Почему это надёжно
> • Лейбл `org.opencontainers.image.revision` — стандартная **OCI‑аннотация**; `docker/metadata-action` действительно её пишет в образ по умолчанию. Это позволяет однозначно сопоставить запущенный образ и git‑коммит. ([GitHub][1])
> • Извлечь лейблы и другие поля можно через `docker image inspect` / `docker inspect` с **Go‑шаблонами** (`--format`). ([Docker Documentation][2])
> • `docker compose -f … ps -q` даёт контейнеры конкретного compose‑проекта; Compose помечает их лейблом `com.docker.compose.project`, что группирует ресурсы проекта. ([Docker Documentation][3])
> • Для HTTP‑проверок скрипт использует `curl -w` (write‑out) с переменными `http_code`, `url_effective`, `num_redirects`, что официально задокументировано. ([everything.curl.dev][4])

---

## 1) Сохраните скрипт `verify-deploy.sh`

```bash
#!/usr/bin/env bash
# verify-deploy.sh
set -Eeuo pipefail

# === Конфиг через переменные окружения / флаги ===
SSH_HOST="${SSH_HOST:-}"
SSH_USER="${SSH_USER:-}"
SSH_PORT="${SSH_PORT:-22}"
REMOTE_COMPOSE="${REMOTE_COMPOSE:-/opt/tg-bot/compose.yaml}"

BASE_URL="${BASE_URL:-}"                 # напр. http://devbest.pro:8081
EXPECTED_SHA="${EXPECTED_SHA:-}"         # напр. $(git rev-parse HEAD)

NGINX_SERVICE="${NGINX_SERVICE:-nginx}"  # имя сервиса в compose
NGINX_CONF_LOCAL="${NGINX_CONF_LOCAL:-./nginx/nginx.conf}"
NGINX_CONF_IN_CONTAINER="${NGINX_CONF_IN_CONTAINER:-/etc/nginx/nginx.conf}"

usage() {
  cat <<EOF
Обязательные переменные:
  SSH_HOST, SSH_USER, BASE_URL, EXPECTED_SHA
Опционально:
  SSH_PORT (по умолчанию 22)
  REMOTE_COMPOSE (по умолчанию /opt/tg-bot/compose.yaml)
  NGINX_SERVICE (по умолчанию 'nginx')
  NGINX_CONF_LOCAL (по умолчанию ./nginx/nginx.conf)
  NGINX_CONF_IN_CONTAINER (по умолчанию /etc/nginx/nginx.conf)
Пример запуска:
  SSH_HOST=vm1272520 SSH_USER=sergey BASE_URL=http://devbest.pro:8081 \\
  EXPECTED_SHA=\$(git rev-parse HEAD) bash verify-deploy.sh
EOF
}

[[ -z "${SSH_HOST}" || -z "${SSH_USER}" || -z "${BASE_URL}" || -z "${EXPECTED_SHA}" ]] && { usage; exit 2; }

short() { echo "${1:0:12}"; }

echo "==> Ожидаемый коммит: $(short "$EXPECTED_SHA")"
echo "==> Сервер: ${SSH_USER}@${SSH_HOST}:${SSH_PORT}, compose: ${REMOTE_COMPOSE}"
echo

remote() { ssh -p "$SSH_PORT" -o StrictHostKeyChecking=accept-new "${SSH_USER}@${SSH_HOST}" "$@"; }

# --- 1. Собираем список контейнеров проекта ---
echo "== docker compose ps (remote) =="
remote "docker compose -f '${REMOTE_COMPOSE}' ps" || { echo "Compose недоступен"; exit 1; }
echo

CONTAINERS=$(remote "docker compose -f '${REMOTE_COMPOSE}' ps -q" || true)
if [[ -z "$CONTAINERS" ]]; then
  echo "Нет контейнеров у проекта (compose ps -q дал пусто)"; exit 1
fi

# --- 2. Проверяем ревизии образов через OCI label ---
echo "== Сводка по образам и ревизиям (org.opencontainers.image.revision) =="
FAIL=0
while read -r CID; do
  [[ -z "$CID" ]] && continue
  # service name
  SVC=$(remote "docker container inspect --format '{{ index .Config.Labels \"com.docker.compose.service\"}}' $CID")
  # image ref used by container
  IMG_REF=$(remote "docker container inspect --format '{{ .Config.Image }}' $CID")
  # image ID (content digest)
  IMG_ID=$(remote "docker container inspect --format '{{ .Image }}' $CID")
  # revision label read from IMAGE (не из контейнера)
  REV=$(remote "docker image inspect --format '{{ index .Config.Labels \"org.opencontainers.image.revision\"}}' $IMG_ID || true")
  # repo digests (для справки)
  DIGESTS=$(remote "docker image inspect --format '{{ json .RepoDigests }}' $IMG_ID || true")

  MATCH="NO"
  if [[ -n "$REV" ]]; then
    if [[ "$REV" == "$EXPECTED_SHA" || "$REV" == $(short "$EXPECTED_SHA")* || "$EXPECTED_SHA" == "$REV"* ]]; then
      MATCH="YES"
    fi
  fi

  printf "%-14s image=%-48s rev=%-14s match=%s\n" "$SVC" "$IMG_REF" "$(short "${REV:-n/a}")" "$MATCH"
  [[ "$MATCH" == "NO" ]] && FAIL=1
done <<< "$CONTAINERS"
echo

# --- 3. Сравниваем nginx.conf (локальный vs запущенный) по SHA256 (опционально) ---
if [[ -f "$NGINX_CONF_LOCAL" ]]; then
  echo "== Проверка nginx.conf (хэш локального vs в контейнере '$NGINX_SERVICE') =="
  LOCAL_SHA=$(sha256sum "$NGINX_CONF_LOCAL" | awk '{print $1}')
  NGINX_CID=$(remote "docker compose -f '${REMOTE_COMPOSE}' ps -q '${NGINX_SERVICE}'" || true)
  if [[ -n "$NGINX_CID" ]]; then
    REMOTE_SHA=$(
      remote "docker exec '$NGINX_CID' sh -lc 'command -v sha256sum >/dev/null 2>&1 && sha256sum \"$NGINX_CONF_IN_CONTAINER\" 2>/dev/null | awk '{print \$1}' || (command -v busybox >/dev/null 2>&1 && busybox sha256sum \"$NGINX_CONF_IN_CONTAINER\" 2>/dev/null | awk '{print \$1}') || true'"
    )
    if [[ -n "$REMOTE_SHA" ]]; then
      echo "local : $LOCAL_SHA"
      echo "remote: $REMOTE_SHA"
      if [[ "$LOCAL_SHA" != "$REMOTE_SHA" ]]; then
        echo "NGINX CONF MISMATCH"; FAIL=1
      else
        echo "NGINX CONF OK"
      fi
    else
      echo "Не удалось прочитать ${NGINX_CONF_IN_CONTAINER} в контейнере (нет sha256sum или файла). Пропускаю."
    fi
  else
    echo "Контейнер сервиса '$NGINX_SERVICE' не найден."
  fi
  echo
fi

# --- 4. HTTP smoke: /health и /admin/ ---
echo "== HTTP smoke =="
set +e
HEALTH=$(curl -fsS -o /dev/null -w "health http_code:%{http_code} time_total:%{time_total}\n" "${BASE_URL%/}/health")
RC=$?
set -e
if [[ $RC -ne 0 ]]; then echo "health FAIL (curl rc=$RC)"; FAIL=1; else echo "$HEALTH"; fi

set +e
ADMIN=$(curl -sS -o /dev/null -L --max-redirs 15 -w "admin  http_code:%{http_code} num_redirects:%{num_redirects} url_effective:%{url_effective}\n" "${BASE_URL%/}/admin/")
RC=$?
set -e
if [[ $RC -ne 0 ]]; then
  echo "admin  FAIL (curl rc=$RC)"; FAIL=1
else
  echo "$ADMIN"
fi
echo

if [[ $FAIL -ne 0 ]]; then
  echo "==> ПРОВЕРКА ЗАВЕРШЕНА: НЕСОВПАДЕНИЯ ОБНАРУЖЕНЫ"; exit 1
else
  echo "==> ПРОВЕРКА ЗАВЕРШЕНА: ВСЁ ОК"
fi
```

### Как запустить (одной командой)

```bash
SSH_HOST=vm1272520 SSH_USER=sergey BASE_URL=http://devbest.pro:8081 \
EXPECTED_SHA=$(git rev-parse HEAD) \
bash verify-deploy.sh
```

> Если хотите проверить сразу удалённый digest тега в реестре (чтобы убедиться, что **pull** подтянул самую свежую манифест‑лист/образ), можно дополнительно использовать:
>
> ```bash
> ssh -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
>   "docker buildx imagetools inspect ghcr.io/s-typy/shariat-nginx:dev-latest"
> ```
>
> Команда показывает **imagetools/manifest** и digest в реестре, без локального pull. ([Docker Documentation][5])

---

## Что именно проверяется и на что опираемся (ссылки)

1. **Соответствие коммиту**
   Скрипт сравнивает `EXPECTED_SHA` и значение лейбла образа `org.opencontainers.image.revision`, который проставляет `docker/metadata-action@v5`. Пример из официальной документации действия:
   `labels: org.opencontainers.image.revision=${{ github.sha }}`. ([GitHub][1])
   Аннотации/лейблы — стандарт OCI Image Spec (раздел Annotations). ([https://opencontainers.github.io][6])
   Извлечение лейбла делается через `docker image inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision"}}'`. Документация `docker image inspect`/`docker inspect` и форматирования (Go‑templates) — официальные. ([Docker Documentation][2])

2. **Идентификация контейнеров из нужного compose‑проекта**
   Используется `docker compose -f <file> ps` (в т. ч. `-q` для ID). Это относится к CLI `docker compose`, флаг `-f` и команда `ps` описаны в документации. Сам Compose группирует ресурсы по проекту и проставляет служебные лейблы `com.docker.compose.*`. ([Docker Documentation][3])

3. **HTTP‑smoke**
   `curl -w` (write‑out) с переменными `http_code`, `url_effective`, `num_redirects` — официальный раздел «Write out». Это позволяет за один вызов получить код, финальный URL и число редиректов. ([everything.curl.dev][4])
   (На заметку к вашей прежней диагностике: сообщение `curl: (47) Maximum (50) redirects followed` соответствует поведению curl — дефолт лимит редиректов **50** по man‑page. ([curl.se][7]))

4. **Сверка конфигов Nginx**
   Сравнение `sha256sum` локального `nginx.conf` и файла в контейнере — практичный индикатор, что образ на сервере собран именно из текущего дерева. Если хотите ещё и *на лету* видеть ревизию в ответах, можно добавить в `nginx.conf` метку‑заголовок:

   ```nginx
   http {
     add_header X-Image-Revision "<GIT_SHA>" always;
   }
   ```

   `add_header ... always` документирован в `ngx_http_headers_module` (параметр `always` добавляет заголовок при любом коде ответа). ([Nginx][8])

---

## (Опционально) Как «прибить» проверку к пайплайну

После вашего `deploy`‑job добавьте `verify`‑job, который дергает скрипт по SSH:

```yaml
  verify:
    needs: deploy
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run verify script over SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.SSH_HOST }}
          port: ${{ secrets.SSH_PORT }}
          username: ${{ secrets.SSH_USER }}
          key: ${{ secrets.SSH_KEY }}
          fingerprint: ${{ secrets.SSH_HOST_FINGERPRINT }}
          script: |
            set -euo pipefail
            BASE_URL="http://devbest.pro:8081"
            EXPECTED_SHA="${{ github.sha }}"
            REMOTE_COMPOSE="/opt/tg-bot/compose.yaml"
            bash -s <<'EOS'
            # Вставьте сюда ТЕЛО verify-deploy.sh из ответа (функции + логика)
            EOS
```

---

### Что ещё можно добавить (по вкусу)

* **Сверка digest с реестром**: `docker buildx imagetools inspect` возвращает digest тега в GHCR — можно сравнить его с `RepoDigests` локального образа (для вашей платформы). ([Docker Documentation][5])
* **Явный заголовок версии на /health**: если добавите в backend/бот/фронт эндпоинт или заголовок `X-Revision`, smoke‑тест может проверять, что *вся цепочка* (не только Nginx) отдает те же ревизии. Реализация заголовка для Nginx через `add_header` показана выше. ([Nginx][8])

---

Если захочется расширить сценарий — например, валидировать отсутствие *orphan‑containers* или автоматически ловить бесконечные 302‑петли по `/admin/` (такие петли легко видно по `num_redirects` и `url_effective`) — это легко впишется в тот же скрипт без изменения принципа работы.

[1]: https://github.com/docker/metadata-action?utm_source=chatgpt.com "docker/metadata-action"
[2]: https://docs.docker.com/reference/cli/docker/image/inspect/?utm_source=chatgpt.com "docker image inspect"
[3]: https://docs.docker.com/reference/cli/docker/compose/?utm_source=chatgpt.com "docker compose"
[4]: https://everything.curl.dev/usingcurl/verbose/writeout.html?utm_source=chatgpt.com "Write out - Everything curl"
[5]: https://docs.docker.com/reference/cli/docker/buildx/imagetools/inspect/?utm_source=chatgpt.com "docker buildx imagetools inspect"
[6]: https://specs.opencontainers.org/image-spec/?utm_source=chatgpt.com "The OpenContainers Image Spec"
[7]: https://curl.se/docs/manpage.html?utm_source=chatgpt.com "curl man page"
[8]: https://nginx.org/en/docs/http/ngx_http_headers_module.html "Module ngx_http_headers_module"
