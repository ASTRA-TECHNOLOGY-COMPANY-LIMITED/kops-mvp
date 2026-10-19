"""Workbook access: .xlsb is converted once to .xlsx with LibreOffice (cached by sha256) so that
cell fills - which carry style status in ORDER RECAP - can be read with openpyxl."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import openpyxl

from . import config


class ExcelError(RuntimeError):
    pass


def open_workbook(path: Path, digest: str):
    path = Path(path)
    if path.suffix.lower() == ".xlsb":
        path = _xlsb_to_xlsx(path, digest)
    return openpyxl.load_workbook(path, data_only=True)


def _xlsb_to_xlsx(path: Path, digest: str) -> Path:
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = config.CACHE_DIR / f"{digest}.xlsx"
    if out.exists():
        return out
    soffice = config.find_soffice()
    if not soffice:
        raise ExcelError(
            "LibreOffice (soffice) is required to read .xlsb files. "
            "Install it (macOS: `brew install --cask libreoffice`) or set KOPS_SOFFICE.")
    with tempfile.TemporaryDirectory() as tmp:
        # Copy to a plain name: LibreOffice struggles with some unicode/paren file names.
        src = Path(tmp) / "src.xlsb"
        src.write_bytes(path.read_bytes())
        subprocess.run([soffice, "--headless", f"-env:UserInstallation=file://{tmp}/lo",
                        "--convert-to", "xlsx", "--outdir", tmp, str(src)],
                       check=True, capture_output=True, timeout=600)
        conv = Path(tmp) / "src.xlsx"
        if not conv.exists():
            raise ExcelError(f"LibreOffice did not convert {path.name}")
        out.write_bytes(conv.read_bytes())
    return out


def fill_key(cell) -> str | None:
    """Stable key for a cell's solid fill: 'FF92D050', 'theme7:0.4', 'idx64' or None."""
    try:
        f = cell.fill
        if not f or not f.fill_type:
            return None
        c = f.fgColor
        if c.type == "rgb":
            return c.rgb if isinstance(c.rgb, str) else None
        if c.type == "theme":
            return f"theme{c.theme}:{round(c.tint or 0, 2)}"
        if c.type == "indexed":
            return f"idx{c.indexed}"
    except Exception:  # openpyxl raises on some theme colours
        return None
    return None
