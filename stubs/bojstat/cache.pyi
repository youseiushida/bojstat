from bojstat.enums import CacheMode as CacheMode
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    def __init__(self, *, cache_dir: Path | None, ttl_seconds: int) -> None: ...
    def get(self, *, key: str, mode: CacheMode, allow_incomplete: bool = False) -> CacheHit | None:
        """キャッシュを読み取る。

        Args:
            key: キー文字列。
            mode: キャッシュモード。
            allow_incomplete: incompleteエントリの許可。

        Returns:
            ヒット時の情報。
        """
    def put(self, *, key: str, payload: dict[str, Any], complete: bool) -> None:
        """キャッシュを書き込む。"""
