"""CLIエントリポイント。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _require_typer() -> Any:
    try:
        import typer
    except ImportError as exc:
        raise RuntimeError(
            "CLIには typer が必要です。pip install 'bojstat[cli]' を実行してください。"
        ) from exc
    return typer


def _dump_frame(frame: Any, out: Path) -> None:
    suffix = out.suffix.lower()
    if suffix == ".json":
        payload = {
            "meta": frame.meta.__dict__,
            "records": frame.to_long(numeric_mode="string") if hasattr(frame, "to_long") else [],
        }
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return
    if suffix == ".csv":
        df = frame.to_pandas()
        df.to_csv(out, index=False)
        return
    if suffix == ".parquet":
        try:
            import pyarrow  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "Parquet backend is required. pip install 'bojstat[cli]' を実行してください。"
            ) from exc
        df = frame.to_pandas()
        df.to_parquet(out, index=False)
        return
    raise ValueError("出力拡張子は .json / .csv / .parquet のみ対応です。")


def app_entry() -> None:
    """CLIアプリを起動する。"""

    typer = _require_typer()
    from bojstat import BojClient

    app = typer.Typer(no_args_is_help=True)

    @app.command("metadata")
    def metadata_command(
        db: str = typer.Option(..., "--db"),
        lang: str = typer.Option("jp", "--lang"),
        out: Path = typer.Option(..., "--out"),
    ) -> None:
        """メタデータを取得する。"""

        with BojClient(lang=lang) as client:
            frame = client.metadata.get(db=db)
            _dump_frame(frame, out)

    @app.command("code")
    def code_command(
        db: str = typer.Option(..., "--db"),
        code: str = typer.Option(..., "--code"),
        start: str | None = typer.Option(None, "--start"),
        end: str | None = typer.Option(None, "--end"),
        lang: str = typer.Option("jp", "--lang"),
        out: Path = typer.Option(..., "--out"),
    ) -> None:
        """コードAPIで時系列を取得する。"""

        with BojClient(lang=lang) as client:
            frame = client.data.get_by_code(
                db=db,
                code=code,
                start=start,
                end=end,
            )
            _dump_frame(frame, out)

    @app.command("layer")
    def layer_command(
        db: str = typer.Option(..., "--db"),
        frequency: str = typer.Option(..., "--frequency"),
        layer: str = typer.Option(..., "--layer"),
        start: str | None = typer.Option(None, "--start"),
        end: str | None = typer.Option(None, "--end"),
        lang: str = typer.Option("jp", "--lang"),
        out: Path = typer.Option(..., "--out"),
    ) -> None:
        """階層APIで時系列を取得する。"""

        with BojClient(lang=lang) as client:
            frame = client.data.get_by_layer(
                db=db,
                frequency=frequency,
                layer=layer,
                start=start,
                end=end,
            )
            _dump_frame(frame, out)

    app()


if __name__ == "__main__":
    app_entry()
