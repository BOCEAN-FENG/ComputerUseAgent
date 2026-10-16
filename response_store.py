# -*- coding: utf-8 -*-
"""Durable, per-request API-response journal.

Only server *responses* are stored (not outbound images, prompts or headers).
Records are JSONL, readable in the GUI and after a crash. Exact configured
API keys are redacted if an unusual provider echoes them in a response.
"""
from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_RESPONSE_CHARS = 2_000_000
SESSION_PREFIX = 'api-'


def response_directory() -> Path:
    base = os.getenv('LOCALAPPDATA')
    if base:
        return Path(base) / 'AuroraComputerStudio' / 'api_responses'
    return Path.home() / '.aurora-computer-studio' / 'api_responses'


def list_sessions(folder: Path | None = None) -> list[Path]:
    folder = Path(folder) if folder else response_directory()
    return sorted(folder.glob('api-*.jsonl'), key=lambda p: p.name, reverse=True) if folder.exists() else []


def read_records(session_file: Path) -> list[dict[str, Any]]:
    """Only open a journal inside the response directory (avoid path traversal)."""
    target = Path(session_file).resolve()
    directory = response_directory().resolve()
    if target.parent != directory or not target.name.startswith(SESSION_PREFIX) or target.suffix != '.jsonl':
        raise ValueError('只能读取 Aurora API 响应记录目录下的 JSONL 文件。')
    entries = []
    with target.open('r', encoding='utf-8') as f:
        for line in f:
            try:
                record = json.loads(line)
                if isinstance(record, dict):
                    entries.append(record)
            except json.JSONDecodeError:
                # If the process ended mid-write, preserve previous valid lines.
                continue
    return entries


def _redact(text: Any, api_key: str) -> str:
    if text is None:
        return ''
    value = str(text)
    if api_key:
        value = value.replace(api_key, '[REDACTED_API_KEY]')
    return value


def _trim(value: str) -> tuple[str, bool]:
    return (value[:MAX_RESPONSE_CHARS], True) if len(value) > MAX_RESPONSE_CHARS else (value, False)


class ResponseStore:
    def __init__(self, folder: Path | None = None, *, label: str = 'task'):
        self.folder = Path(folder) if folder else response_directory()
        self.folder.mkdir(parents=True, exist_ok=True)
        # Timestamp + random suffix ensures unique session files even across processes.
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        safe_label = re.sub('[^a-zA-Z0-9_-]', '', label)[:16] or 'task'
        self.path = self.folder / f'api-{stamp}-{safe_label}-{secrets.token_hex(3)}.jsonl'
        self.path.touch(exist_ok=False)

    def append(self, event: dict[str, Any], *, api_key: str) -> dict[str, Any]:
        """Append each HTTP reply immediately, before subsequent model actions run."""
        raw, truncated = _trim(_redact(event.get('raw_body'), api_key))
        content, content_truncated = _trim(_redact(event.get('model_content'), api_key))
        record = {
            'time': datetime.now().astimezone().isoformat(timespec='milliseconds'),
            'phase': str(event.get('phase', 'action')),
            'step': event.get('step'),
            'model': _redact(event.get('model', ''), api_key),
            'http_status': event.get('http_status'),
            'parse_status': str(event.get('parse_status', 'unknown')),
            'parse_error': _redact(event.get('parse_error', ''), api_key),
            'model_content': content,
            'raw_body': raw,
            'response_truncated': truncated,
            'content_truncated': content_truncated,
        }
        # Do not repeat API keys in outbound headers; store only the returned body.
        with self.path.open('a', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n')
            f.flush()
        record['session_path'] = str(self.path)
        return record
