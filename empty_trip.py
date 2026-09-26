"""
empty_trip.py
-------------
แดชบอร์ด "เที่ยวเปล่า & รถว่างไปสาขา" — มุมมองเส้นทาง

แหล่งข้อมูล
- อ่านเฉพาะไฟล์ในโฟลเดอร์ data ที่ชื่อมีคำว่า "เที่ยวเปล่า" เช่น "Dashboard เที่ยวเปล่า.xlsx"
  (ถ้ามีหลายไฟล์ ใช้ไฟล์ที่แก้ไขล่าสุดไฟล์เดียว)
- ราคาต่อเส้นทาง / ต้นทุนเฉลี่ย / ค่าเฉลี่ยหลังตัด outlier อ่านจากคอลัมน์ในไฟล์ตรง ๆ
  (เป็นค่าระดับเส้นทาง ไม่เปลี่ยนตามตัวกรอง)

ตรรกะเดิม
- เที่ยวเปล่า   = Manifest Type มีคำว่า "ของเหมาตีเปล่า" หรือ "เที่ยวเปล่า"
- รถว่างไปสาขา = Manifest Type มีคำว่า "รถว่างไปสาขา"
- จำนวนเที่ยว  = นับ Travel Req. No. ไม่ซ้ำ
- ต้นทุน       = คอลัมน์ Total Cost

มุมมองเส้นทาง
- เส้นทางจาก Loading ↔ Unloading (วิ่งสลับทิศนับเป็นเส้นทางเดียวกัน) แบบเดียวกับหน้า Transportation Cost
- ทุกการ์ด กราฟ และตาราง สรุปเป็นระดับเส้นทาง
"""

from html import escape as esc
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from transport_cost_route import (
    GRAY,
    KNOWN_COST_COLUMNS,
    PAGE_CSS,
    PALETTE,
    THAI_MONTHS,
    _card,
    _chart_layout,
    _id_text,
    _key,
    _km,
    _money,
    _money_full,
    _num,
    _style,
    _table_html,
    _tint,
    _wkey,
    build_route_colors,
    build_routes,
    find_manifest_col,
)

DATA_FOLDER = Path("data")
SOURCE_KEYWORD = "เที่ยวเปล่า"

EMPTY = "เที่ยวเปล่า"
BRANCH = "รถว่างไปสาขา"
TYPES = [EMPTY, BRANCH]
TRIP_COLORS = {EMPTY: "#F07C8C", BRANCH: "#F6AE6B"}
PRICE_COLOR = "#7CC4D6"
PLOT_CONFIG = {"displayModeBar": False}

PIE_EXCLUDE = {"Total Cost", "Total Cash"}
PIE_DEFAULT = ["รวมต้นทุนค่าเดินทาง", "รวมต้นทุนค่าซ่อม", "รวมค่าเสื่อม"]
DISTANCE_CANDIDATES = ["ระยะทาง", "Distance", "Total Distance", "Distance (km)", "KM"]

# คอลัมน์ระดับเส้นทางในไฟล์ Dashboard เที่ยวเปล่า
PRICE_NAMES = ["ราคาต่อเส้นทาง"]
AVG_NAMES = ["ต้นทุนเฉลี่ย"]
AVG_KEPT_NAMES = ["ค่าเฉลี่ยหลังตัด outlier"]
OUTLIER_FLAG_NAMES = ["ตัด outlier"]

EXTRA_CSS = """
<style>
.et-dirs-cell { white-space: normal !important; min-width: 250px; }
.et-dirs { display: flex; flex-direction: column; gap: 3px; }
.et-split { display: flex; height: 5px; border-radius: 99px; overflow: hidden; background: #FBEBEE; margin-bottom: 3px; }
.et-split > span { display: block; height: 100%; }
.et-dir { display: grid; grid-template-columns: 9px minmax(0, 1fr) auto 36px; gap: 8px; align-items: center;
          font-size: 12.5px; color: #475569; line-height: 1.45; }
.et-dir-sw { width: 9px; height: 9px; border-radius: 3px; }
.et-dir-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.et-dir b { color: #1E293B; font-weight: 700; font-variant-numeric: tabular-nums; text-align: right; }
.et-dir small { color: #94A3B8; font-size: 11.5px; text-align: right; font-variant-numeric: tabular-nums; }
.et-badge { display: inline-block; font-size: 12px; font-weight: 600; padding: 2px 10px; border-radius: 99px; color: #3F2A2E; }
.et-over { color: #C23B53 !important; font-weight: 700; }
.et-under { color: #3E9E6A !important; }
.et-price { color: #2F7F95 !important; font-weight: 700; }
.et-route-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; margin: 8px 0 12px; }
.et-route-box { background: #FFF8F9; border: 1px solid #F6DDE2; border-radius: 14px; padding: 10px 14px; }
.et-route-box .k { font-size: 12px; color: #64748B; font-weight: 600; }
.et-route-box .v { font-size: 20px; font-weight: 800; color: #0F172A; line-height: 1.25; white-space: nowrap; }
.et-route-box .s { font-size: 11.5px; color: #94A3B8; }
</style>
"""
ARROW = ' <span class="tc-arrow">→</span> '


# =========================================================
# HELPERS
# =========================================================

def _norm(c) -> str:
    return "".join(str(c).split()).casefold()


def _find_col(df, names):
    lookup = {_norm(c): c for c in df.columns}
    for n in names:
        if _norm(n) in lookup:
            return lookup[_norm(n)]
    return None


def find_source_file():
    """ไฟล์ในโฟลเดอร์ data ที่ชื่อมีคำว่า เที่ยวเปล่า (หลายไฟล์ = ใช้ไฟล์ล่าสุด)"""
    if not DATA_FOLDER.exists():
        return None
    files = [
        f for f in DATA_FOLDER.iterdir()
        if f.is_file() and f.suffix.lower() in {".xlsx", ".xlsm", ".xls"}
        and not f.name.startswith("~$")
        and _norm(_key(SOURCE_KEYWORD)) in _norm(_key(f.stem))
    ]
    return max(files, key=lambda f: f.stat().st_mtime_ns).name if files else None


def _first_number(s):
    v = _num(s).dropna()
    return float(v.iloc[0]) if not v.empty else float("nan")


def _parse_date(series: pd.Series) -> pd.Series:
    """แปลงวันที่ให้ครอบคลุม: รูปแบบ ISO (yyyy-mm-dd) / ข้อความ dd/mm/yyyy / เลข serial ของ Excel / ปี พ.ศ."""
    if pd.api.types.is_datetime64_any_dtype(series):
        dt = pd.to_datetime(series, errors="coerce")
    else:
        text = series.astype("string").str.strip()
        dt = pd.to_datetime(text, format="%Y-%m-%d %H:%M:%S", errors="coerce")
        dt = dt.fillna(pd.to_datetime(text, format="%Y-%m-%d", errors="coerce"))
        rest = dt.isna() & text.notna() & text.ne("")
        if rest.any():
            try:
                other = pd.to_datetime(text.where(rest), dayfirst=True, errors="coerce", format="mixed")
            except (TypeError, ValueError):
                other = pd.to_datetime(text.where(rest), dayfirst=True, errors="coerce")
            dt = dt.fillna(other)
        num = pd.to_numeric(text, errors="coerce")
        serial = num.where(num.between(20000, 80000))
        if serial.notna().any():
            dt = dt.where(serial.isna(), pd.to_datetime(serial, unit="D", origin="1899-12-30", errors="coerce"))
    be = dt.dt.year > 2400  # ปี พ.ศ. → ค.ศ.
    if be.any():
        dt = dt.where(~be, dt - pd.DateOffset(years=543))
    return dt


def _badge(text, color):
    return f'<span class="et-badge" style="background:{_tint(color, 0.72)}">{esc(text)}</span>'


def _dirs_block(g, route_color):
    """ทิศทางการวิ่ง: แถบสัดส่วน + บรรทัดละทิศทาง (g มีคอลัมน์ _Direction, n)"""
    total_n = float(g["n"].sum()) or 1.0
    colors = [route_color if k == 0 else _tint(route_color, 0.55) for k in range(len(g))]
    bar = "".join(
        f'<span style="width:{n / total_n * 100:.1f}%;background:{c}"></span>'
        for n, c in zip(g["n"], colors)
    )
    lines = "".join(
        f'<div class="et-dir"><span class="et-dir-sw" style="background:{c}"></span>'
        f'<span class="et-dir-name">{esc(str(d)).replace(" → ", ARROW)}</span>'
        f'<b>{int(n):,}</b><small>{n / total_n * 100:.0f}%</small></div>'
        for d, n, c in zip(g["_Direction"], g["n"], colors)
    )
    return f'<div class="et-dirs"><div class="et-split">{bar}</div>{lines}</div>'


def _diff_cell(actual, price):
    """ส่วนต่าง = ต้นทุนเฉลี่ยจริง − ราคาต่อเส้นทาง (แดง = เกินราคา)"""
    if pd.isna(actual) or pd.isna(price) or not price:
        return '<td class="tc-num tc-muted">—</td>'
    diff = actual - price
    cls = "et-over" if diff > 0 else "et-under"
    sign = "+" if diff > 0 else "−"
    return f'<td class="tc-num {cls}">{sign}฿{abs(diff):,.0f}<br><small>{diff / price * 100:+.0f}%</small></td>'


# =========================================================
# DASHBOARD
# =========================================================

def render_empty_trip_dashboard(raw_df: pd.DataFrame):
    source_file = find_source_file()
    if source_file is None:
        st.error(
            f"ไม่พบไฟล์ที่ชื่อมีคำว่า “{SOURCE_KEYWORD}” ในโฟลเดอร์ data "
            "— อัปโหลดไฟล์ เช่น “Dashboard เที่ยวเปล่า.xlsx” ในหน้า Data Management ก่อน"
        )
        return
    if raw_df is None or raw_df.empty or "_source_file" not in raw_df.columns:
        st.error("ยังไม่มีข้อมูลในฐานข้อมูล — กด “🔄 โหลดข้อมูลจาก Excel ใหม่” ที่แถบด้านซ้าย")
        return

    src = raw_df[raw_df["_source_file"].map(_key) == _key(source_file)].copy()
    if src.empty:
        st.error(f"ไฟล์ {source_file} ยังไม่ถูกนำเข้าฐานข้อมูล — กด “🔄 โหลดข้อมูลจาก Excel ใหม่” ที่แถบด้านซ้าย")
        return
    missing = [c for c in ["Manifest Type", "Total Cost", "Loading", "Unloading"] if c not in src.columns]
    if missing:
        st.error(f"ไฟล์ {source_file} ขาดคอลัมน์: " + ", ".join(missing))
        return

    price_col = _find_col(src, PRICE_NAMES)
    avg_col = _find_col(src, AVG_NAMES)
    kept_col = _find_col(src, AVG_KEPT_NAMES)
    flag_col = _find_col(src, OUTLIER_FLAG_NAMES)

    # ---------------- ราคาระดับเส้นทางจากไฟล์ ----------------
    _r, _d, _m, src_load, src_unload = build_routes(src)
    src["_PairKey"] = ["|".join(sorted(p)) for p in zip(src_load, src_unload)]
    price_parts = {}
    for name, col in (("Price", price_col), ("AvgFile", avg_col), ("AvgKept", kept_col)):
        price_parts[name] = (src.groupby("_PairKey")[col].agg(_first_number) if col
                             else pd.Series(dtype="float64"))
    price_tbl = pd.DataFrame(price_parts)

    # ---------------- แยกประเภทเที่ยว (ตรรกะเดิม) ----------------
    manifest = src["Manifest Type"].astype("string").fillna("").str.strip()
    is_empty = manifest.str.contains(r"ของเหมาตีเปล่า|เที่ยวเปล่า", regex=True, na=False)
    is_branch = manifest.str.contains("รถว่างไปสาขา", regex=False, na=False)
    work = src[is_empty | is_branch].copy()
    if work.empty:
        st.info("ยังไม่พบ Manifest Type ที่เป็น 'เที่ยวเปล่า' หรือ 'รถว่างไปสาขา'")
        return
    work["_Type"] = EMPTY
    work.loc[is_branch.loc[work.index], "_Type"] = BRANCH
    work["_Cost"] = _num(work["Total Cost"]).fillna(0)

    route, direction, _main, load, unload = build_routes(work)
    work["_Route"], work["_Direction"], work["_Load"], work["_Unload"] = route, direction, load, unload
    work["_PairKey"] = ["|".join(sorted(p)) for p in zip(load, unload)]

    # วันที่: ใช้ Disbursement Date เป็นหลัก (ถ้าไม่มีค่อยใช้ Travel Req. Date)
    date_col = _find_col(work, ["Disbursement Date"]) or _find_col(work, ["Travel Req. Date"])
    work["_Date"] = _parse_date(work[date_col]) if date_col else pd.NaT
    years = work["_Date"].dt.year
    work["_Year"] = years.map(lambda y: "" if pd.isna(y) else str(int(y + 543 if y < 2400 else y)))
    work["_MonthNum"] = work["_Date"].dt.month
    dist_col = next((c for c in DISTANCE_CANDIDATES if c in work.columns), None)
    work["_Distance"] = _num(work[dist_col]).fillna(0) if dist_col else 0.0
    work["_Flag"] = work[flag_col].astype("string").fillna("").str.strip() if flag_col else ""

    if "Travel Req. No." in work.columns:
        tid = work["Travel Req. No."].astype("string").fillna("").str.strip()
        work["_TripId"] = tid.mask(tid.eq(""))
    else:
        work["_TripId"] = work.index.astype(str)

    def trip_count(part):
        return int(part["_TripId"].nunique())

    vehicle_col = next((c for c in ["Vehicle Model", "ประเภทรถ"] if c in work.columns), None)
    route_colors = build_route_colors(
        work.groupby("_Route")["_Cost"].sum().sort_values(ascending=False).index
    )

    st.markdown(PAGE_CSS + EXTRA_CSS, unsafe_allow_html=True)

    # ---------------- ตัวกรอง ----------------
    fcard = _card("et_filters")
    fcard.markdown('<div class="tc-filter-title">🔎 ตัวกรองข้อมูล</div>', unsafe_allow_html=True)
    f1, f2, f3, f4, f5 = fcard.columns([0.8, 1.1, 1.1, 1.9, 1.2])
    filtered = work
    with f1:
        year_opts = sorted(y for y in work["_Year"].unique() if y)
        year = st.selectbox("ปี", ["ทั้งหมด"] + year_opts, key="et_year")
    if year != "ทั้งหมด":
        filtered = filtered[filtered["_Year"] == year]
    with f2:
        months = sorted(int(m) for m in filtered["_MonthNum"].dropna().unique())
        chosen_months = st.multiselect("เดือน", [THAI_MONTHS[m] for m in months],
                                       placeholder="ทั้งหมด", key="et_month")
    if chosen_months:
        nums = [n for n, label in THAI_MONTHS.items() if label in chosen_months]
        filtered = filtered[filtered["_MonthNum"].isin(nums)]
    with f3:
        chosen_types = st.multiselect("ประเภทเที่ยว", TYPES, placeholder="ทั้งหมด", key="et_type")
    if chosen_types:
        filtered = filtered[filtered["_Type"].isin(chosen_types)]
    with f4:
        route_opts = sorted(r for r in filtered["_Route"].unique() if r)
        chosen_routes = st.multiselect("เส้นทาง", route_opts, placeholder="ทั้งหมด",
                                       key=_wkey("et_route", route_opts))
    if chosen_routes:
        filtered = filtered[filtered["_Route"].isin(chosen_routes)]
    with f5:
        if vehicle_col:
            veh = filtered[vehicle_col].astype("string").fillna("").str.strip()
            veh_opts = sorted(v for v in veh.unique() if v)
            chosen_veh = st.multiselect("ประเภทรถ", veh_opts, placeholder="ทั้งหมด",
                                        key=_wkey("et_vehicle", veh_opts))
            if chosen_veh:
                filtered = filtered[veh.isin(chosen_veh)]
        else:
            st.caption("ไม่มีข้อมูลประเภทรถ")

    if filtered.empty:
        st.info("ไม่มีข้อมูลตามตัวกรองที่เลือก")
        return

    # ---------------- สรุประดับเส้นทาง ----------------
    rs = (
        filtered.groupby(["_Route", "_Type"])
        .agg(Trips=("_TripId", "nunique"), Cost=("_Cost", "sum"))
        .unstack("_Type", fill_value=0)
    )
    rs.columns = [f"{m}_{t}" for m, t in rs.columns]
    for t in TYPES:
        for m in ("Trips", "Cost"):
            if f"{m}_{t}" not in rs.columns:
                rs[f"{m}_{t}"] = 0
    rs["TripsAll"] = filtered.groupby("_Route")["_TripId"].nunique()
    rs["CostAll"] = rs[f"Cost_{EMPTY}"] + rs[f"Cost_{BRANCH}"]
    rs["PairKey"] = filtered.groupby("_Route")["_PairKey"].first()
    rs = rs.reset_index()
    rs["AvgActual"] = rs["CostAll"] / rs["TripsAll"].replace(0, float("nan"))
    rs = rs.merge(price_tbl, left_on="PairKey", right_index=True, how="left")
    for c in ("Price", "AvgFile", "AvgKept"):
        if c not in rs.columns:
            rs[c] = float("nan")
    rs["Diff"] = rs["AvgActual"] - rs["Price"]
    valid = rs[rs["_Route"] != "ไม่ระบุเส้นทาง"].copy()
    has_price = bool(valid["Price"].notna().any())

    dir_counts = (
        filtered.groupby(["_Route", "_Direction"])["_TripId"].nunique()
        .reset_index(name="n").sort_values("n", ascending=False)
    )
    dir_html = {r: _dirs_block(g, route_colors.get(r, GRAY)) for r, g in dir_counts.groupby("_Route")}

    # ---------------- การ์ดตัวเลข (ระดับเส้นทาง) ----------------
    n_routes = int(valid["_Route"].nunique())
    n_empty_routes = int((valid[f"Trips_{EMPTY}"] > 0).sum())
    n_branch_routes = int((valid[f"Trips_{BRANCH}"] > 0).sum())
    total_loss = float(valid["CostAll"].sum())
    total_trips = trip_count(filtered)
    over = valid[valid["Diff"] > 0]

    def kpi(icon, bg, label, value, sub_html, value_color="#0F172A"):
        return (
            f'<div class="tc-kpi"><div class="tc-kpi-icon" style="background:{bg}">{icon}</div>'
            f'<div><div class="tc-kpi-label">{esc(label)}</div>'
            f'<div class="tc-kpi-value" style="color:{value_color}">{esc(value)}</div>'
            f'<div class="tc-kpi-sub">{sub_html}</div></div></div>'
        )

    cards = [
        kpi("🛣️", "#FFE8EC", "จำนวนเส้นทาง", f"{n_routes:,} เส้นทาง",
            f"มี{EMPTY} {n_empty_routes:,} · {BRANCH} {n_branch_routes:,} เส้นทาง"),
        kpi("💰", "#FFF0E6", "ต้นทุนสูญเสียรวม", _money(total_loss),
            f"เฉลี่ย {_money(total_loss / n_routes if n_routes else 0)} ต่อเส้นทาง · {total_trips:,} เที่ยว"),
    ]
    if has_price:
        prices = valid["Price"].dropna()
        cards.append(kpi(
            "🏷️", "#E6F4FA", "ราคาต่อเส้นทาง (เฉลี่ย)", _money_full(prices.mean()),
            f"ต่ำสุด {_money_full(prices.min())} · สูงสุด {_money_full(prices.max())}", "#2F7F95",
        ))
        cards.append(kpi(
            "⚠️", "#FDE9EC", "เส้นทางที่ต้นทุนเฉลี่ยเกินราคา", f"{len(over):,} เส้นทาง",
            f"จาก {int(prices.size):,} เส้นทางที่มีราคา · เทียบต้นทุนเฉลี่ยต่อเที่ยวตามตัวกรอง",
            "#C23B53" if len(over) else "#0F172A",
        ))
    st.markdown('<div class="tc-kpi-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)

    # ---------------- ข้อสังเกตสำคัญ ----------------
    if not valid.empty:
        top_loss = valid.loc[valid["CostAll"].idxmax()]
        top_freq = valid.loc[valid["TripsAll"].idxmax()]

        def split_html(row, key):
            tot = float(row[f"{key}_{EMPTY}"] + row[f"{key}_{BRANCH}"]) or 1.0
            bar = "".join(
                f'<span style="width:{row[f"{key}_{t}"] / tot * 100:.1f}%;background:{TRIP_COLORS[t]}"></span>'
                for t in TYPES
            )
            fmt = _money if key == "Cost" else (lambda v: f"{int(v):,} เที่ยว")
            lines = "".join(
                f'<div class="tc-ins-line"><span class="tc-sw" style="background:{TRIP_COLORS[t]}"></span>'
                f'<span>{t}</span><b>{esc(fmt(row[f"{key}_{t}"]))}</b></div>'
                for t in TYPES
            )
            return f'<div class="tc-mini-bar">{bar}</div>{lines}'

        def price_line(row):
            if pd.isna(row["Price"]):
                return ""
            return (
                f'<div class="tc-ins-line"><span class="tc-sw" style="background:{PRICE_COLOR}"></span>'
                f'<span>ราคาต่อเส้นทาง</span><b>{_money_full(row["Price"])}</b></div>'
            )

        cells = [
            ("#E0566C", "💸", "เส้นทางที่สูญเสียมากที่สุด", _money(top_loss["CostAll"]),
             top_loss["_Route"], split_html(top_loss, "Cost") + price_line(top_loss)),
            ("#D0588A", "🔁", "เส้นทางที่เกิดบ่อยที่สุด", f'{int(top_freq["TripsAll"]):,} เที่ยว',
             top_freq["_Route"], split_html(top_freq, "Trips") + price_line(top_freq)),
        ]
        # ใช้เส้นทางที่วิ่งอย่างน้อย 5 เที่ยว เพื่อไม่ให้เส้นทาง 1–2 เที่ยวดึงค่าเฉลี่ยจนดูผิดปกติ
        over_reliable = over[over["TripsAll"] >= 5]
        if not over_reliable.empty:
            over = over_reliable
        if not over.empty:
            worst = over.loc[over["Diff"].idxmax()]
            cells.append((
                "#C23B53", "⚠️", "ต้นทุนเฉลี่ยเกินราคามากที่สุด" + (" (≥5 เที่ยว)" if not over_reliable.empty else ""), "+" + _money_full(worst["Diff"]),
                worst["_Route"],
                f'<div class="tc-ins-line"><span class="tc-sw" style="background:{TRIP_COLORS[EMPTY]}"></span>'
                f'<span>ต้นทุนเฉลี่ยต่อเที่ยว</span><b>{_money_full(worst["AvgActual"])}</b></div>'
                + price_line(worst)
                + f'<div class="tc-ins-sub">{int(worst["TripsAll"]):,} เที่ยว · เกินราคา '
                  f'{worst["Diff"] / worst["Price"] * 100:.0f}%</div>',
            ))
        elif has_price:
            top_price = valid.loc[valid["Price"].idxmax()]
            cells.append((
                "#2F7F95", "🏷️", "เส้นทางราคาสูงสุด", _money_full(top_price["Price"]),
                top_price["_Route"], f'<div class="tc-ins-sub">{int(top_price["TripsAll"]):,} เที่ยว</div>',
            ))
        html_cells = "".join(
            f'<div class="tc-ins"><div class="tc-ins-top">'
            f'<span class="tc-ins-icon" style="background:{_tint(c, 0.86)}">{icon}</span>'
            f'<span class="tc-ins-title">{esc(title)}</span></div>'
            f'<div class="tc-ins-metric" style="color:{c}">{esc(metric)}</div>'
            f'<div class="tc-ins-main">{esc(main)}</div>{extra}</div>'
            for c, icon, title, metric, main, extra in cells
        )
        st.markdown(
            '<div class="tc-ins-card"><div class="tc-ins-head">ข้อสังเกตสำคัญ</div>'
            f'<div class="tc-ins-grid" style="grid-template-columns:repeat({len(cells)}, minmax(0, 1fr))">'
            f"{html_cells}</div></div>",
            unsafe_allow_html=True,
        )

    # ---------------- อันดับเส้นทาง ----------------
    with _card("et_rank"):
        st.markdown("#### อันดับเส้นทาง")
        metric_opts = ["ต้นทุนสูญเสียรวม", "จำนวนเที่ยว"] + (
            ["ต้นทุนเฉลี่ยต่อเที่ยว เทียบ ราคาต่อเส้นทาง"] if has_price else [])
        o1, o2 = st.columns([1.5, 0.6])
        with o1:
            ov_metric = st.selectbox("ตัวชี้วัด", metric_opts, key=_wkey("et_rank_metric", metric_opts))
        with o2:
            ov_top = st.selectbox("จำนวน Top", [5, 10, 15, 20, 30], index=1, key="et_rank_top")

        if ov_metric.startswith("ต้นทุนเฉลี่ยต่อเที่ยว"):
            plot = valid[valid["Price"].notna()].sort_values("CostAll", ascending=False).head(ov_top).iloc[::-1]
            st.caption("แท่ง = ราคาต่อเส้นทางจากไฟล์ · ◆ = ต้นทุนเฉลี่ยต่อเที่ยวจริงตามตัวกรอง "
                       "(◆ แดง = เกินราคา, ◆ เขียว = ต่ำกว่าราคา) · เรียงตามต้นทุนสูญเสียรวม")
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name="ราคาต่อเส้นทาง", y=plot["_Route"], x=plot["Price"], orientation="h",
                marker_color=_tint(PRICE_COLOR, 0.35),
                text=plot["Price"].map(_money_full), textposition="inside", insidetextanchor="end",
                hovertemplate="%{y}<br>ราคาต่อเส้นทาง: ฿%{x:,.0f}<extra></extra>",
            ))
            fig.add_trace(go.Scatter(
                name="ต้นทุนเฉลี่ยต่อเที่ยว", y=plot["_Route"], x=plot["AvgActual"], mode="markers",
                marker=dict(size=13, symbol="diamond", line=dict(color="white", width=1.5),
                            color=["#D0505C" if d > 0 else "#3E9E6A" for d in plot["Diff"].fillna(0)]),
                customdata=plot[["TripsAll", "Diff"]].to_numpy(),
                hovertemplate=("%{y}<br>ต้นทุนเฉลี่ยต่อเที่ยว: ฿%{x:,.0f}"
                               "<br>ส่วนต่างจากราคา: ฿%{customdata[1]:,.0f}"
                               "<br>%{customdata[0]:,} เที่ยว<extra></extra>"),
            ))
            x_max = float(max(plot["Price"].max(), plot["AvgActual"].max())) if not plot.empty else None
            _chart_layout(fig, max(360, 34 * len(plot) + 120), "บาทต่อเที่ยว", x_max)
            st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
        else:
            key = "Cost" if ov_metric == "ต้นทุนสูญเสียรวม" else "Trips"
            rank_col = "CostAll" if key == "Cost" else "TripsAll"
            plot = valid[valid[rank_col] > 0].sort_values(rank_col, ascending=False).head(ov_top).iloc[::-1]
            st.caption("เส้นทางจาก Loading ↔ Unloading (วิ่งสลับทิศนับเป็นเส้นทางเดียวกัน) · แยกสีตามประเภทเที่ยว")
            fig = go.Figure()
            val_fmt = "฿%{x:,.0f}" if key == "Cost" else "%{x:,.0f} เที่ยว"
            for t in TYPES:
                fig.add_trace(go.Bar(
                    name=t, y=plot["_Route"], x=plot[f"{key}_{t}"], orientation="h",
                    marker_color=TRIP_COLORS[t],
                    hovertemplate=f"%{{y}}<br>{t}: {val_fmt}<extra></extra>",
                ))
            totals = plot[f"{key}_{EMPTY}"] + plot[f"{key}_{BRANCH}"]
            label_fmt = (lambda v: f"  {_money_full(v)}") if key == "Cost" else (lambda v: f"  {int(v):,}")
            fig.add_trace(go.Scatter(
                y=plot["_Route"], x=totals, mode="text", showlegend=False, hoverinfo="skip",
                text=totals.map(label_fmt), textposition="middle right",
                textfont=dict(color="#334155", size=12),
            ))
            fig.update_layout(barmode="stack")
            _chart_layout(fig, max(360, 34 * len(plot) + 120),
                          "บาท" if key == "Cost" else "จำนวนเที่ยว",
                          float(totals.max()) if not totals.empty else None)
            st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)

    # ---------------- แนวโน้มรายเดือนตามเส้นทาง ----------------
    with _card("et_trend"):
        st.markdown("#### แนวโน้มรายเดือนตามเส้นทาง")
        st.caption("แต่ละเส้น = 1 เส้นทาง (สีเดียวกับตาราง)")
        trend_opts = valid.sort_values("CostAll", ascending=False)["_Route"].tolist()
        t1, t2 = st.columns([3, 1.2])
        with t1:
            trend_routes = st.multiselect("เลือกเส้นทาง (สูงสุด 10)", trend_opts, default=trend_opts[:5],
                                          max_selections=10, key=_wkey("et_trend_routes", trend_opts))
        with t2:
            tr_metric = st.selectbox("ตัวชี้วัด", ["ต้นทุนสูญเสียรวม", "จำนวนเที่ยว", "ต้นทุนเฉลี่ยต่อเที่ยว"],
                                     key="et_tr_metric")
        t = filtered[filtered["_Route"].isin(trend_routes) & filtered["_Date"].notna()]
        if not trend_routes:
            st.info("เลือกอย่างน้อย 1 เส้นทาง")
        elif t.empty:
            st.info("ไม่มีข้อมูลวันที่สำหรับสร้างแนวโน้มรายเดือน")
        else:
            g = (
                t.assign(_P=t["_Date"].dt.to_period("M"))
                .groupby(["_P", "_Route"])
                .agg(Trips=("_TripId", "nunique"), Cost=("_Cost", "sum"))
                .reset_index().sort_values("_P")
            )
            g["Avg"] = g["Cost"] / g["Trips"].replace(0, float("nan"))
            g["Label"] = g["_P"].map(
                lambda p: f"{THAI_MONTHS[p.month]} {str(p.year + 543 if p.year < 2400 else p.year)[-2:]}"
            )
            ycol = {"ต้นทุนสูญเสียรวม": "Cost", "จำนวนเที่ยว": "Trips", "ต้นทุนเฉลี่ยต่อเที่ยว": "Avg"}[tr_metric]
            order = list(dict.fromkeys(g["Label"]))
            fig = go.Figure()
            for r in trend_routes:
                gr = g[g["_Route"] == r]
                if gr.empty:
                    continue
                fig.add_trace(go.Scatter(
                    name=r, x=gr["Label"], y=gr[ycol], mode="lines+markers",
                    line=dict(width=2.5, shape="spline", smoothing=0.6, color=route_colors.get(r, GRAY)),
                    marker=dict(size=7, line=dict(color="white", width=1.5)),
                    customdata=gr[["Trips", "Cost"]].to_numpy(),
                    hovertemplate=(f"<b>{esc(r)}</b> • %{{x}}<br>จำนวนเที่ยว: %{{customdata[0]:,}}"
                                   "<br>ต้นทุน: ฿%{customdata[1]:,.0f}<extra></extra>"),
                ))
            fig.update_layout(
                height=400, margin=dict(l=15, r=15, t=20, b=20),
                legend=dict(orientation="h", y=-0.22, x=0),
                xaxis=dict(title="", type="category", categoryorder="array", categoryarray=order),
                yaxis=dict(title="จำนวนเที่ยว" if ycol == "Trips" else "บาท", tickformat=",.0f",
                           rangemode="tozero"),
            )
            _style(fig)
            st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)

    # ---------------- องค์ประกอบต้นทุนของเส้นทาง ----------------
    with _card("et_pie"):
        st.markdown("#### องค์ประกอบต้นทุนของเส้นทาง")
        pie_routes = ["ทุกเส้นทาง"] + valid.sort_values("CostAll", ascending=False)["_Route"].tolist()
        p1, p2, p3 = st.columns([1.6, 1, 0.9])
        with p1:
            pie_route = st.selectbox("เส้นทาง", pie_routes, key=_wkey("et_pie_route", pie_routes))
        with p2:
            pie_type = st.selectbox("ประเภทเที่ยว", ["ทั้งหมด"] + TYPES, key="et_pie_type")
        pie_src = filtered if pie_route == "ทุกเส้นทาง" else filtered[filtered["_Route"] == pie_route]
        if pie_type != "ทั้งหมด":
            pie_src = pie_src[pie_src["_Type"] == pie_type]
        sums = {
            c: float(_num(pie_src[c]).fillna(0).sum())
            for c in KNOWN_COST_COLUMNS if c in pie_src.columns and c not in PIE_EXCLUDE
        }
        available = [c for c, v in sorted(sums.items(), key=lambda x: -x[1]) if v > 0]
        if not available:
            st.info("ไม่พบองค์ประกอบต้นทุนที่มีมูลค่า")
        else:
            default = [c for c in PIE_DEFAULT if c in available] or available[:4]
            cols_key = _wkey("et_pie_cols", available)
            n_sel = len(st.session_state.get(cols_key, default))
            with p3:
                st.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)
                picker = (st.popover(f"⚙️ รายการต้นทุน ({n_sel})") if hasattr(st, "popover")
                          else st.expander(f"⚙️ รายการต้นทุน ({n_sel})"))
            with picker:
                chosen = st.multiselect("เลือกต้นทุนที่ต้องการเปรียบเทียบ", available,
                                        default=default, key=cols_key)
            items = sorted([(c, sums[c]) for c in chosen if sums[c] > 0], key=lambda x: -x[1])
            if not items:
                st.info("กด ⚙️ รายการต้นทุน แล้วเลือกอย่างน้อย 1 รายการ")
            else:
                total = sum(v for _, v in items)
                colors = {c: PALETTE[i % len(PALETTE)] for i, (c, _) in enumerate(items)}
                fig = go.Figure(go.Pie(
                    labels=[c for c, _ in items], values=[v for _, v in items], hole=0.64, sort=False,
                    marker=dict(colors=[colors[c] for c, _ in items], line=dict(color="white", width=3)),
                    text=[f"{v / total * 100:.0f}%" if v / total >= 0.05 else "" for _, v in items],
                    textinfo="text", textposition="inside", insidetextfont=dict(color="#4A2A30", size=13),
                    hovertemplate="%{label}<br>฿%{value:,.0f}<br>%{percent}<extra></extra>",
                ))
                fig.update_layout(
                    height=290, showlegend=False, margin=dict(l=0, r=0, t=6, b=6),
                    annotations=[dict(
                        text=f"<span style='font-size:12px;color:#64748B'>รวมที่เลือก</span>"
                             f"<br><b style='font-size:18px;color:#1E293B'>{_money(total)}</b>",
                        x=0.5, y=0.5, showarrow=False,
                    )],
                )
                _style(fig)
                c_pie, c_leg = st.columns([1, 1.3], gap="small")
                with c_pie:
                    st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
                with c_leg:
                    rows = "".join(
                        f'<div class="tc-leg-row"><span class="tc-sw" style="background:{colors[c]}"></span>'
                        f'<span class="tc-leg-name">{esc(c)}</span><span class="tc-leg-val">{_money(v)}</span>'
                        f'<span class="tc-leg-pct">{v / total * 100:.1f}%</span></div>'
                        for c, v in items
                    )
                    n = trip_count(pie_src)
                    st.markdown(
                        f'<div class="tc-legend">{rows}</div>'
                        f'<div class="tc-leg-foot">{n:,} เที่ยว · เฉลี่ย ฿{(total / n if n else 0):,.0f} ต่อเที่ยว</div>',
                        unsafe_allow_html=True,
                    )

    # ---------------- ตารางเส้นทาง ----------------
    with _card("et_table"):
        st.markdown("#### ตารางเส้นทาง")
        table_routes = valid.sort_values("CostAll", ascending=False)["_Route"].tolist()
        s1, s2 = st.columns([3, 1])
        with s1:
            pick_routes = st.multiselect(
                "เลือกเส้นทาง (ไม่เลือก = แสดงทุกเส้นทาง)", table_routes,
                placeholder="พิมพ์ชื่อสถานที่เพื่อค้นหา", key=_wkey("et_table_routes", table_routes),
            )
        sort_opts = ["ต้นทุนสูญเสียรวม", "จำนวนเที่ยว"] + (
            ["ราคาต่อเส้นทาง"] if has_price else []) + ["ชื่อเส้นทาง"]
        with s2:
            sort_label = st.selectbox("เรียงตาม", sort_opts, key=_wkey("et_table_sort", sort_opts))
        sort_by, asc = {
            "ต้นทุนสูญเสียรวม": ("CostAll", False), "จำนวนเที่ยว": ("TripsAll", False),
            "ราคาต่อเส้นทาง": ("Price", False), "ส่วนต่างจากราคา": ("Diff", False),
            "ชื่อเส้นทาง": ("_Route", True),
        }[sort_label]
        tbl = valid if not pick_routes else valid[valid["_Route"].isin(pick_routes)]
        tbl = tbl.sort_values(sort_by, ascending=asc, na_position="last").reset_index(drop=True)
        cost_rank = {r: i for i, r in enumerate(table_routes, 1)}
        st.caption(
            f"แสดง {len(tbl):,} จาก {len(valid):,} เส้นทาง · # = อันดับตามต้นทุนสูญเสียรวม · "
            "ต้นทุนเฉลี่ย/เที่ยว = ต้นทุนรวม ÷ จำนวนเที่ยวตามตัวกรอง"
            + (" · ราคาต่อเส้นทาง มาจากไฟล์ (ไม่เปลี่ยนตามตัวกรอง)" if has_price else "")
        )
        max_cost = float(valid["CostAll"].max() or 1)
        head = ["#", "เส้นทาง", "ทิศทางการวิ่ง", EMPTY, BRANCH, "ต้นทุนสูญเสียรวม", "ต้นทุนเฉลี่ย/เที่ยว"]
        if has_price:
            head += ["ราคาต่อเส้นทาง"]
        body = []
        for r in tbl.to_dict("records"):
            color = route_colors.get(r["_Route"], GRAY)
            cells = [
                f'<td class="tc-rank">{cost_rank.get(r["_Route"], "")}</td>',
                f'<td><span class="tc-dot" style="background:{color}"></span><b>{esc(r["_Route"])}</b></td>',
                f'<td class="et-dirs-cell">{dir_html.get(r["_Route"], "")}</td>',
                f'<td class="tc-num">{int(r[f"Trips_{EMPTY}"]):,}<br>'
                f'<small class="tc-muted">{_money(r[f"Cost_{EMPTY}"])}</small></td>',
                f'<td class="tc-num">{int(r[f"Trips_{BRANCH}"]):,}<br>'
                f'<small class="tc-muted">{_money(r[f"Cost_{BRANCH}"])}</small></td>',
                f'<td class="tc-num"><b>{_money_full(r["CostAll"])}</b>'
                f'<div class="tc-bar"><span style="width:{r["CostAll"] / max_cost * 100:.1f}%;'
                f'background:{color}"></span></div></td>',
                f'<td class="tc-num">{_money_full(r["AvgActual"])}</td>',
            ]
            if has_price:
                price_txt = _money_full(r["Price"]) if pd.notna(r["Price"]) else "—"
                cells.append(f'<td class="tc-num et-price">{price_txt}</td>')
            body.append("<tr>" + "".join(cells) + "</tr>")
        st.markdown(_table_html(head, body, right_cols=set(range(3, len(head))), max_height=480),
                    unsafe_allow_html=True)
        export = pd.DataFrame({
            "เส้นทาง": tbl["_Route"],
            f"{EMPTY} (เที่ยว)": tbl[f"Trips_{EMPTY}"], f"ต้นทุน{EMPTY}": tbl[f"Cost_{EMPTY}"],
            f"{BRANCH} (เที่ยว)": tbl[f"Trips_{BRANCH}"], f"ต้นทุน{BRANCH}": tbl[f"Cost_{BRANCH}"],
            "ต้นทุนสูญเสียรวม": tbl["CostAll"], "ต้นทุนเฉลี่ยต่อเที่ยว": tbl["AvgActual"].round(2),
            **({"ราคาต่อเส้นทาง": tbl["Price"]} if has_price else {}),
        })
        st.download_button(
            "⬇️ ดาวน์โหลดตารางเส้นทาง (CSV)", export.to_csv(index=False).encode("utf-8-sig"),
            file_name="empty_trip_routes.csv", mime="text/csv", key="et_route_download",
        )

    # ---------------- รายละเอียดเส้นทาง ----------------
    with _card("et_detail"):
        st.markdown("#### รายละเอียดเส้นทาง")
        route_opts2 = valid.sort_values("CostAll", ascending=False)["_Route"].tolist()
        if not route_opts2:
            st.info("ไม่มีเส้นทางตามตัวกรอง")
        else:
            pick = st.selectbox("เลือกเส้นทาง", route_opts2, key=_wkey("et_detail_route", route_opts2))
            row = valid[valid["_Route"] == pick].iloc[0]
            d = filtered[filtered["_Route"] == pick].sort_values("_Cost", ascending=False)
            boxes = [
                ("จำนวนเที่ยว", f'{int(row["TripsAll"]):,}',
                 f'{EMPTY} {int(row[f"Trips_{EMPTY}"]):,} · {BRANCH} {int(row[f"Trips_{BRANCH}"]):,}'),
                ("ต้นทุนสูญเสียรวม", _money(row["CostAll"]),
                 f'{EMPTY} {_money(row[f"Cost_{EMPTY}"])} · {BRANCH} {_money(row[f"Cost_{BRANCH}"])}'),
                ("ต้นทุนเฉลี่ยต่อเที่ยว", _money_full(row["AvgActual"]), "ตามตัวกรอง"),
            ]
            if has_price and pd.notna(row["Price"]):
                diff = row["Diff"]
                boxes += [
                    ("ราคาต่อเส้นทาง", _money_full(row["Price"]),
                     f'เฉลี่ยหลังตัด outlier {_money_full(row["AvgKept"])}'),
                    ("ส่วนต่างจากราคา", ("+" if diff > 0 else "−") + _money_full(abs(diff)),
                     "ต้นทุนเฉลี่ยเกินราคา" if diff > 0 else "ต้นทุนเฉลี่ยต่ำกว่าราคา"),
                ]
            st.markdown(
                '<div class="et-route-grid">' + "".join(
                    f'<div class="et-route-box"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div>'
                    f'<div class="s">{esc(s)}</div></div>' for k, v, s in boxes
                ) + "</div>" + dir_html.get(pick, ""),
                unsafe_allow_html=True,
            )

            with st.expander(f"ดูรายเที่ยวของเส้นทางนี้ ({trip_count(d):,} เที่ยว)"):
                mf_col = find_manifest_col(d)
                has_id = "Travel Req. No." in d.columns
                head = (["วันที่"] + (["Manifest No."] if mf_col else []) + (["Trip ID"] if has_id else [])
                        + ["ทิศทางการวิ่ง", "ประเภทเที่ยว"] + (["ประเภทรถ"] if vehicle_col else [])
                        + ["ระยะทาง", "ต้นทุนรวม"] + (["ตัด outlier"] if flag_col else []))
                body = []
                for r in d.head(300).to_dict("records"):
                    date_txt = r["_Date"].strftime("%d/%m/%Y") if pd.notna(r["_Date"]) else "—"
                    cells = [f'<td class="tc-muted">{date_txt}</td>']
                    if mf_col:
                        cells.append(f'<td class="tc-mono"><b>{esc(_id_text(r.get(mf_col)))}</b></td>')
                    if has_id:
                        cells.append(f'<td class="tc-mono">{esc(_id_text(r.get("Travel Req. No.")))}</td>')
                    cells += [
                        f'<td>{esc(str(r["_Load"]))}{ARROW}{esc(str(r["_Unload"]))}</td>',
                        f'<td>{_badge(r["_Type"], TRIP_COLORS[r["_Type"]])}</td>',
                    ]
                    if vehicle_col:
                        cells.append(f'<td class="tc-muted">{esc(_id_text(r.get(vehicle_col)))}</td>')
                    cells += [
                        f'<td class="tc-num tc-muted">{_km(r["_Distance"])}</td>',
                        f'<td class="tc-num"><b>{_money_full(r["_Cost"])}</b></td>',
                    ]
                    if flag_col:
                        flag = str(r["_Flag"])
                        flag_color = "#EC7F86" if flag == "ตัด" else "#86CFA3"
                        cells.append(f"<td>{_badge(flag or '—', flag_color)}</td>")
                    body.append("<tr>" + "".join(cells) + "</tr>")
                num_cols = {head.index("ระยะทาง"), head.index("ต้นทุนรวม")}
                st.caption("เรียงจากต้นทุนสูงสุด · แสดงสูงสุด 300 เที่ยว"
                           + (" · ตัด = เที่ยวที่ไฟล์ไม่นำมาคิดค่าเฉลี่ยหลังตัด outlier" if flag_col else ""))
                st.markdown(_table_html(head, body, right_cols=num_cols, max_height=420),
                            unsafe_allow_html=True)
                export = pd.DataFrame({
                    "วันที่": d["_Date"].dt.strftime("%d/%m/%Y"),
                    **({"Manifest No.": d[mf_col].map(_id_text)} if mf_col else {}),
                    **({"Trip ID": d["Travel Req. No."].map(_id_text)} if has_id else {}),
                    "ต้นทาง (Loading)": d["_Load"], "ปลายทาง (Unloading)": d["_Unload"],
                    "ประเภทเที่ยว": d["_Type"],
                    **({"ประเภทรถ": d[vehicle_col]} if vehicle_col else {}),
                    "ระยะทาง (กม.)": d["_Distance"], "ต้นทุนรวม": d["_Cost"],
                    **({"ตัด outlier": d["_Flag"]} if flag_col else {}),
                })
                st.download_button(
                    f"⬇️ ดาวน์โหลด {len(d):,} เที่ยว (CSV)", export.to_csv(index=False).encode("utf-8-sig"),
                    file_name="empty_trip_route_detail.csv", mime="text/csv", key="et_detail_download",
                )

    note = "" if has_price else " · ไม่พบคอลัมน์ ราคาต่อเส้นทาง ในไฟล์"
    st.markdown(
        f'<div class="tc-source">ข้อมูลจาก {esc(source_file)} · {len(work):,} เที่ยว (เที่ยวเปล่า + รถว่างไปสาขา)'
        f" · แสดง {total_trips:,} เที่ยวตามตัวกรอง{note}</div>",
        unsafe_allow_html=True,
    )