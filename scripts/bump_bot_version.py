#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Tuple

CONFIG_PATH = Path("bot/config/settings.toml")
SECTION_HEADER = "[default]"
KEY = "BOT_VERSION"
VERSION_PATTERN = re.compile(rf"^(\s*{KEY}\s*=\s*)\"([^\"]+)\"", re.MULTILINE)


def parse_version(value: str) -> Tuple[int, int, int]:
    try:
        major, minor, patch = (int(part) for part in value.split("."))
    except ValueError as exc:
        raise ValueError(f"Unsupported version format: {value!r}") from exc
    return major, minor, patch


def format_version(parts: Tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in parts)


def bump_version(version: str, part: str) -> str:
    major, minor, patch = parse_version(version)
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1
    return format_version((major, minor, patch))


def load_version(content: str) -> str:
    match = VERSION_PATTERN.search(content)
    if match:
        return match.group(2)
    return "0.0.0"


def replace_version(content: str, new_version: str) -> str:
    match = VERSION_PATTERN.search(content)
    if match:
        return VERSION_PATTERN.sub(
            lambda m: f'{m.group(1)}"{new_version}"', content, count=1
        )

    insert_block = f"    {KEY} = \"{new_version}\"\n"
    section_match = re.search(rf"^{re.escape(SECTION_HEADER)}\s*$", content, re.MULTILINE)
    if section_match:
        insert_position = section_match.end()
        return content[:insert_position] + "\n" + insert_block + content[insert_position:]

    # Fallback: append new section at the end
    return f"{content.rstrip()}\n\n{SECTION_HEADER}\n{insert_block}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Bump bot version in settings.toml")
    parser.add_argument(
        "--part",
        choices=("major", "minor", "patch"),
        default="patch",
        help="Version component to increment",
    )
    parser.add_argument(
        "--set",
        dest="set_version",
        help="Explicitly set version instead of bumping",
    )
    args = parser.parse_args()

    if not CONFIG_PATH.exists():
        raise SystemExit(f"Configuration file not found: {CONFIG_PATH}")

    content = CONFIG_PATH.read_text(encoding="utf-8")
    current_version = load_version(content)
    new_version = args.set_version or bump_version(current_version, args.part)
    updated = replace_version(content, new_version)
    CONFIG_PATH.write_text(updated, encoding="utf-8")
    print(f"{current_version} -> {new_version}")


if __name__ == "__main__":
    main()
