#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timezone
from typing import Any

import hvac
import requests

from src.objects.slack_base import SlackClient

DEFAULT_VAULT_ADDR = "https://vault.ci.openshift.org"
DEFAULT_VAULT_KV_PATH = "kv/selfservice/firewatch-tool/jira-credentials"
NOTIFY_THRESHOLDS_DAYS = (30, 14, 7, 3, 1)


def eprint(*args: Any, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)


def split_kv_mount_and_path(full_path: str) -> tuple[str, str]:
    p = full_path.strip().strip("/")
    if "/" not in p:
        raise ValueError(f"invalid KV path (expected mount/path): {full_path!r}")
    mount, rest = p.split("/", 1)
    if not mount or not rest:
        raise ValueError(f"invalid KV path: {full_path!r}")
    return mount, rest


def read_secret_from_vault(
    vault_addr: str,
    vault_token: str,
    kv_path: str,
) -> dict[str, Any]:
    mount, path = split_kv_mount_and_path(kv_path)
    client = hvac.Client(url=vault_addr, token=vault_token)
    if not client.is_authenticated():
        raise RuntimeError("Vault authentication failed")
    resp = client.secrets.kv.v2.read_secret_version(path=path, mount_point=mount)
    data = resp.get("data", {}).get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Vault response missing secret data")
    return data


def parse_expiry_date(expires_at: str) -> date:
    s = expires_at.strip()
    if not s:
        raise ValueError("expires_at is empty")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as exc:
        raise ValueError(f"invalid expires_at ISO 8601: {expires_at!r}") from exc
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
        return dt.date()
    return dt.date()


def days_until_expiry(expiry: date, today: date | None = None) -> int:
    ref = today if today is not None else date.today()
    return (expiry - ref).days


def should_notify_approaching(days_left: int) -> bool:
    return 1 <= days_left <= max(NOTIFY_THRESHOLDS_DAYS)


def build_approaching_message(
    kv_path: str,
    days_left: int,
    expiry: date,
) -> str:
    return (
        f"Firewatch Jira API token is approaching expiration.\n"
        f"KV path: {kv_path}\n"
        f"Days remaining: {days_left}\n"
        f"Expiry date: {expiry.isoformat()}\n"
        f"Follow the token rotation runbook to renew before expiry."
    )


def build_expired_message(kv_path: str, expiry: date, days_overdue: int) -> str:
    return (
        f"URGENT: Firewatch Jira API token has expired.\n"
        f"KV path: {kv_path}\n"
        f"Expiry date: {expiry.isoformat()}\n"
        f"Expired {days_overdue} day(s) ago.\n"
        f"Rotate immediately using the token rotation runbook."
    )


def build_expires_today_message(kv_path: str, expiry: date) -> str:
    return (
        f"URGENT: Firewatch Jira API token expires today.\n"
        f"KV path: {kv_path}\n"
        f"Expiry date: {expiry.isoformat()}\n"
        f"Rotate immediately using the token rotation runbook."
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Check Firewatch Jira token expiry and alert Slack.")
    p.add_argument(
        "--vault-addr",
        default=os.environ.get("VAULT_ADDR", DEFAULT_VAULT_ADDR),
        help=f"Vault address (default: env VAULT_ADDR or {DEFAULT_VAULT_ADDR})",
    )
    p.add_argument(
        "--vault-token",
        default=os.environ.get("VAULT_TOKEN"),
        help="Vault token (default: env VAULT_TOKEN)",
    )
    p.add_argument(
        "--vault-kv-path",
        default=os.environ.get("VAULT_KV_PATH", DEFAULT_VAULT_KV_PATH),
        help="KV secret path mount/rest (default: env VAULT_KV_PATH or built-in default)",
    )
    p.add_argument(
        "--slack-webhook-url",
        default=os.environ.get("SLACK_WEBHOOK_URL"),
        help="Slack incoming webhook URL (default: env SLACK_WEBHOOK_URL)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.vault_token:
        eprint("error: VAULT_TOKEN or --vault-token is required")
        return 1
    if not args.slack_webhook_url:
        eprint("error: SLACK_WEBHOOK_URL or --slack-webhook-url is required")
        return 1

    try:
        secret = read_secret_from_vault(
            args.vault_addr,
            args.vault_token,
            args.vault_kv_path,
        )
    except Exception as exc:
        eprint(f"error: Vault read failed: {exc}")
        return 1

    raw_expires = secret.get("expires_at")
    if raw_expires is None:
        eprint("error: secret missing expires_at")
        return 1
    if not isinstance(raw_expires, str):
        eprint("error: expires_at must be a string")
        return 1

    try:
        expiry = parse_expiry_date(raw_expires)
    except ValueError as exc:
        eprint(f"error: {exc}")
        return 1

    days_left = days_until_expiry(expiry)
    eprint(f"expires_at={expiry.isoformat()} days_remaining={days_left}")

    try:
        if days_left < 0:
            msg = build_expired_message(args.vault_kv_path, expiry, abs(days_left))
            SlackClient.post_webhook(args.slack_webhook_url, msg)
            eprint("sent Slack: expired token alert")
            return 2
        if days_left == 0:
            msg = build_expires_today_message(args.vault_kv_path, expiry)
            SlackClient.post_webhook(args.slack_webhook_url, msg)
            eprint("sent Slack: expires today alert")
            return 2
        if should_notify_approaching(days_left):
            msg = build_approaching_message(args.vault_kv_path, days_left, expiry)
            SlackClient.post_webhook(args.slack_webhook_url, msg)
            eprint("sent Slack: approaching expiry")
        else:
            eprint("no notification (outside alert window)")
    except requests.RequestException as exc:
        eprint(f"error: Slack webhook request failed: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
