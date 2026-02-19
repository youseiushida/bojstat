from bojstat.errors import BojPaginationStalledError as BojPaginationStalledError
from dataclasses import dataclass

@dataclass(slots=True)
class CodePagerState:
    """コードAPIページング状態。"""
    chunk_index: int
    start_position: int = ...

def advance_code_position(*, state: CodePagerState, next_position: int | None) -> bool:
    """次ページへ進むか判定して状態更新する。

    Args:
        state: 現在状態。
        next_position: API応答NEXTPOSITION。

    Returns:
        継続が必要ならTrue。

    Raises:
        BojPaginationStalledError: 位置が進行しない場合。
    """
