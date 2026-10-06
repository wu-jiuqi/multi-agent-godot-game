#!/usr/bin/env python3
"""Check whether the Penpot MCP endpoint is currently connected.

The checker deliberately has no Penpot client, network access, environment
variable lookup, or browser integration.  A caller injects a read-only probe
that reports a small JSON-compatible result, or supplies that result through
the CLI.  Only connection status and safe, non-secret metadata are returned.

Probe input:

    {"connected": true, "endpoint": "https://design.penpot.app/mcp"}

``connected`` must be a real boolean.  A probe may include ``provider``,
``server``, ``transport`` and an ``error`` object; unknown fields are ignored.
The CLI accepts the same object through ``--probe-json``, ``--probe-file`` or
stdin.  It never accepts or reads a token, cookie, header, or credential.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

STATE_CONNECTED = "connected"
STATE_DISCONNECTED = "disconnected"
STATE_ERROR = "error"
STATES = {STATE_CONNECTED, STATE_DISCONNECTED, STATE_ERROR}

_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_.-]{0,63}$")
_SECRET_RE = re.compile(
    r"(?i)(\b(?:token|secret|password|passwd|api[_-]?key|authorization)\b\s*[:=]\s*)[^\s,;]+"
)


def _checked_at(value: datetime | None = None) -> str:
    """Return a stable UTC timestamp for a result."""

    timestamp = value or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _redact_text(value: Any, *, limit: int = 500) -> str:
    """Convert probe text to bounded, credential-redacted display text."""

    text = str(value).strip()
    text = _SECRET_RE.sub(r"\1[REDACTED]", text)
    return text[:limit]


def _safe_code(value: Any, default: str) -> str:
    if isinstance(value, str):
        candidate = value.strip().upper()
        if _CODE_RE.fullmatch(candidate):
            return candidate
    return default


def _safe_endpoint(value: Any) -> str | None:
    """Keep an endpoint's origin/path while removing credentials and query data."""

    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    # urlsplit.hostname excludes userinfo.  Rebuild from the safe host and
    # path only, intentionally dropping query strings and fragments.
    host = parsed.hostname
    try:
        port = parsed.port
    except ValueError:
        return None
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = host
    if port is not None:
        netloc = f"{netloc}:{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def _safe_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {"provider": "penpot"}
    endpoint = _safe_endpoint(payload.get("endpoint"))
    if endpoint is not None:
        metadata["endpoint"] = endpoint
    for key in ("server", "transport"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            metadata[key] = _redact_text(value, limit=120)
    return metadata


def _error_from_probe(value: Any, *, default_code: str, default_message: str) -> dict[str, str]:
    if isinstance(value, Mapping):
        code = _safe_code(value.get("code"), default_code)
        message_value = value.get("message", value.get("detail"))
        if message_value is not None and str(message_value).strip():
            return {"code": code, "message": _redact_text(message_value)}
    elif value is not None and str(value).strip():
        return {"code": default_code, "message": _redact_text(value)}
    return {"code": default_code, "message": default_message}


def _result(
    state: str,
    *,
    checked_at: str,
    metadata: Mapping[str, Any] | None = None,
    error: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    output: dict[str, Any] = {
        "state": state,
        "checked_at": checked_at,
        "connection": {
            **dict(metadata or {"provider": "penpot"}),
            "connected": state == STATE_CONNECTED,
        },
        "error": dict(error) if error is not None else None,
    }
    return output


def check_penpot_mcp_connection(
    probe: Callable[[], Any],
    *,
    checked_at: datetime | None = None,
) -> dict[str, Any]:
    """Run an injected read-only probe and return a JSON-safe connection state.

    The probe owns all MCP-specific behavior.  It should return a mapping with
    ``connected: bool`` and may include safe metadata or ``error``.  Exceptions
    and malformed results become ``state=error``; a normal ``connected=false``
    result becomes ``state=disconnected``.  The function never retries,
    writes, logs in, or reads credentials.
    """

    timestamp = _checked_at(checked_at)
    try:
        raw = probe()
    except Exception:
        return _result(
            STATE_ERROR,
            checked_at=timestamp,
            error={"code": "PROBE_FAILED", "message": "Penpot MCP 探针执行失败"},
        )

    if isinstance(raw, bool):
        payload: Mapping[str, Any] = {"connected": raw}
    elif isinstance(raw, Mapping):
        payload = raw
    else:
        return _result(
            STATE_ERROR,
            checked_at=timestamp,
            error={"code": "PROBE_INVALID", "message": "探针必须返回布尔值或 JSON 对象"},
        )

    connected = payload.get("connected")
    if type(connected) is not bool:
        return _result(
            STATE_ERROR,
            checked_at=timestamp,
            metadata=_safe_metadata(payload),
            error={"code": "PROBE_INVALID", "message": "探针结果的 connected 必须是布尔值"},
        )

    metadata = _safe_metadata(payload)
    supplied_error = payload.get("error")
    if connected:
        if supplied_error is not None:
            return _result(
                STATE_ERROR,
                checked_at=timestamp,
                metadata=metadata,
                error=_error_from_probe(
                    supplied_error,
                    default_code="PROBE_INCONSISTENT",
                    default_message="探针同时报告 connected=true 和 error",
                ),
            )
        return _result(STATE_CONNECTED, checked_at=timestamp, metadata=metadata)

    return _result(
        STATE_DISCONNECTED,
        checked_at=timestamp,
        metadata=metadata,
        error=_error_from_probe(
            supplied_error,
            default_code="NOT_CONNECTED",
            default_message="Penpot MCP 当前未连接",
        ),
    )


# Keep the validator discoverable by callers that use the repository's
# ``validate_*`` naming convention while retaining the explicit ``check_*``
# name for dependency injection at call sites.
validate_penpot_connection = check_penpot_mcp_connection


def _read_probe_input(args: argparse.Namespace) -> Any:
    if args.probe_json is not None and args.probe_file is not None:
        raise ValueError("--probe-json 与 --probe-file 不能同时使用")
    if args.probe_json is not None:
        return json.loads(args.probe_json)
    if args.probe_file is not None:
        try:
            source = sys.stdin if str(args.probe_file) == "-" else args.probe_file.open("r", encoding="utf-8")
            try:
                text = source.read()
            finally:
                if source is not sys.stdin:
                    source.close()
        except OSError as exc:
            raise ValueError("无法读取探针输入文件") from exc
    else:
        text = sys.stdin.read()
    if not text.strip():
        raise ValueError("缺少探针 JSON 输入")
    return json.loads(text)


def _error_result(exc: Exception) -> dict[str, Any]:
    code = "INPUT_INVALID" if isinstance(exc, (json.JSONDecodeError, ValueError)) else "INPUT_FAILED"
    message = "探针 JSON 输入无效" if isinstance(exc, json.JSONDecodeError) else _redact_text(exc)
    return _result(
        STATE_ERROR,
        checked_at=_checked_at(),
        error={"code": code, "message": message},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-json", help="JSON 探针结果；只应包含 connected 与非敏感元数据")
    parser.add_argument("--probe-file", type=Path, help="包含 JSON 探针结果的文件，使用 - 表示 stdin")
    args = parser.parse_args(argv)
    try:
        payload = _read_probe_input(args)
        result = check_penpot_mcp_connection(lambda: payload)
    except Exception as exc:  # Keep CLI output JSON-only for automation.
        result = _error_result(exc)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return {STATE_CONNECTED: 0, STATE_DISCONNECTED: 2, STATE_ERROR: 3}[result["state"]]


if __name__ == "__main__":
    raise SystemExit(main())
