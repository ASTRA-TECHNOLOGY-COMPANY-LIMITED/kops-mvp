"""Synthetic ('giả định') data for the manager dashboard demo (D-04). Never real, never in core / fact / golden checks.

Written to schema `sim` with is_synthetic = true and an assumption_id (dw/docs/assumptions.md). Reproducible: fixed
seed, inputs read in a fixed order. Distributions come from the complete real cycle (CHALLENGER 26FW): first-lot delay
against ETD, shipped / ordered ratio, daily output per factory, KLMAS defect rate per factory, third-party defect-code
mix and reject share - no round invented numbers. KOPS_SIM=0 turns it off.

  ASM-SIM-01  two earlier seasons 25SS / 25FW of CHALLENGER (orders, shipments, inspections) for trends
  ASM-SIM-02  daily output for running styles whose factory sends no daily report (TIEN THANH, FG VINA, DHG ...)
  ASM-SIM-03  inspection results + defects for styles without KLMAS inspection data whose ETD has passed
  ASM-SIM-04  shipments for customers without Shipment Status (DHG, JBEE, KOFA) for styles whose ETD has passed
  ASM-SIM-05  defect codes of synthetic inspections drawn from the third-party Pareto (INPUT DATA)
"""
from __future__ import annotations

import bisect
import datetime as dt
import math
import random
import statistics

from . import config

SEED = 20261023
SIM_SEASONS = {"25SS": (2025, "SS", dt.date(2025, 2, 1), dt.date(2025, 7, 31)),
               "25FW": (2025, "FW", dt.date(2025, 8, 1), dt.date(2026, 1, 31))}

DDL = """
CREATE SCHEMA IF NOT EXISTS sim;
CREATE TABLE sim.season (season VARCHAR, year INTEGER, half VARCHAR, start_date DATE, end_date DATE, assumption_id VARCHAR);
CREATE TABLE sim.style (style_nk VARCHAR, customer VARCHAR, brand VARCHAR, season VARCHAR, style_code VARCHAR,
  factory_code VARCHAR, order_qty INTEGER, etd DATE, rdd DATE, is_active BOOLEAN, assumption_id VARCHAR);
CREATE TABLE sim.shipment_lot (customer VARCHAR, season VARCHAR, style_code VARCHAR, style_key BIGINT, factory_code VARCHAR,
  lot_label VARCHAR, lot_etd DATE, qty INTEGER, ship_mode VARCHAR, assumption_id VARCHAR);
CREATE TABLE sim.daily_output (customer VARCHAR, season VARCHAR, style_code VARCHAR, style_key BIGINT, factory_code VARCHAR,
  fact_date DATE, output_day INTEGER, output_ttl INTEGER, assumption_id VARCHAR);
CREATE TABLE sim.inspection (inspection_id VARCHAR, customer VARCHAR, season VARCHAR, style_code VARCHAR, style_key BIGINT,
  factory_code VARCHAR, fact_date DATE, inspected_qty INTEGER, passed_qty INTEGER, defect_qty INTEGER, result VARCHAR,
  assumption_id VARCHAR);
CREATE TABLE sim.defect (inspection_id VARCHAR, code VARCHAR, code_group VARCHAR, points INTEGER, assumption_id VARCHAR);
"""


def _workdays_after(d: dt.date, n: int) -> dt.date:
    while n > 0:
        d += dt.timedelta(days=1)
        if d.isoweekday() != 7:
            n -= 1
    return d


class _Pick:
    """Empirical distribution: draw a real observed value (bootstrap)."""

    def __init__(self, values, default):
        self.values = sorted(v for v in values if v is not None) or [default]

    def __call__(self, rng):
        return self.values[rng.randrange(len(self.values))]


def _params(con):
    q = lambda sql: con.execute(sql).fetchall()      # noqa: E731
    delay = [r[0] for r in q("""
        SELECT date_diff('day', s.etd, min(l.lot_etd)) FROM fact.shipment_lot l JOIN dim.style s USING (style_key)
        WHERE s.customer = 'CHALLENGER' AND s.season = '26FW' AND s.etd IS NOT NULL GROUP BY s.style_key, s.etd ORDER BY 1""")]
    ratio = [r[0] for r in q("""
        SELECT sum(l.qty) / any_value(s.order_qty) FROM fact.shipment_lot l JOIN dim.style s USING (style_key)
        WHERE s.customer = 'CHALLENGER' AND s.season = '26FW' AND s.order_qty > 0 GROUP BY s.style_key ORDER BY 1""")]
    rate = {}
    for fac, v in q("""SELECT factory_code, output_day FROM fact.daily_output WHERE output_day > 0 AND customer = 'CHALLENGER'
                       ORDER BY factory_code, fact_date, style_code"""):
        rate.setdefault(fac, []).append(v)
    all_rates = [v for vs in rate.values() for v in vs]
    defect = {fac: r for fac, r in q("""SELECT factory_code, sum(defect_qty) / nullif(sum(inspected_qty), 0) FROM fact.inspection_day
                                        GROUP BY 1 HAVING sum(inspected_qty) > 0 ORDER BY 1""")}
    overall = q("SELECT sum(defect_qty) / nullif(sum(inspected_qty), 0) FROM fact.inspection_day")[0][0] or 0.2
    codes = q("""SELECT code, any_value(code_group), sum(points) FROM fact.defect GROUP BY code ORDER BY 3 DESC, 1""")
    reject = q("SELECT avg(CASE WHEN result = 'REJECT' THEN 1.0 ELSE 0 END) FROM fact.inspection WHERE source = 'THIRD_PARTY'")[0][0]
    modes = [r[0] for r in q("""SELECT ship_mode FROM fact.shipment_lot l JOIN dim.style s USING (style_key)
                                WHERE s.customer = 'CHALLENGER' AND s.season = '26FW' ORDER BY 1""")]
    return dict(delay=_Pick(delay, 0), ratio=_Pick([min(r, 1.1) for r in ratio], 1.0), rate=rate,
                all_rate=_Pick(all_rates, config.RULES["default_daily_output"]), defect=defect, defect_all=overall,
                codes=codes, reject=reject or 0.08, modes=_Pick(modes, "SEA"))


def _defects(rng, p, iid, points, out):
    """Split defect points over codes drawn from the third-party mix (ASM-SIM-05)."""
    if not p["codes"] or points <= 0:
        return
    weights, cum = [c[2] for c in p["codes"]], []
    total = 0
    for w in weights:
        total += w
        cum.append(total)
    for _ in range(points):
        i = bisect.bisect_left(cum, rng.random() * total)
        code, group, _ = p["codes"][min(i, len(cum) - 1)]
        out.setdefault((iid, code, group), 0)
        out[(iid, code, group)] += 1


def _inspect(rng, p, fac, order_qty):
    inspected = max(1, int(order_qty * rng.uniform(0.9, 1.0)))
    rate = p["defect"].get(fac, p["defect_all"]) * rng.uniform(0.7, 1.3)
    defects = int(round(inspected * rate))
    result = "REJECT" if rng.random() < p["reject"] else "PASS"
    return inspected, inspected if result == "PASS" else int(inspected * rng.uniform(0.6, 0.95)), defects, result


def generate(con) -> dict:
    con.execute(DDL)
    if not config.SIM:
        return {}
    rng, p = random.Random(SEED), _params(con)
    today = dt.date.fromisoformat(config.TODAY)
    styles, lots, daily, insp, defects = [], [], [], [], {}

    # ASM-SIM-01: earlier seasons from the real 26FW (FW) / 27SS (SS) style mix of CHALLENGER
    base = {s: con.execute(f"""SELECT style_no, factory_code, order_qty, etd FROM dim.style WHERE customer = 'CHALLENGER'
                               AND season = '{s}' AND is_active AND order_qty > 0 AND etd IS NOT NULL ORDER BY style_no""").fetchall()
            for s in ("26FW", "27SS")}
    for season, src, years in (("25FW", "26FW", 1), ("25SS", "27SS", 2)):
        rows = base[src]
        n = int(round(len(rows) * rng.uniform(0.85, 1.05)))
        for i in range(n):
            _, fac, qty, etd = rows[rng.randrange(len(rows))]
            qty = int(round(qty * rng.uniform(0.9, 1.1) / 10) * 10) or 10
            etd = etd.replace(year=etd.year - years) if not (etd.month == 2 and etd.day == 29) else etd - dt.timedelta(days=365 * years)
            code = f"SIM{season}-{i + 1:03d}"
            styles.append((f"SIM|CHALLENGER|{season}|{code}", "CHALLENGER", "CHALLENGER", season, code, fac, qty, etd,
                           etd + dt.timedelta(days=config.RULES["rdd_offset_days"]), True, "ASM-SIM-01"))
            shipped = int(qty * p["ratio"](rng))
            first = etd + dt.timedelta(days=p["delay"](rng))
            parts = [shipped] if rng.random() < 0.7 else [int(shipped * 0.8), shipped - int(shipped * 0.8)]
            for k, q in enumerate(parts):
                lots.append(("CHALLENGER", season, code, None, fac, f"SIM LOT {k + 1}", first + dt.timedelta(days=14 * k), q,
                             p["modes"](rng), "ASM-SIM-01"))
            ins, passed, dq, res = _inspect(rng, p, fac, qty)
            iid = f"S01-{season}-{i + 1:03d}"
            insp.append((iid, "CHALLENGER", season, code, None, fac, first - dt.timedelta(days=rng.randint(1, 4)), ins, passed,
                         dq, res, "ASM-SIM-01"))
            _defects(rng, p, iid, dq, defects)

    # ETD far before the season (typed year, e.g. KOFA 27SS ETD 02/2026) -> no synthetic data for that style
    real = con.execute("""SELECT s.style_key, s.customer, s.season, s.style_no, s.factory_code, s.order_qty, s.etd
                          FROM dim.style s JOIN dim.season n USING (season)
                          WHERE s.is_active AND s.order_qty > 0 AND s.etd IS NOT NULL AND s.etd >= n.start_date - 120
                          ORDER BY s.customer, s.season, s.style_no""").fetchall()
    has_daily = {k for (k,) in con.execute("SELECT DISTINCT style_key FROM fact.daily_output WHERE style_key IS NOT NULL").fetchall()}
    has_insp = {k for (k,) in con.execute("""SELECT DISTINCT style_key FROM fact.inspection WHERE style_key IS NOT NULL
                                             UNION SELECT style_key FROM fact.production_status WHERE inspected_qty > 0""").fetchall()}
    has_ship = {k for (k,) in con.execute("SELECT DISTINCT style_key FROM fact.shipment_lot WHERE style_key IS NOT NULL").fetchall()}
    status_cust = {c for (c,) in con.execute("SELECT DISTINCT customer FROM fact.shipment_lot").fetchall()}
    for key, cust, season, code, fac, qty, etd in real:
        # ASM-SIM-02: daily output where the factory sends no report, styles with ETD from 60 days ago to 75 days ahead
        if key not in has_daily and -60 <= (etd - today).days <= 75:
            rates = p["rate"].get(fac)
            rate = statistics.median(rates) if rates else p["all_rate"](rng)
            days = max(3, math.ceil(qty / max(rate, 1)))
            start = etd - dt.timedelta(days=int(days * 7 / 6) + config.RULES["ready_buffer_days"])
            d, ttl = start, 0
            while ttl < qty and d <= today:
                if d.isoweekday() != 7:
                    out = min(qty - ttl, max(0, int(round(rate * rng.uniform(0.6, 1.3)))))
                    ttl += out
                    daily.append((cust, season, code, key, fac, d, out, ttl, "ASM-SIM-02"))
                d += dt.timedelta(days=1)
        # ASM-SIM-04: shipments for customers that send no Shipment Status, ETD passed
        if key not in has_ship and cust not in status_cust and etd + dt.timedelta(days=7) <= today:
            first = etd + dt.timedelta(days=p["delay"](rng))
            if first <= today:
                lots.append((cust, season, code, key, fac, "SIM LOT 1", first, int(qty * p["ratio"](rng)), p["modes"](rng),
                             "ASM-SIM-04"))
        # ASM-SIM-03: inspection for styles without KLMAS inspection data, ETD passed
        if key not in has_insp and etd <= today:
            ins, passed, dq, res = _inspect(rng, p, fac, qty)
            iid = f"S03-{key}"
            insp.append((iid, cust, season, code, key, fac, etd - dt.timedelta(days=rng.randint(1, 4)), ins, passed, dq, res,
                         "ASM-SIM-03"))
            _defects(rng, p, iid, dq, defects)

    con.executemany("INSERT INTO sim.season VALUES (?, ?, ?, ?, ?, 'ASM-SIM-01')",
                    [(s, *v) for s, v in SIM_SEASONS.items()])
    for table, rows in (("sim.style", styles), ("sim.shipment_lot", lots), ("sim.daily_output", daily),
                        ("sim.inspection", insp)):
        if rows:
            con.executemany(f"INSERT INTO {table} VALUES ({', '.join('?' * len(rows[0]))})", rows)
    if defects:
        con.executemany("INSERT INTO sim.defect VALUES (?, ?, ?, ?, 'ASM-SIM-05')",
                        [(i, c, g, n) for (i, c, g), n in sorted(defects.items())])
    return dict(style=len(styles), shipment_lot=len(lots), daily_output=len(daily), inspection=len(insp),
                defect=len(defects))
