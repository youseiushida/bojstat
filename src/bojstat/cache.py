"""ローカルキャッシュ。"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from bojstat.enums import CacheMode


@dataclass(slots=True)
class CacheHit:
    """キャッシュ読み取り結果。

    Attributes:
        payload: 保存済み内容。
        stale: stale判定。
    """

    payload: dict[str, Any]
    stale: bool


class FileCache:
    """JSONファイルベースキャッシュ。"""

    def __init__(self, *, cache_dir: Path | None, ttl_seconds: int) -> None:
        self._cache_dir = cache_dir
        self._ttl_seconds = ttl_seconds
        self._lock = Lock()
        if self._cache_dir is not None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _path_for_key(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        assert self._cache_dir is not None
        return self._cache_dir / f"{digest}.json"

    def get(
        self,
        *,
        key: str,
        mode: CacheMode,
        allow_incomplete: bool = False,
    ) -> CacheHit | None:
        """キャッシュを読み取る。

        Args:
            key: キー文字列。
            mode: キャッシュモード。
            allow_incomplete: incompleteエントリの許可。

        Returns:
            ヒット時の情報。
        """

        if self._cache_dir is None or mode == CacheMode.OFF:
            return None
        if mode == CacheMode.FORCE_REFRESH:
            return None

        path = self._path_for_key(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            quarantine = path.with_suffix(path.suffix + ".broken")
            try:
                path.replace(quarantine)
            except OSError:
                pass
            return None

        if not allow_incomplete and not payload.get("complete", False):
            return None

        created_at = float(payload.get("created_at", 0.0))
        stale = (time.time() - created_at) > self._ttl_seconds
        return CacheHit(payload=payload, stale=stale)

    def put(self, *, key: str, payload: dict[str, Any], complete: bool) -> None:
        """キャッシュを書き込む。"""

        if self._cache_dir is None:
            return
        path = self._path_for_key(key)
        body = {
            "created_at": time.time(),
            "complete": complete,
            "payload": payload,
        }
        data = json.dumps(body, ensure_ascii=False, separators=(",", ":"))

        with self._lock:
            fd, tmp_path = tempfile.mkstemp(
                prefix=path.name,
                suffix=".tmp",
                dir=str(self._cache_dir),
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(data)
                Path(tmp_path).replace(path)
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
