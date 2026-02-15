#!/usr/bin/env python3
"""
Trigger backend translations repair job via admin API.

Usage:
  python scripts/run_translation_repair.py \
    --base-url http://localhost:8000 \
    --service-api-key <BACKEND_SERVICE_API_KEY>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run backend translations repair task.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("BACKEND_BASE_URL", "http://localhost:8000"),
        help="Backend API base URL.",
    )
    parser.add_argument(
        "--service-api-key",
        default=os.getenv("BACKEND_SERVICE_API_KEY"),
        help="Service API key used for /auth/service-login.",
    )
    parser.add_argument(
        "--targets-for-icons",
        default="ar,tr,en",
        help="Comma-separated language codes for emoji/icon sync.",
    )
    parser.add_argument(
        "--use-ru-for-missing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fill missing translations from RU values.",
    )
    parser.add_argument(
        "--ensure-placeholders",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enforce placeholder consistency across locales.",
    )
    parser.add_argument(
        "--use-ai",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use configured AI translator when available.",
    )
    return parser.parse_args()


def post_json(url: str, payload: dict, *, token: str | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        text = response.read().decode("utf-8")
    if not text:
        return {}
    return json.loads(text)


def main() -> int:
    args = parse_args()
    api_key = (args.service_api_key or "").strip()
    if not api_key:
        print("Missing --service-api-key (or BACKEND_SERVICE_API_KEY).", file=sys.stderr)
        return 2

    base_url = args.base_url.rstrip("/")
    targets = [code.strip().lower() for code in args.targets_for_icons.split(",") if code.strip()]
    login_payload = {"api_key": api_key, "service": "maintenance"}
    repair_payload = {
        "targets_for_icons": targets,
        "use_ru_for_missing": bool(args.use_ru_for_missing),
        "ensure_placeholders": bool(args.ensure_placeholders),
        "use_ai": bool(args.use_ai),
    }

    try:
        login_data = post_json(f"{base_url}/auth/service-login", login_payload)
        access_token = str(login_data.get("access_token") or "").strip()
        if not access_token:
            print("Service login did not return access_token.", file=sys.stderr)
            return 1
        result = post_json(
            f"{base_url}/admin/translations/repair",
            repair_payload,
            token=access_token,
        )
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {details}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
