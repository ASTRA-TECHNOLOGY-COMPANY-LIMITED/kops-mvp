"""Synthetic data, acceptance scenarios and benchmark for large historical loads (H-06, H-08, H-13).

Everything is written OUTSIDE the repo (a folder you pass, e.g. under /tmp) and never committed: generated files are
derived from the real KLMAS files in raw-docs (copied with a changed ZIP comment, so contents stay identical).

  python -m kops_dw bench accept --out DIR     acceptance checks of HISTORY_SCALE_PLAN (incremental, quarantine,
                                               unknown template, mbox 1,000 messages, OCR) on copies in DIR
  python -m kops_dw bench gen --out DIR [--files 5000] [--mails 50000]
  python -m kops_dw bench run --out DIR        cold build, warm build, +10 files/+100 mails; report DIR/bench.md
Each build runs in a subprocess with KOPS_RAW_DOCS / KOPS_INBOX / KOPS_BUILD pointing into DIR.
"""
from __future__ import annotations

import datetime as dt
import json
import mailbox
import os
import random
import shutil
import subprocess
import sys
import time
import zipfile
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from pathlib import Path

from . import config

PY = sys.executable
SUBJECTS = [
    ("en", "[{s}] Qty reduction request", "Dear team,\nPlease reduce {s} by 10% for all colours.\nRegards"),
    ("en", "[{s}] ETD change", "Hi,\nBuyer asks to move ETD of {s} to {d}.\nThanks"),
    ("en", "RE: [{s}] fabric arrival", "Fabric for {s} will arrive at factory on {d}. Please update the plan."),
    ("ko", "[{s}] 수량 변경 요청", "안녕하세요.\n{s} 수량을 10% 감량 요청드립니다.\n납기는 {d} 입니다.\n감사합니다."),
    ("ko", "[{s}] 샘플 코멘트", "{s} 탑샘플 코멘트 전달드립니다. 원단 컬러 확인 부탁드립니다."),
    ("vi", "[{s}] Trễ giao hàng", "Chào chị,\nNhà máy báo {s} sẽ trễ giao hàng, dự kiến xuất {d}.\nCảm ơn chị."),
    ("vi", "[{s}] Xác nhận số lượng", "Em gửi lại số lượng cuối cùng của mã {s}, nhờ chị kiểm tra giúp em."),
]
AUTOMATED = [
    {"From": "no-reply@shipping-portal.example", "Subject": "Your booking {n} is confirmed",
     "Auto-Submitted": "auto-generated"},
    {"From": "newsletter@fabric-fair.example", "Subject": "Fabric fair {n}: register now",
     "List-Unsubscribe": "<mailto:unsub@fabric-fair.example>"},
    {"From": "MAILER-DAEMON@mail.example", "Subject": "Undeliverable: order {n}"},
    {"From": "kim.colleague@klmas.example", "Subject": "Automatic reply: out of office {n}"},
    {"From": "promo@supplier.example", "Subject": "Big sale {n}", "Precedence": "bulk"},
]


# ---------------------------------------------------------------- generators
def style_codes(limit=400) -> list[str]:
    """Real style codes from the last build (so emails match the style dictionary), else synthetic ones."""
    try:
        import duckdb
        con = duckdb.connect(str(config.DB_PATH), read_only=True)
        codes = [r[0] for r in con.execute(f"SELECT DISTINCT style_no FROM core.style_dictionary LIMIT {limit}").fetchall()]
        con.close()
        if codes:
            return codes
    except Exception:
        pass
    return [f"CHF{random.randint(1, 4)}MPT{random.randint(6000, 7999)}" for _ in range(limit)]


def make_mbox(path: Path, n: int, dup_rate=0.05, auto_rate=0.08, seed=1, start=dt.datetime(2024, 1, 1),
              tag="") -> dict:
    """An .mbox of n messages: business mails in EN/KO/VI, exact duplicates (same message under another Gmail
    label, as Takeout exports it) and automated mails. Returns the expected counts."""
    rnd = random.Random(seed)
    codes = style_codes()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    box = mailbox.mbox(str(path))
    n_auto = int(n * auto_rate)
    n_dup = int(n * dup_rate)
    n_biz = n - n_auto - n_dup
    biz = []
    box.lock()
    try:
        for i in range(n_biz):
            lang, subj, body = rnd.choice(SUBJECTS)
            s = rnd.choice(codes)
            sent = start + dt.timedelta(minutes=rnd.randint(0, 2 * 365 * 24 * 60))
            m = EmailMessage()
            m["From"] = rnd.choice(["Lee Sujin <sujin.lee@buyer-a.example>", "Nguyen Lan <lan@klmas.example>",
                                    "Park Minho <minho@buyer-b.example>", "Tran Hung <hung@factory.example>"])
            m["To"] = "orders@klmas.example"
            m["Date"] = format_datetime(sent)
            m["Subject"] = subj.format(s=s) + f" #{tag}{i}"
            m["Message-ID"] = make_msgid(domain="bench.example")
            m["X-Gmail-Labels"] = rnd.choice(["Inbox", "Inbox,Important", "Sent", "CHALLENGER", "DHG"])
            m.set_content(body.format(s=s, d=(sent + dt.timedelta(days=30)).strftime("%d/%m/%Y")))
            box.add(m)
            biz.append(m)
        for i in range(n_auto):
            a = rnd.choice(AUTOMATED)
            m = EmailMessage()
            for k, v in a.items():
                m[k] = v.format(n=f"{tag}{i}")
            m["To"] = "orders@klmas.example"
            m["Date"] = format_datetime(start + dt.timedelta(minutes=rnd.randint(0, 2 * 365 * 24 * 60)))
            m["Message-ID"] = make_msgid(domain="bench.example")
            m.set_content("This is an automated message.")
            box.add(m)
        for i in range(n_dup):
            m = rnd.choice(biz)
            dup = EmailMessage()
            for k, v in m.items():
                if k != "X-Gmail-Labels":
                    dup[k] = v
            dup["X-Gmail-Labels"] = "Archived"
            dup.set_content(m.get_content())
            box.add(dup)
    finally:
        box.flush()
        box.unlock()
        box.close()
    return dict(messages=n, business=n_biz, automated=n_auto, duplicates=n_dup)


def make_scanned_pdf(path: Path) -> bool:
    """A scanned (image-only) email print in KO / VI / EN for the OCR test. Needs Pillow + a CJK font."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False
    font = next((f for f in ["/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "/System/Library/Fonts/AppleSDGothicNeo.ttc",
                             "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                             "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"] if Path(f).exists()), None)
    if not font:
        return False
    f = ImageFont.truetype(font, 34)
    lines = ["From: Lee Sujin <sujin.lee@buyer-a.example>", "Sent: Monday, October 19, 2026 10:15 AM",
             "To: orders@klmas.example", "Subject: [SCAN] CHF4MPT6444 납기 지연",
             "", "안녕하세요. CHF4MPT6444 납기 지연 관련 확인 부탁드립니다.",
             "Nhà máy báo trễ giao hàng, dự kiến xuất ngày 30/10/2026.", "ETD 2026-10-30, quantity 1200 pcs."]
    img = Image.new("RGB", (1700, 2200), "white")
    d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        d.text((120, 150 + i * 70), ln, font=f, fill="black")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PDF", resolution=200.0)
    return True


def _copy_variant(src: Path, dest: Path, tag: str):
    """Same workbook, different bytes (ZIP comment) -> a distinct file for the manifest and the lake."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    with zipfile.ZipFile(dest, "a") as z:
        z.comment = f"kops-bench {tag}".encode()


def _sources(raw: Path) -> list[Path]:
    """Real parseable Excel files (xlsb replaced by their cached xlsx conversion) as templates for copies."""
    from .pipeline import classify
    from .util import sha256
    out = []
    for p in sorted(raw.rglob("*")):
        if not p.is_file() or any(x.startswith(("_", ".")) for x in p.relative_to(raw).parts):
            continue
        stype, parser, _ = classify(p)
        if p.suffix.lower() == ".xlsx" or (p.suffix.lower() == ".xlsb" and (config.CACHE_DIR / f"{sha256(p)}.xlsx").exists()):
            out.append(p)
    return out


def gen(out: Path, n_files=5000, n_mails=50000, seed=7):
    """DIR/raw: n_files Excel copies named like KLMAS files over seasons 24SS..27SS (plus the real non-Excel files);
    DIR/inbox: n_mails messages in 10 .mbox files + 1,000 single .eml files."""
    from .util import sha256
    rnd = random.Random(seed)
    raw, inbox = out / "raw", out / "inbox"
    shutil.rmtree(raw, ignore_errors=True)
    shutil.rmtree(inbox, ignore_errors=True)
    srcs = _sources(config.RAW_DOCS_DIR)
    seasons = ["24SS", "24FW", "25SS", "25FW", "26SS", "26FW", "27SS"]
    for i in range(n_files):
        src = srcs[i % len(srcs)]
        real = config.CACHE_DIR / f"{sha256(src)}.xlsx" if src.suffix.lower() == ".xlsb" else src
        season = seasons[i % len(seasons)]
        day = dt.date(2000 + int(season[:2]) - 1, 7, 1) + dt.timedelta(days=rnd.randint(0, 360))
        name = re_season(src.name, season)
        name = day.strftime("%y%m%d") + name[6:] if name[:6].isdigit() else f"{day:%y%m%d} {name}"
        _copy_variant(real, raw / "HISTORY" / season / f"{i:05d}" / (Path(name).stem + ".xlsx"), f"{i}")
    n_eml = min(1000, n_mails // 10)
    per_box = (n_mails - n_eml) // 10
    expected = dict(files=n_files, mbox=[])
    for b in range(10):
        expected["mbox"].append(make_mbox(inbox / f"takeout_{b:02d}.mbox", per_box, seed=seed + b, tag=f"b{b}-"))
    tmp = inbox / "_tmp.mbox"
    make_mbox(tmp, n_eml, dup_rate=0, auto_rate=0, seed=seed + 99, tag="eml-")
    box = mailbox.mbox(str(tmp))
    for i, key in enumerate(box.iterkeys()):
        (inbox / "eml" / f"{i // 200:02d}").mkdir(parents=True, exist_ok=True)
        (inbox / "eml" / f"{i // 200:02d}" / f"{i:05d}.eml").write_bytes(box.get_bytes(key))
    box.close()
    tmp.unlink()
    expected["eml"] = n_eml
    (out / "expected.json").write_text(json.dumps(expected, indent=1))
    print(f"Generated {n_files} Excel files in {raw} and {per_box * 10 + n_eml} messages in {inbox}")


def re_season(name: str, season: str) -> str:
    import re
    return re.sub(r"\b2\d(SS|FW)\b", season, name, count=1) if re.search(r"\b2\d(SS|FW)\b", name) else f"{season} {name}"


# ---------------------------------------------------------------- running builds
def _env(out: Path, raw: Path | None = None, inbox: Path | None = None, **extra) -> dict:
    env = dict(os.environ)
    env.update(KOPS_RAW_DOCS=str(raw or out / "raw"), KOPS_INBOX=str(inbox or out / "inbox"),
               KOPS_BUILD=str(out / "build"), **{k: str(v) for k, v in extra.items()})
    return env


def run_build(env: dict, *args) -> dict:
    """Run `python -m kops_dw build` in a subprocess; returns seconds, peak RSS (largest process) and the run row."""
    import tempfile
    t0 = time.time()
    with tempfile.TemporaryFile("w+") as log:
        p = subprocess.Popen([PY, "-m", "kops_dw", "build", *args], cwd=config.DW_DIR, env=env, stdout=log,
                             stderr=subprocess.STDOUT, text=True)
        _, status, usage = os.wait4(p.pid, 0)       # rusage of the build and of the workers it waited for
        p.returncode = os.waitstatus_to_exitcode(status)
        log.seek(0)
        stdout = log.read()
    secs = time.time() - t0
    rss_mb = usage.ru_maxrss / ((1 << 20) if sys.platform == "darwin" else 1024)
    if p.returncode:
        print(stdout[-3000:])
        raise SystemExit(f"build failed ({p.returncode})")
    import duckdb
    con = duckdb.connect(str(Path(env["KOPS_BUILD"]) / "kops.duckdb"), read_only=True)
    run = dict(zip([d[0] for d in con.execute("SELECT * FROM etl.run ORDER BY run_id DESC LIMIT 1").description],
                   con.execute("SELECT * FROM etl.run ORDER BY run_id DESC LIMIT 1").fetchone()))
    con.close()
    return dict(seconds=round(secs, 1), peak_rss_mb=round(rss_mb), run=run, stdout=stdout)


def query(env: dict, sql: str):
    import duckdb
    con = duckdb.connect(str(Path(env["KOPS_BUILD"]) / "kops.duckdb"), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="kops_dw bench")
    ap.add_argument("cmd", choices=["accept", "gen", "run", "dash"])
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--files", type=int, default=5000)
    ap.add_argument("--mails", type=int, default=50000)
    a = ap.parse_args(argv)
    out = a.out.resolve()
    if config.REPO_DIR in out.parents or out == config.REPO_DIR:
        raise SystemExit("--out must be outside the repository (generated data is derived from KLMAS files)")
    out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "gen":
        return gen(out, a.files, a.mails)
    if a.cmd == "accept":
        return accept(out)
    if a.cmd == "dash":
        for line in dash_lines(_env(out)):
            print(line)
        return True
    return benchmark(out)


# ---------------------------------------------------------------- acceptance (HISTORY_SCALE_PLAN §6)
def _mirror(src: Path, dest: Path):
    """Symlink tree of raw-docs (no copy, nothing in raw-docs is touched)."""
    for p in src.rglob("*"):
        rel = p.relative_to(src)
        if p.is_file() and not any(x.startswith(("_", ".")) for x in rel.parts) and p.name != "README.md":
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            (dest / rel).symlink_to(p)


def accept(out: Path) -> bool:
    out = out / "accept"
    shutil.rmtree(out, ignore_errors=True)
    raw, inbox, build = out / "raw", out / "inbox", out / "build"
    _mirror(config.RAW_DOCS_DIR, raw)
    inbox.mkdir(parents=True)
    (build / "cache").mkdir(parents=True)
    for f in config.CACHE_DIR.glob("*.xlsx"):                # .xlsb conversions: no LibreOffice needed
        shutil.copyfile(f, build / "cache" / f.name)
    env = _env(out, raw, Path(f"{config.DW_DIR / 'samples' / 'inbox'}{os.pathsep}{inbox}"))
    results = []

    def check(name, ok, detail):
        results.append((name, bool(ok), detail))
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}", flush=True)

    def test_ok():
        p = subprocess.run([PY, "-m", "kops_dw", "test"], cwd=config.DW_DIR, env=env, capture_output=True, text=True)
        return p.returncode == 0, p.stdout.strip().splitlines()[-1]

    print(f"Acceptance in {out}")
    b1 = run_build(env)
    ok, last = test_ok()
    check("Cold build + 33 checks", ok, f"{b1['seconds']} s, parsed {b1['run']['n_parsed']}, {last}")
    b2 = run_build(env)
    check("H-01/H-02 second build, no change: nothing parsed, < 10 s", b2["run"]["n_parsed"] == 0 and b2["seconds"] < 10,
          f"parsed {b2['run']['n_parsed']}, hashed {b2['run']['n_hashed']}, {b2['seconds']} s")
    src = next(raw.rglob("*BPK 27SS ORDER RECAP.xlsx"))     # an older-dated copy: never the current version
    _copy_variant(src.resolve(), raw / "ORDER" / "250101 DHG) BPK 25SS ORDER RECAP.xlsx", "accept")
    b3 = run_build(env)
    check("H-01 one file added: only that file parsed", b3["run"]["n_parsed"] == 1 and b3["run"]["n_new"] == 1,
          f"new {b3['run']['n_new']}, parsed {b3['run']['n_parsed']}, {b3['seconds']} s")

    (raw / "ORDER" / "250102 MJ) 25SS CHALLENGER ORDER RECAP.xlsx").write_bytes(os.urandom(4096))
    jbee = next(raw.rglob("261019 MJ) 27SS JBEE ORDER RECAP.xlsx")).resolve()
    import openpyxl
    wb = openpyxl.load_workbook(jbee)
    renamed = next(c for row in wb.worksheets[0].iter_rows(min_row=1, max_row=6) for c in row
                   if isinstance(c.value, str) and c.value.strip().upper().startswith("ORDER Q"))
    renamed.value = "ORDER QUANTITY"
    wb.save(raw / "ORDER" / "250103 MJ) 25SS JBEE ORDER RECAP.xlsx")
    b4 = run_build(env)
    q = query(env, "SELECT file_name, reason, message, labels FROM etl.quarantine")
    broken = [r for r in q if r[0].startswith("250102")]
    unknown = [r for r in q if r[0].startswith("250103")]
    check("H-03 broken file: build goes on, file quarantined", broken and broken[0][1] == "PARSE_FAILED"
          and b4["run"]["n_parsed"] == 2, f"{broken[0][1] if broken else 'not quarantined'}; {b4['seconds']} s")
    check("H-04 renamed column -> UNKNOWN_TEMPLATE with labels", unknown and unknown[0][1] == "UNKNOWN_TEMPLATE"
          and "ORDER QUANTITY" in (unknown[0][3] or ""),
          (unknown[0][2][-120:] if unknown else "not quarantined"))
    check("H-03/H-04 quarantine report written", (build / "quarantine.csv").exists(),
          f"{len(q)} row(s) in build/quarantine.csv")

    exp = make_mbox(inbox / "accept_1000.mbox", 1000, seed=11, tag="acc-")
    b5 = run_build(env)
    fid = "(SELECT file_id FROM etl.source_file WHERE file_name = 'accept_1000.mbox')"
    raw_n = query(env, f"SELECT count(*) FROM raw.email WHERE file_id = {fid}")[0][0]
    core_n = query(env, f"SELECT count(*) FROM core.email WHERE msg_key IN (SELECT msg_key FROM raw.email "
                        f"WHERE file_id = {fid})")[0][0]
    filt = query(env, f"SELECT count(*) FROM raw.email_filtered WHERE file_id = {fid}")[0][0]
    check("H-06 mbox 1,000 messages loads < 2 min", b5["seconds"] < 120 and b5["run"]["n_parsed"] == 1,
          f"{b5['seconds']} s (whole build), parse {b5['run']['parse_seconds']} s")
    check("H-06 duplicates merged, automated mail filtered",
          raw_n == exp["business"] + exp["duplicates"] and core_n == exp["business"] and filt == exp["automated"],
          f"raw {raw_n} = {exp['business']} + {exp['duplicates']} dup; core {core_n}; filtered {filt}")

    if make_scanned_pdf(inbox / "scan_ko_vi.pdf"):
        run_build(env)
        pending = query(env, "SELECT count(*) FROM etl.ocr_queue WHERE status = 'PENDING'")[0][0]
        p = subprocess.run([PY, "-m", "kops_dw", "ocr"], cwd=config.DW_DIR, env=env, capture_output=True, text=True)
        b6 = run_build(env)
        rec = query(env, "SELECT sender_email, subject, text_source, body FROM raw.email "
                         "WHERE subject LIKE '[SCAN]%'")
        check("H-08 scanned PDF -> text via OCR (kor+vie+eng)", rec and rec[0][2] == "ocr" and "납기" in rec[0][3]
              and "giao hàng" in rec[0][3], f"queued {pending} file(s); {p.stdout.strip().splitlines()[0]}; "
                                             f"{(rec[0][:2] if rec else 'no record')}")
        p2 = subprocess.run([PY, "-m", "kops_dw", "ocr"], cwd=config.DW_DIR, env=env, capture_output=True, text=True)
        b7 = run_build(env)
        check("H-08 re-run: nothing OCR'd or parsed again", "empty" in p2.stdout and b7["run"]["n_parsed"] == 0
              and b6["run"]["n_parsed"] >= 1, f"{p2.stdout.strip()}; build parsed {b7['run']['n_parsed']}")
    else:
        check("H-08 scanned PDF -> text via OCR", False, "Pillow or a CJK font missing: cannot make the test PDF")
    passed = sum(ok for _, ok, _ in results)
    lines = [f"# Acceptance {dt.datetime.now():%Y-%m-%d %H:%M}", "", "| Check | Result | Detail |", "|---|---|---|"]
    lines += [f"| {n} | {'PASS' if ok else 'FAIL'} | {d.replace('|', '/')} |" for n, ok, d in results]
    (out / "accept.md").write_text("\n".join(lines) + "\n")
    print(f"{passed}/{len(results)} acceptance checks passed -> {out / 'accept.md'}")
    return passed == len(results)


# ---------------------------------------------------------------- benchmark (H-13)
def _sql_timings(env) -> list[tuple[str, float]]:
    """Re-run each SQL model file on a copy of the DB to see which one is slow."""
    import duckdb
    db = Path(env["KOPS_BUILD"]) / "kops.duckdb"
    tmp = db.with_name("sqltiming.duckdb")
    shutil.copyfile(db, tmp)
    con = duckdb.connect(str(tmp))
    for schema in ("mart", "core"):
        for name, kind in con.execute(f"SELECT table_name, table_type FROM information_schema.tables "
                                      f"WHERE table_schema = '{schema}'").fetchall():
            con.execute(f"DROP {'VIEW' if kind == 'VIEW' else 'TABLE'} IF EXISTS {schema}.{name} CASCADE")
    out = []
    for f in sorted((config.DW_DIR / "sql").glob("[1-9]*.sql")):
        t0 = time.time()
        con.execute(f.read_text())
        out.append((f.name, round(time.time() - t0, 2)))
    con.close()
    tmp.unlink()
    return out


def _chrome() -> str | None:
    for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Chromium.app/Contents/MacOS/Chromium"):
        if Path(p).exists():
            return p
    return shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")


def page_load_ms(env: dict, season: str | None = None, port: int = 8799) -> int | None:
    """Open the dashboard through `serve` in headless Chrome; the page writes its time to first render on <body>."""
    chrome = _chrome()
    if not chrome:
        return None
    import re
    import tempfile
    srv = subprocess.Popen([PY, "-m", "kops_dw", "serve", "--port", str(port)], cwd=config.DW_DIR, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.5)
        with tempfile.TemporaryDirectory() as prof:
            url = f"http://127.0.0.1:{port}/" + (f"?season={season}" if season else "")
            p = subprocess.run([chrome, "--headless", "--disable-gpu", f"--user-data-dir={prof}",
                                "--virtual-time-budget=20000", "--dump-dom", url], capture_output=True, text=True, timeout=120)
        m = re.search(r'data-load-ms="(\d+)"', p.stdout)
        return int(m.group(1)) if m else None
    finally:
        srv.terminate()
        srv.wait()


def dash_lines(env: dict) -> list[str]:
    """Render the per-season dashboard and report file sizes and page load time (H-11)."""
    import json
    build = Path(env["KOPS_BUILD"])
    t0 = time.time()
    p = subprocess.run([PY, "-m", "kops_dw", "dashboard"], cwd=config.DW_DIR, env=env, capture_output=True, text=True)
    secs = round(time.time() - t0, 1)
    if p.returncode != 0:
        return [f"- Dashboard: LỖI {p.stderr.strip().splitlines()[-1][:200]}"]
    idx = json.loads((build / "data" / "index.json").read_text())
    sizes = {k: v / 1e6 for k, v in idx["sizes"].items()}
    seasons = {k: v for k, v in sizes.items() if k != "_common"}
    big = max(seasons.items(), key=lambda x: x[1]) if seasons else ("-", 0)
    ms = page_load_ms(env, idx["default"])
    ms_big = page_load_ms(env, big[0]) if big[0] != idx["default"] else ms
    return [f"- Dashboard theo mùa (H-11): render {secs} s; {len(seasons)} mùa, file mùa lớn nhất {big[0]} {big[1]:.1f} MB, "
            f"tổng các mùa {sum(seasons.values()):.1f} MB, _common {sizes.get('_common', 0):.1f} MB; mở trang (mùa "
            f"{idx['default']}) {ms if ms is not None else 'n/a'} ms, mùa {big[0]} {ms_big if ms_big is not None else 'n/a'} ms"]


def benchmark(out: Path) -> bool:
    if not (out / "raw").exists():
        gen(out)
    build = out / "build"
    shutil.rmtree(build, ignore_errors=True)
    (build / "cache").mkdir(parents=True)
    env = _env(out)
    n_raw = sum(1 for p in (out / "raw").rglob("*") if p.is_file())
    raw_gb = sum(p.stat().st_size for p in (out / "raw").rglob("*") if p.is_file()) / 1e9
    inbox_gb = sum(p.stat().st_size for p in (out / "inbox").rglob("*") if p.is_file()) / 1e9
    print(f"Benchmark on {n_raw} files ({raw_gb:.1f} GB) + inbox ({inbox_gb:.2f} GB); workers {config.WORKERS}")
    rows = []
    b1 = run_build(env)
    rows.append(("1. Lần đầu (cold)", b1))
    print(f"  cold: {b1['seconds']} s", flush=True)
    b2 = run_build(env)
    rows.append(("2. Lần sau, không đổi", b2))
    srcs = _sources(config.RAW_DOCS_DIR)[:10]
    from .util import sha256
    for i, src in enumerate(srcs):
        real = config.CACHE_DIR / f"{sha256(src)}.xlsx" if src.suffix.lower() == ".xlsb" else src
        _copy_variant(real, out / "raw" / "NEW" / f"{i:02d}" / (Path(re_season(src.name, "25FW")).stem + ".xlsx"),
                      f"new{i}")
    make_mbox(out / "inbox" / "new_100.mbox", 100, seed=99, tag="new-")
    b3 = run_build(env)
    rows.append(("3. Thêm 10 file + 100 thư", b3))
    dash = dash_lines(env)
    sql = _sql_timings(env)
    stats = query(env, """SELECT parser, count(*), round(sum(parse_seconds), 1), round(max(parse_seconds), 2)
                          FROM etl.source_file WHERE parse_key IS NOT NULL GROUP BY 1 ORDER BY 3 DESC""")
    counts = query(env, """SELECT (SELECT count(*) FROM etl.source_file), (SELECT count(*) FROM raw.email),
                                  (SELECT count(*) FROM core.email), (SELECT count(*) FROM raw.email_filtered),
                                  (SELECT count(*) FROM raw.order_recap_color) + (SELECT count(*) FROM raw.order_line_ext)
                                  + (SELECT count(*) FROM raw.shipment_cell), (SELECT count(*) FROM etl.quarantine)""")[0]
    db_mb = (build / "kops.duckdb").stat().st_size / 1e6
    lake_mb = sum(f.stat().st_size for f in (build / "lake").rglob("*.parquet")) / 1e6
    n_parquet = sum(1 for _ in (build / "lake").rglob("*.parquet"))
    lines = [f"# Benchmark H-13 — {dt.datetime.now():%Y-%m-%d %H:%M}", "",
             f"Dữ liệu giả lập (nhân bản file thật, không commit): {n_raw} file Excel/khác ({raw_gb:.1f} GB), "
             f"{counts[1] - 0} thư trong raw.email; máy: {os.cpu_count()} CPU, KOPS_WORKERS={config.WORKERS}.", "",
             "| Lượt build | Thời gian | Parse | Nạp lake | SQL | File parse | RAM tiến trình build | RAM lớn nhất (cả worker) |",
             "|---|---|---|---|---|---|---|---|"]
    for name, b in rows:
        r = b["run"]
        lines.append(f"| {name} | {b['seconds']} s | {r['parse_seconds']} s | {r['load_seconds']} s | "
                     f"{r['sql_seconds']} s | {r['n_parsed']} | {r['peak_rss_mb']:.0f} MB | {b['peak_rss_mb']} MB |")
    lines += ["", f"- Lake Parquet: **{lake_mb:.0f} MB** ({n_parquet} file) = {lake_mb / 1e3 / max(raw_gb + inbox_gb, 1e-9):.1%} "
              f"dung lượng nguồn; DuckDB: {db_mb:.0f} MB.",
              f"- Dòng: {counts[0]} file nguồn, {counts[1]} thư raw / {counts[2]} thư sau gộp trùng / {counts[3]} thư bị lọc, "
              f"{counts[4]} dòng đơn hàng + ô xuất hàng; {counts[5]} file cách ly.", *dash, "",
              "| Parser | File | Tổng giây parse (CPU, cộng mọi worker) | File chậm nhất |", "|---|---|---|---|"]
    lines += [f"| {a} | {b} | {c} | {d} s |" for a, b, c, d in stats]
    lines += ["", "| File SQL | Giây |", "|---|---|"] + [f"| {a} | {b} |" for a, b in sql]
    (out / "bench.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return True
