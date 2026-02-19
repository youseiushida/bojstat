"""階層API用ページャ。"""

from __future__ import annotations

from dataclasses import dataclass

from bojstat.errors import BojPaginationStalledError


@dataclass(slots=True)
class LayerPagerState:
    """階層APIページング状態。"""

    start_position: int = 1


def advance_layer_position(*, state: LayerPagerState, next_position: int | None) -> bool:
    """次ページへ進むか判定して状態更新する。

    Args:
        state: 現在状態。
        next_position: API応答NEXTPOSITION。

    Returns:
        継続が必要ならTrue。

    Raises:
        BojPaginationStalledError: 位置が進行しない場合。
    """

    if next_position is None:
        return False
    if next_position <= state.start_position:
        raise BojPaginationStalledError(
            chunk_index=0,
            start=state.start_position,
            next_position=next_position,
        )
    state.start_position = next_position
    return True
