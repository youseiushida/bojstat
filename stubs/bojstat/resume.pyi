from bojstat.config import TOKEN_VERSION as TOKEN_VERSION
from bojstat.errors import BojResumeTokenMismatchError as BojResumeTokenMismatchError
from bojstat.types import ResumeTokenState as ResumeTokenState
from typing import Any

def build_request_fingerprint(components: dict[str, Any]) -> str:
    """要求構成要素から指紋を生成する。"""
def encode_resume_token(payload: dict[str, Any]) -> str:
    """再開トークンをエンコードする。"""
def decode_resume_token(token: str) -> ResumeTokenState:
    """再開トークンを復元する。"""
def create_resume_token(*, api: str, api_origin: str, request_fingerprint: str, chunk_index: int, next_position: int, lang: str, format: str, parser_version: str, normalizer_version: str, schema_version: str, code_order_map: dict[str, int]) -> str:
    """再開トークンを生成する。"""
def validate_resume_token(state: ResumeTokenState, *, request_fingerprint: str, chunk_index: int, parser_version: str, normalizer_version: str) -> None:
    """再開トークンの整合性を検証する。"""
