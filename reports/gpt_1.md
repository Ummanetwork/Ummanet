Симптом понятен: `curl -IL http://devbest.pro:8081/admin/` утыкается в бесконечные редиректы `302 Location: /admin/` и падает на лимите 50 переходов. Это ровно то, как `curl` себя ведёт: при `-L` он следует редиректам (по умолчанию до 50 раз) и вываливается с ошибкой 47, если петля не заканчивается. ([MDN Web Docs][1])

Ниже — короткая диагностика и сразу рабочее исправление.

---

## Почему образовалась петля (по конфигу)

В вашем `nginx.conf` для админки:

```nginx
location = /admin  { return 301 /admin/; }   # это трогает ТОЛЬКО /admin без слеша
location /admin/ {
  proxy_pass http://react_admin/;            # <-- тут важен завершающий /
  proxy_redirect http://react_admin:5173/ /admin/;
  proxy_redirect http://react_admin/ /admin/;
  ...
}
```

* Правило `= /admin` даёт **301**, но в логе `curl` **нет ни одного 301**, значит бесконечный редирект приходит **не отсюда**. ([MDN Web Docs][2])
* Внутри `location /admin/` вы проксируете на `react_admin:5173` и **переписываете Location заголовки** от апстрима в `/admin/` с помощью `proxy_redirect`. Если апстрим (Vite/React Admin dev‑сервер) отвечает редиректом на `/` или на `http://react_admin:5173/`, NGINX переписывает это в `/admin/`, клиент снова запрашивает `/admin/` — и цикл повторяется. Это как раз то, что делает `proxy_redirect`: меняет `Location`/`Refresh` в ответах апстрима. ([Nginx][3])

Дополнительно, из‑за завершающего слеша в `proxy_pass http://react_admin/;` NGINX **срезает префикс `/admin/`** перед отправкой на апстрим (т.е. `/admin/x` превращается в `/x` для апстрима). Это штатная логика NGINX при `proxy_pass` **с URI**. Без завершающего слеша (`proxy_pass http://react_admin;`) исходный URI передаётся **как есть**. ([Nginx][3])

> Резюме гипотезы (проверяемая): апстрим отдаёт редирект (например на `/`), `proxy_redirect` превращает его в `/admin/`, клиент возвращается на `/admin/` и всё повторяется.

---

## Как быстро подтвердить причину (2 команды)

1. Временно отключить переписывание редиректов и посмотреть «сырой» `Location` из апстрима:

```nginx
location /admin/ {
  proxy_pass http://react_admin/;
  proxy_redirect off;  # временно
}
```

Перезагрузить NGINX и снова: `curl -IL http://devbest.pro:8081/admin/` — вы должны увидеть исходный `Location` (скорее всего `/` или `http://react_admin:5173/`). Именно так работает `proxy_redirect off;`. ([Nginx][3])

2. Посмотреть прямой ответ апстрима из контейнера (без NGINX):

```bash
docker exec -it <nginx_container> curl -sIL http://react-admin:5173/ -H 'Host: devbest.pro'
docker exec -it <nginx_container> curl -sIL http://react-admin:5173/admin/ -H 'Host: devbest.pro'
```

Если там `302` на `/` или на абсолютный URL — это и есть источник. (Сам факт того, что `302` — это временный редирект с указанием нового URL в `Location`, описан в спецификации/MDN.) ([MDN Web Docs][1])

---

## Исправление (рекомендуемый вариант)

Сделайте фронтенд действительно «жить» под под-путём `/admin/`, а NGINX перестанет что‑либо «магически» переписывать:

### 1) React‑Admin / React Router: добавить basename `/admin`

Если вы используете кастомный роутер (не встроенный HashRouter по умолчанию), задайте базовый путь:

```tsx
import { RouterProvider, createBrowserRouter } from 'react-router-dom';
import { Admin, Resource } from 'react-admin';

const router = createBrowserRouter(
  [{
    path: '*',
    element: (
      <Admin dataProvider={...}>
        <Resource name="posts" />
      </Admin>
    ),
  }],
  { basename: '/admin' },
);

export default () => <RouterProvider router={router} />;
```

Документация React‑Admin прямо про это: «Если админка сервится с подпути И вы используете другой Router, задайте `basename`, чтобы все ссылки включали под‑путь `/admin`». Там же есть пример с `<Admin basename="/admin">` при встраивании в родительское приложение. ([marmelab.com][4])

### 2) Vite: выставить `base: '/admin/'`

В `vite.config.ts/js`:

```ts
import { defineConfig } from 'vite';
export default defineConfig({
  base: '/admin/',  // и в dev, и в prod
});
```

`base` — это **публичный базовый путь** как в деве, так и в проде; все ссылки на ассеты будут переписаны с учётом этого базового пути. ([vitejs][5])

### 3) NGINX: перестать срезать префикс и выключить переписывание редиректов

Заменить ваш блок админки на:

```nginx
location = /admin { return 301 /admin/; }

location /admin/ {
  # ВАЖНО: без завершающего "/" — тогда апстрим увидит исходный URI c /admin/ целиком
  proxy_pass http://react_admin;

  proxy_redirect off;          # не переписываем Location — базовый путь уже учтён фронтом
  proxy_set_header Host $host; # стандартные заголовки
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;

  # если в dev нужен HMR по WebSocket, прокиньте апгрейд (не обязателен для фикса редиректов):
  proxy_http_version 1.1;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
}
```

Почему это работает:

* Без завершающего слеша у `proxy_pass` NGINX **не** заменяет префикс — URI уходит в апстрим как есть (с `/admin/`). Это официальная семантика `proxy_pass`. ([Nginx][3])
* `proxy_redirect off` гарантирует, что мы **не** превратим возможные редиректы апстрима во внутренний `/admin/`-пинг‑понг. ([Nginx][3])
* Так как `base` и `basename` заданы, переписывать HTML через `sub_filter` больше не нужно. К слову, сам модуль `ngx_http_sub_module` «по умолчанию не собирается» — использовать его стоит лишь при острой необходимости. (Подтвердить, включён ли он в вашем образе, не могу без доступа к логу `nginx -V`.) ([Nginx][6])

---

## Альтернатива (временный обходной путь)

Если по каким‑то причинам вы **не готовы** сейчас менять фронт (оставляете `base` по умолчанию `/`), можно проксировать так, чтобы NGINX снимал `/admin` перед отдачей в апстрим и добавлял его назад в редиректах:

```nginx
location = /admin { return 301 /admin/; }

location /admin/ {
  # снять префикс /admin/ перед отправкой к апстриму
  rewrite ^/admin/(.*)$ /$1 break;
  proxy_pass http://react_admin/;     # здесь как раз НУЖЕН завершающий "/"

  # переписать относительные Location назад под /admin/
  proxy_redirect / /admin/;

  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;
}
```

`proxy_redirect / /admin/;` — штатный способ переписать относительные `Location` от апстрима, добавив префикс. Но это именно «костыль», лучше всё‑таки настроить `base`/`basename` на фронте. ([Nginx][3])

---

## Как проверить, что всё починилось

После правок и reload’а NGINX:

```bash
curl -IL http://devbest.pro:8081/admin/ | sed -n '1,12p'
```

Вы должны увидеть либо прямой `200 OK`, либо ограниченное число редиректов (например один — со /admin на /admin/), но **точно не десятки**. Напомню: `curl -L` по умолчанию прекращает следовать редиректам после 50 переходов. ([curl.se][7])

---

### Ссылки, на которых основаны рекомендации

* Что такое `302` и как работает `Location` — MDN. ([MDN Web Docs][1])
* Лимит редиректов `curl` (`--max-redirs`, по умолчанию 50) — официальная man‑страница. ([curl.se][7])
* Семантика `proxy_pass` с/без завершающего `/` — официальная документация NGINX (`ngx_http_proxy_module`). ([Nginx][3])
* Что делает `proxy_redirect` (и как его отключить) — официальная документация NGINX. ([Nginx][3])
* Модуль `sub_filter` и то, что он не включён по умолчанию — официальная документация NGINX (`ngx_http_sub_module`). ([Nginx][6])
* React‑Admin: как правильно работать под подпутём и где указывать `basename`. ([marmelab.com][4])
* Vite: опция `base` — базовый публичный путь в dev и prod (и CLI `--base`). ([vitejs][5])

---

Если захочется, добавлю минимальный патч к вашему `nginx.conf` целиком и проверочный чек‑лист для `docker compose` (какие порты проброшены, где логинитесь в GHCR и т.п.).

[1]: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/302?utm_source=chatgpt.com "302 Found - HTTP - MDN - Mozilla"
[2]: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status?utm_source=chatgpt.com "HTTP response status codes - MDN - Mozilla"
[3]: https://nginx.org/en/docs/http/ngx_http_proxy_module.html "Module ngx_http_proxy_module"
[4]: https://marmelab.com/react-admin/Routing.html "React-admin - Routing in React-Admin Apps"
[5]: https://vite.dev/config/shared-options?utm_source=chatgpt.com "Shared Options"
[6]: https://nginx.org/en/docs/http/ngx_http_sub_module.html?utm_source=chatgpt.com "Module ngx_http_sub_module"
[7]: https://curl.se/docs/manpage.html?utm_source=chatgpt.com "curl man page"
