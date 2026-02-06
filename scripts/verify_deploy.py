#!/usr/bin/env python3
"""
Utility to verify that the remote deployment matches a given git revision
and responds correctly on public HTTP endpoints.

It follows the checks suggested in reports/gpt_2.md:
  * ensure docker compose stack is running;
  * confirm every container carries org.opencontainers.image.revision label
    that matches the expected git SHA;
  * (optional) compare remote nginx.conf checksum against local copy;
  * perform lightweight HTTP smoke tests for /health and /admin/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence


REDIRECT_STATUSES = {301, 302, 303, 307, 308}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify remote deployment revision and basic health.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--ssh-target",
        help="SSH config host alias (if provided, --host/--user/--port are optional)",
    )
    parser.add_argument("--host", help="SSH host of the target server")
    parser.add_argument("--user", help="SSH user")
    parser.add_argument("--port", type=int, default=22, help="SSH port")
    parser.add_argument(
        "--base-url",
        required=True,
        help="Base URL of the deployed site (e.g. http://example.com:8081)",
    )
    parser.add_argument(
        "--expected-sha",
        required=True,
        help="Git commit SHA that images should be labeled with",
    )
    parser.add_argument(
        "--remote-compose",
        default="/opt/tg-bot/compose.yaml",
        help="Compose file path on the remote host",
    )
    parser.add_argument(
        "--nginx-service",
        default="nginx",
        help="Name of nginx service within docker compose",
    )
    parser.add_argument(
        "--local-nginx-conf",
        default=os.path.join("nginx", "nginx.conf"),
        help="Path to the local nginx.conf for checksum comparison",
    )
    parser.add_argument(
        "--remote-nginx-conf",
        default="/etc/nginx/nginx.conf",
        help="Path to nginx.conf inside the running nginx container",
    )
    parser.add_argument(
        "--skip-nginx-conf",
        action="store_true",
        help="Skip nginx.conf checksum comparison",
    )
    parser.add_argument(
        "--skip-http",
        action="store_true",
        help="Skip HTTP smoke checks",
    )
    parser.add_argument(
        "--http-endpoint",
        action="append",
        dest="http_endpoints",
        default=["/health", "/admin/"],
        help="Relative HTTP endpoint to probe (can be specified multiple times)",
    )
    parser.add_argument(
        "--max-redirects",
        type=int,
        default=10,
        help="Maximum redirects to follow for HTTP probes",
    )
    parser.add_argument(
        "--http-timeout",
        type=int,
        default=10,
        help="HTTP request timeout in seconds",
    )
    parser.add_argument(
        "--identity",
        help="Path to SSH private key (passed as -i)",
    )
    parser.add_argument(
        "--ssh-option",
        action="append",
        default=[],
        metavar="OPTION",
        help="Extra -o option for ssh (e.g. StrictHostKeyChecking=accept-new)",
    )
    args = parser.parse_args()
    if args.ssh_target:
        return args

    if not args.host or not args.user:
        parser.error("either --ssh-target or both --host and --user must be provided")

    return args


def ensure_dependencies() -> None:
    if shutil.which("ssh") is None:
        sys.exit("`ssh` command not found in PATH.")
    if shutil.which("docker") is None:
        print("Warning: `docker` not found locally. Remote commands may still work.", file=sys.stderr)


def build_ssh_base_cmd(args: argparse.Namespace) -> List[str]:
    base = ["ssh"]
    if args.identity:
        base.extend(["-i", args.identity])
    if not any(opt.startswith("StrictHostKeyChecking=") for opt in args.ssh_option):
        args.ssh_option.append("StrictHostKeyChecking=accept-new")
    for opt in args.ssh_option:
        base.extend(["-o", opt])
    if args.ssh_target:
        base.append(args.ssh_target)
    else:
        base.extend(["-p", str(args.port)])
        base.append(f"{args.user}@{args.host}")
    return base


def run_ssh(
    base_cmd: Sequence[str],
    remote_cmd: Sequence[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    cmd = list(base_cmd) + list(remote_cmd)
    return subprocess.run(
        cmd,
        check=check,
        capture_output=True,
        text=True,
    )


def print_section(title: str) -> None:
    print(f"\n=== {title} ===")


@dataclass
class ContainerRevision:
    service: str
    container_id: str
    image: str
    revision_label: Optional[str]
    repo_digests: List[str]
    matched: bool


def revision_matches(revision: Optional[str], expected_sha: str) -> bool:
    if not revision:
        return False
    rev = revision.lower()
    exp = expected_sha.lower()
    if rev == exp:
        return True
    if rev.endswith(exp):
        return True
    return exp in rev


def collect_container_info(
    args: argparse.Namespace,
    ssh_base: Sequence[str],
    container_ids: Iterable[str],
) -> List[ContainerRevision]:
    revisions: List[ContainerRevision] = []
    for cid in container_ids:
        cid = cid.strip()
        if not cid:
            continue
        try:
            inspect = run_ssh(ssh_base, ["docker", "container", "inspect", cid])
        except subprocess.CalledProcessError as exc:
            print(f"- failed to inspect container {cid}: {exc.stderr.strip()}", file=sys.stderr)
            continue

        try:
            data = json.loads(inspect.stdout)[0]
        except (json.JSONDecodeError, IndexError) as err:
            print(f"- unable to parse inspect output for {cid}: {err}", file=sys.stderr)
            continue

        labels = data.get("Config", {}).get("Labels") or {}
        service = labels.get("com.docker.compose.service", "<unknown>")
        revision_label = labels.get("org.opencontainers.image.revision")
        image = data.get("Config", {}).get("Image", "<unknown>")
        repo_digests = data.get("RepoDigests") or []
        matched = revision_matches(revision_label, args.expected_sha)

        revisions.append(
            ContainerRevision(
                service=service,
                container_id=cid,
                image=image,
                revision_label=revision_label,
                repo_digests=repo_digests,
                matched=matched,
            )
        )
    return revisions


def human_short(value: str, length: int = 12) -> str:
    value = value or ""
    return value[:length]


def read_local_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_remote_sha256(
    args: argparse.Namespace,
    ssh_base: Sequence[str],
) -> Optional[str]:
    remote_cmd = [
        "docker",
        "compose",
        "-f",
        args.remote_compose,
        "exec",
        "-T",
        args.nginx_service,
        "sha256sum",
        args.remote_nginx_conf,
    ]
    try:
        result = run_ssh(ssh_base, remote_cmd)
    except subprocess.CalledProcessError as exc:
        print(f"- unable to calculate remote sha256: {exc.stderr.strip()}", file=sys.stderr)
        return None

    parts = result.stdout.strip().split()
    if not parts:
        return None
    return parts[0]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

    def http_error_302(self, req, fp, code, msg, headers):
        return fp

    http_error_301 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302
    http_error_308 = http_error_302


@dataclass
class HttpResult:
    endpoint: str
    status: Optional[int]
    final_url: Optional[str]
    redirects: int
    error: Optional[str]

    @property
    def ok(self) -> bool:
        if self.error:
            return False
        if self.status is None:
            return False
        return self.status < 400


def follow_http(
    base_url: str,
    endpoint: str,
    *,
    timeout: int,
    max_redirects: int,
) -> HttpResult:
    opener = urllib.request.build_opener(NoRedirect())
    opener.addheaders = [("User-Agent", "deploy-verifier/1.0")]

    current = urllib.parse.urljoin(base_url.rstrip("/") + "/", endpoint.lstrip("/"))
    redirects = 0

    while True:
        request = urllib.request.Request(current, method="GET")
        try:
            response = opener.open(request, timeout=timeout)
            status = response.getcode()
            location = response.getheader("Location")
            if status in REDIRECT_STATUSES and location and redirects < max_redirects:
                redirects += 1
                current = urllib.parse.urljoin(current, location)
                continue
            response.read()  # exhaust stream
            return HttpResult(endpoint=endpoint, status=status, final_url=current, redirects=redirects, error=None)
        except urllib.error.HTTPError as err:
            status = err.code
            location = err.headers.get("Location")
            if status in REDIRECT_STATUSES and location and redirects < max_redirects:
                redirects += 1
                current = urllib.parse.urljoin(current, location)
                continue
            body = err.read(256)
            error = f"HTTP {status}: {body.decode(errors='ignore')}"
            return HttpResult(endpoint=endpoint, status=status, final_url=current, redirects=redirects, error=error)
        except urllib.error.URLError as err:
            return HttpResult(endpoint=endpoint, status=None, final_url=current, redirects=redirects, error=str(err))
        except Exception as err:  # noqa: BLE001
            return HttpResult(endpoint=endpoint, status=None, final_url=current, redirects=redirects, error=str(err))
        if redirects >= max_redirects:
            return HttpResult(
                endpoint=endpoint,
                status=None,
                final_url=current,
                redirects=redirects,
                error=f"Exceeded max redirects ({max_redirects})",
            )


def main() -> int:
    args = parse_args()
    ensure_dependencies()

    expected_sha = args.expected_sha.strip()
    print_section("Expected revision")
    print(f"Commit: {expected_sha}")

    ssh_base = build_ssh_base_cmd(args)

    # Compose status
    print_section("docker compose ps")
    try:
        ps_output = run_ssh(ssh_base, ["docker", "compose", "-f", args.remote_compose, "ps"])
        print(ps_output.stdout.strip() or "(no output)")
    except subprocess.CalledProcessError as exc:
        print(exc.stdout)
        print(exc.stderr, file=sys.stderr)
        return 1

    try:
        ids_output = run_ssh(ssh_base, ["docker", "compose", "-f", args.remote_compose, "ps", "-q"])
        container_ids = [line.strip() for line in ids_output.stdout.splitlines() if line.strip()]
    except subprocess.CalledProcessError as exc:
        print(exc.stderr, file=sys.stderr)
        return 1

    if not container_ids:
        print("No containers reported by docker compose -f ps -q.", file=sys.stderr)
        return 1

    print_section("Image revision labels")
    revisions = collect_container_info(args, ssh_base, container_ids)
    revisions.sort(key=lambda r: r.service)

    all_ok = True
    for rev in revisions:
        status = "OK" if rev.matched else "MISMATCH"
        if not rev.matched:
            all_ok = False
        label_display = rev.revision_label or "<missing>"
        print(
            f"- {rev.service:<16} {status:<9} "
            f"label={label_display} image={rev.image} cid={human_short(rev.container_id)}"
        )

    if not revisions:
        print("No container metadata collected.", file=sys.stderr)
        all_ok = False

    # nginx.conf comparison
    if args.skip_nginx_conf:
        print_section("nginx.conf checksum")
        print("Skipped (per flag).")
    else:
        local_conf = os.path.abspath(args.local_nginx_conf)
        if not os.path.exists(local_conf):
            print_section("nginx.conf checksum")
            print(f"Local nginx.conf not found at {local_conf}", file=sys.stderr)
            all_ok = False
        else:
            local_hash = read_local_sha256(local_conf)
            remote_hash = read_remote_sha256(args, ssh_base)
            print_section("nginx.conf checksum")
            print(f"Local : {local_hash}  ({local_conf})")
            if remote_hash:
                print(f"Remote: {remote_hash}  ({args.remote_nginx_conf})")
                if local_hash != remote_hash:
                    print("WARNING: nginx.conf checksum differs from local copy.", file=sys.stderr)
                    all_ok = False
            else:
                print("Remote hash unavailable.", file=sys.stderr)
                all_ok = False

    # HTTP smoke tests
    if args.skip_http:
        print_section("HTTP probes")
        print("Skipped (per flag).")
    else:
        print_section("HTTP probes")
        http_ok = True
        for endpoint in args.http_endpoints:
            result = follow_http(
                args.base_url,
                endpoint,
                timeout=args.http_timeout,
                max_redirects=args.max_redirects,
            )
            marker = "OK" if result.ok else "FAIL"
            details = f"status={result.status} redirects={result.redirects} final={result.final_url}"
            if result.error:
                details += f" error={result.error}"
            print(f"- {endpoint:<12} {marker:<4} {details}")
            if not result.ok:
                http_ok = False
        if not http_ok:
            all_ok = False

    print()
    print("Overall:", "SUCCESS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit("\nInterrupted by user.")
