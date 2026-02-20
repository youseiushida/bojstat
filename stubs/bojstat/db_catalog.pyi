from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class DBInfo:
    '''DBコードの属性情報。

    Attributes:
        code: DBコード（例: "IR01"）。
        name_ja: DB名称（日本語）。
        category_ja: 統計分野（日本語）。
    '''
    code: str
    name_ja: str
    category_ja: str

DB_CATALOG: dict[str, DBInfo]

def list_dbs(*, category: str | None = None) -> list[DBInfo]:
    """DB一覧を返す。

    Args:
        category: 統計分野で部分一致フィルタ。Noneの場合は全件。

    Returns:
        条件に一致するDBInfo一覧。カタログ登録順を保持。
    """
def get_db_info(db: str) -> DBInfo | None:
    """DBコードから属性情報を取得する。

    Args:
        db: DBコード。大小文字不問。

    Returns:
        対応するDBInfo。未知の場合はNone。
    """
def is_known_db(db: str) -> bool:
    """既知のDBコードかどうか判定する。

    Args:
        db: DBコード。大小文字不問。

    Returns:
        既知ならTrue。
    """
