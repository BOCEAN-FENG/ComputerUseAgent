# -*- coding: utf-8 -*-
"""Append-only local lifecycle trace, separate from the API response journal.

Never persists task text, screenshots, reply bodies or API keys. The trace can
identify at which stage an execution terminated, even if no further HTTP call
was issued after the last valid response.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class RunTrace:
    def __init__(self, response_file: Path):
        self.path = Path(response_file).with_name('run-' + Path(response_file).name)
        self.path.touch(exist_ok=False)

    def add(self, phase: str, step: int | None = None, **metadata):
        safe = {k: v for k, v in metadata.items()
                if k in {'action', 'state', 'error_type', 'status', 'video_index',
                         'video_target', 'attempt', 'message_code', 'duration_ms'}}
        record = {'time': datetime.now().astimezone().isoformat(timespec='milliseconds'),
                  'phase': phase, 'step': step, **safe}
        with self.path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
            f.flush()
