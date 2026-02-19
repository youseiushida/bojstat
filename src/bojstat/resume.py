"""再開トークン処理。"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from bojstat.config import TOKEN_VERSION
from bojstat.errors import BojResumeTokenMismatchError
from bojstat.types import ResumeTokenState


_REASON_MAP = {
    "token_version": "token_version_mismatch",
    "request_fingerprint": "fingerprint_mismatch",
    "chunk_index": "chunk_index_mismatch",
    "parser_version": "parser_version_mismatch",
    "normalizer_version": "normalizer_version_mismatch",
}


def build_request_fingerprint(components: dict[str, Any]) -> str:
    """要求構成要素から指紋を生成する。"""

    serialized = json.dumps(components, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def encode_resume_token(payload: dict[str, Any]) -> str:
    """再開トークンをエンコードする。"""

    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_resume_token(token: str) -> ResumeTokenState:
    """再開トークンを復元する。"""

    decoded = base64.urlsafe_b64decode(token.encode("ascii"))
    payload = json.loads(decoded.decode("utf-8"))
    return ResumeTokenState(
        token_version=int(payload["token_version"]),
        api=str(payload["api"]),
        api_origin=str(payload["api_origin"]),
        request_fingerprint=str(payload["request_fingerprint"]),
        chunk_index=int(payload["chunk_index"]),
        next_position=int(payload["next_position"]),
        lang=str(payload["lang"]),
        format=str(payload["format"]),
        parser_version=str(payload["parser_version"]),
        normalizer_version=str(payload["normalizer_version"]),
        schema_version=str(payload["schema_version"]),
        code_order_map={str(k): int(v) for k, v in dict(payload["code_order_map"]).items()},
    )


def create_resume_token(
    *,
    api: str,
    api_origin: str,
    request_fingerprint: str,
    chunk_index: int,
    next_position: int,
    lang: str,
    format: str,
    parser_version: str,
    normalizer_version: str,
    schema_version: str,
    code_order_map: dict[str, int],
) -> str:
    """再開トークンを生成する。"""

    payload: dict[str, Any] = {
        "token_version": TOKEN_VERSION,
        "api": api,
        "api_origin": api_origin,
        "request_fingerprint": request_fingerprint,
        "chunk_index": chunk_index,
        "next_position": next_position,
        "lang": lang,
        "format": format,
        "parser_version": parser_version,
        "normalizer_version": normalizer_version,
        "schema_version": schema_version,
        "code_order_map": code_order_map,
    }
    return encode_resume_token(payload)


def validate_resume_token(
    state: ResumeTokenState,
    *,
    request_fingerprint: str,
    chunk_index: int,
    parser_version: str,
    normalizer_version: str,
) -> None:
    """再開トークンの整合性を検証する。"""

    checks = {
        "token_version": (state.token_version, TOKEN_VERSION),
        "request_fingerprint": (state.request_fingerprint, request_fingerprint),
        "chunk_index": (state.chunk_index, chunk_index),
        "parser_version": (state.parser_version, parser_version),
        "normalizer_version": (state.normalizer_version, normalizer_version),
    }
    for key, pair in checks.items():
        actual, expected = pair
        if actual != expected:
            reason = _REASON_MAP[key]
            raise BojResumeTokenMismatchError(
                f"resume_token 不一致: {key}",
                reason=reason,
            )
