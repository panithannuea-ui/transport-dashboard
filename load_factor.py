"""
load_factor.py
--------------
Load Factor Dashboard (ธีมแดง-ขาวพาสเทล แบบเดียวกับหน้าอื่น)

ตรรกะการคำนวณยึดตามโค้ด load_factor_dashboard_standalone_latest.py ทุกอย่าง:
- 1 แถว = 1 เที่ยว (Trip Key Unique ไม่ซ้ำ)
- LF รวม = ผลรวมน้ำหนัก ÷ ผลรวมความจุ (ไม่ใช่ค่าเฉลี่ยของ LF รายเที่ยว)
- Volume LF > 150% = Check/Outlier: เก็บค่าจริงไว้ในรายละเอียด
  แต่ไม่นำมาคำนวณ Volume LF รวม (ภาพรวม / ชนิดรถ / เส้นทาง)
- Route Key = ระดับเส้นทาง (↔), Trip Direction = ทิศทางวิ่งจริงของเที่ยว (→)

เปลี่ยนเฉพาะหน้าตา: การ์ด KPI, ข้อสังเกตสำคัญ, กราฟสีตามกลุ่ม, ตารางแบบเดียวกับหน้า Transportation
"""

import hashlib
from html import escape as esc

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

FONT = "Noto Sans Thai, IBM Plex Sans Thai, sans-serif"
TEXT = "#1E293B"
MUTED = "#64748B"
GRID = "#F6E6E9"
PLOT_CONFIG = {"displayModeBar": False}

# ช่วงอัตราการใช้ความจุ (ตามโค้ดเดิม)
ORDER = ["0 – 40%", ">40 – 70%", ">70 – 100%", ">100 – 150%", ">150%"]
STATUS_MAP = {
    ORDER[0]: "ใช้ความจุต่ำ",
    ORDER[1]: "ใช้ความจุปานกลาง",
    ORDER[2]: "ใช้ความจุสูง",
    ORDER[3]: "เกินความสามารถบรรทุก",
    ORDER[4]: "ผิดปกติ",
}
MEANING = {
    ORDER[0]: "บรรทุกน้อย",
    ORDER[1]: "เริ่มใช้ความจุ",
    ORDER[2]: "ใช้ความจุค่อนข้างมาก",
    ORDER[3]: "ควรตรวจสอบ",
    ORDER[4]: "ควรตรวจสอบข้อมูล",
}
# สีตามความหมาย (พาสเทล): ต่ำ=ฟ้า, ปานกลาง=เหลือง, สูง=เขียว, เกิน=ส้ม, ผิดปกติ=แดง
GROUP_COLORS = {
    ORDER[0]: "#95B8E6",
    ORDER[1]: "#EFCB64",
    ORDER[2]: "#86CFA3",
    ORDER[3]: "#F6AE6B",
    ORDER[4]: "#EC7F86",
}
OUTLIER_COLOR = "#EC7F86"
# สีทิศทางวิ่งในตารางเส้นทาง: ทิศหลัก (วิ่งบ่อยกว่า) = เข้ม, อีกทิศ = อ่อน
DIR_COLORS = ["#E8687C", "#F7B6C1", "#FAD4DB"]
ARROW = ' <span class="lfx-arrow">→</span> '
# สีตัวเลขในข้อสังเกตสำคัญ (เข้มกว่าสีกราฟ ให้อ่านง่ายบนพื้นขาว)
INS_TEXT = {"#95B8E6": "#4F7CC0", "#86CFA3": "#3E9E6A", "#EC7F86": "#D0505C"}

PAGE_CSS = """
<style>
.lfx-title { font-size: 15px; font-weight: 700; color: #0F172A; margin-bottom: 2px; }

/* KPI */
.lfx-kpi-grid { display: grid; gap: 14px; margin: 8px 0 4px; }
.lfx-kpi-grid.top { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.lfx-kpi-grid.sub { grid-template-columns: repeat(4, minmax(0, 1fr)); margin-top: 12px; }
.lfx-kpi { background: #fff; border: 1px solid #F4D8DE; border-radius: 18px; padding: 16px 18px;
           display: flex; gap: 14px; align-items: center; min-width: 0;
           box-shadow: 0 1px 2px rgba(15, 23, 42, .04), 0 8px 24px rgba(226, 90, 112, .08); }
.lfx-kpi.flat { border: none; box-shadow: none; padding: 4px 0; background: transparent; }
.lfx-kpi-icon { width: 46px; height: 46px; border-radius: 14px; display: grid; place-items: center;
                font-size: 22px; flex: none; }
.lfx-kpi-body { min-width: 0; flex: 1; }
.lfx-kpi-label { font-size: 12.5px; color: #64748B; font-weight: 600; }
.lfx-kpi-value { font-size: 25px; font-weight: 800; color: #0F172A; line-height: 1.2; white-space: nowrap;
                 overflow: hidden; text-overflow: ellipsis; }
.lfx-kpi-grid.sub .lfx-kpi-value { font-size: 21px; }
.lfx-kpi-sub { font-size: 11.5px; color: #94A3B8; }
.lfx-meter { height: 7px; border-radius: 99px; background: #FBEBEE; margin-top: 8px; overflow: hidden; }
.lfx-meter > span { display: block; height: 100%; border-radius: 99px; }

/* Insights */
.lfx-ins-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 6px 0 4px; }
.lfx-ins { padding: 4px 18px; min-width: 0; }
.lfx-ins + .lfx-ins { border-left: 1px solid #FBEBEE; }
.lfx-ins-title { font-size: 12.5px; font-weight: 600; color: #64748B; display: flex; align-items: center; gap: 8px; }
.lfx-ins-icon { width: 28px; height: 28px; border-radius: 9px; display: grid; place-items: center; font-size: 14px; }
.lfx-ins-metric { font-size: 26px; font-weight: 800; line-height: 1.15; margin-top: 8px; }
.lfx-ins-sub { font-size: 12px; color: #94A3B8; margin-top: 4px; line-height: 1.5; }

/* Legend (กราฟวงกลม + คำอธิบายช่วง) */
.lfx-legend { margin-top: 4px; }
.lfx-leg-row { display: grid; grid-template-columns: 12px minmax(0, 1fr) auto 54px; gap: 10px; align-items: center;
               padding: 8px 4px; border-bottom: 1px dashed #F4E4E7; font-size: 13px; }
.lfx-leg-row:last-child { border-bottom: none; }
.lfx-sw { width: 12px; height: 12px; border-radius: 4px; }
.lfx-leg-name { color: #1E293B; font-weight: 600; min-width: 0; }
.lfx-leg-name small { display: block; color: #94A3B8; font-weight: 500; font-size: 11.5px; }
.lfx-leg-val { color: #334155; font-variant-numeric: tabular-nums; text-align: right; }
.lfx-leg-pct { color: #64748B; text-align: right; font-variant-numeric: tabular-nums; }

/* ตาราง */
.lfx-table-wrap { overflow: auto; background: #FFFFFF; border: 1px solid #F6DDE2; border-radius: 14px; margin: 6px 0 8px; }
.lfx-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13.5px; margin: 0 !important; }
.lfx-table thead th {
    position: sticky; top: 0; z-index: 3; background: #FFF3F5; color: #475569;
    font-weight: 700; font-size: 12.5px; text-align: left; padding: 11px 14px;
    border-bottom: 1px solid #F6DDE2; white-space: nowrap;
}
.lfx-table td { padding: 9px 14px; border-bottom: 1px solid #FBEFF1; color: #1E293B; white-space: nowrap; }
.lfx-table tbody tr:nth-child(even) td { background: #FFFBFC; }
.lfx-table tbody tr:hover td { background: #FFE8EC; }
.lfx-num { text-align: right !important; font-variant-numeric: tabular-nums; }
.lfx-muted { color: #64748B !important; }
.lfx-rank { color: #94A3B8 !important; font-size: 12px; width: 30px; }
.lfx-arrow { color: #F4A3B1; font-weight: 700; margin: 0 2px; }
.lfx-lf { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
.lfx-lf-bar { width: 70px; height: 6px; border-radius: 99px; background: #FBEBEE; overflow: hidden; flex: none; }
.lfx-lf-bar > span { display: block; height: 100%; border-radius: 99px; }
.lfx-dirs-cell { white-space: normal !important; min-width: 280px; }
.lfx-dirs { display: flex; flex-direction: column; gap: 3px; }
.lfx-split { display: flex; height: 5px; border-radius: 99px; overflow: hidden; background: #FBEBEE; margin-bottom: 3px; }
.lfx-split > span { display: block; height: 100%; }
.lfx-dir { display: grid; grid-template-columns: 9px minmax(0, 1fr) auto 36px; gap: 8px; align-items: center;
           font-size: 12.5px; color: #475569; line-height: 1.45; }
.lfx-dir-sw { width: 9px; height: 9px; border-radius: 3px; }
.lfx-dir-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lfx-dir b { color: #1E293B; font-weight: 700; font-variant-numeric: tabular-nums; text-align: right; }
.lfx-dir small { color: #94A3B8; font-size: 11.5px; text-align: right; font-variant-numeric: tabular-nums; }
.lfx-badge { display: inline-block; font-size: 12px; font-weight: 600; padding: 2px 10px; border-radius: 99px; }
.lfx-chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 2px 0; }
.lfx-chip { background: #FFE8EC; color: #C23B53; font-size: 12.5px; font-weight: 600; padding: 4px 12px; border-radius: 99px; }
.lfx-chip-muted { background: #F1F5F9; color: #64748B; font-weight: 500; }
.lfx-note { background: #FFF7F8; border: 1px dashed #F4B3BF; border-radius: 14px; padding: 12px 16px;
            font-size: 12.5px; color: #6B4A51; line-height: 1.6; margin-top: 10px; }
.lfx-source { font-size: 12px; color: #94A3B8; margin: 8px 4px 20px; }

@media (max-width: 1100px) {
  .lfx-kpi-grid.sub { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .lfx-ins-grid { grid-template-columns: 1fr; }
  .lfx-ins + .lfx-ins { border-left: none; border-top: 1px solid #FBEBEE; padding-top: 12px; }
}
@media (max-width: 700px) {
  .lfx-kpi-grid.top, .lfx-kpi-grid.sub { grid-template-columns: 1fr; }
}
</style>
"""


# =========================================================
# HELPERS (ตรรกะเดิมจากโค้ดของเพื่อน)
# =========================================================

def _lf_numeric_ratio(series):
    """แปลงค่า Load Factor ให้เป็น ratio เช่น 0.68 = 68%"""
    s = pd.to_numeric(series, errors="coerce").astype("Float64")
    valid = s.dropna().abs()
    if valid.empty:
        return s
    q50 = float(valid.quantile(0.50))
    q90 = float(valid.quantile(0.90))
    # Dataset หลักเก็บเป็น ratio; รองรับกรณี source เก็บ 68 แทน 0.68
    if q50 > 3 or q90 > 10:
        s = s / 100.0
    return s


def _lf_safe_ratio(weight, capacity):
    w = pd.to_numeric(weight, errors="coerce").fillna(0).sum()
    c = pd.to_numeric(capacity, errors="coerce").fillna(0).sum()
    return (w / c) if c not in (0, 0.0) else float("nan")


def _group(v):
    if pd.isna(v):
        return "ไม่ระบุ"
    p = float(v) * 100
    if p <= 40:
        return ORDER[0]
    if p <= 70:
        return ORDER[1]
    if p <= 100:
        return ORDER[2]
    if p <= 150:
        return ORDER[3]
    return ORDER[4]


def _num(series):
    return pd.to_numeric(
        series.astype("string")
        .str.replace(",", "", regex=False)
        .str.replace("฿", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.strip(),
        errors="coerce",
    )


# =========================================================
# HELPERS (หน้าตา)
# =========================================================

def _card(name: str):
    """การ์ดพื้นขาว (CSS อยู่ใน theme.py: div[class*="st-key-tccard_"])"""
    try:
        return st.container(key=f"tccard_lf_{name}")
    except TypeError:
        return st.container(border=True)


def _wkey(base: str, options) -> str:
    """key ที่เปลี่ยนตามรายการตัวเลือก กัน error เวลาตัวเลือกเปลี่ยนตามตัวกรอง"""
    digest = hashlib.md5("|".join(map(str, options)).encode("utf-8")).hexdigest()[:10]
    return f"{base}_{digest}"


def _tint(hex_color: str, amount: float = 0.85) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (round(c + (255 - c) * amount) for c in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}"


def _fmt_amount(value, decimals=0):
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):,.{decimals}f}"


def _fmt_pct(ratio):
    """ratio 0.6812 -> '68.12%'"""
    if ratio is None or pd.isna(ratio):
        return "—"
    return f"{float(ratio) * 100:,.2f}%"


def _lf_cell(ratio):
    """ช่อง LF ในตาราง: ตัวเลข % + แถบสีตามช่วง"""
    if ratio is None or pd.isna(ratio):
        return '<td class="lfx-num lfx-muted">—</td>'
    color = GROUP_COLORS.get(_group(ratio), "#CBD5E1")
    width = max(0.0, min(float(ratio), 1.5)) / 1.5 * 100
    return (
        f'<td class="lfx-num"><div class="lfx-lf">{_fmt_pct(ratio)}'
        f'<span class="lfx-lf-bar"><span style="width:{width:.1f}%;background:{color}"></span></span></div></td>'
    )


def _table_html(head, body, right_cols=(), max_height=420) -> str:
    ths = "".join(
        f'<th class="{"lfx-num" if i in right_cols else ""}">{esc(h)}</th>' for i, h in enumerate(head)
    )
    return (
        f'<div class="lfx-table-wrap" style="max-height:{max_height}px">'
        f'<table class="lfx-table"><thead><tr>{ths}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div>'
    )


def _style(fig):
    fig.update_layout(
        font=dict(family=FONT, color=MUTED, size=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="white", bordercolor="#F4D6DC",
                        font=dict(family=FONT, color=TEXT, size=13)),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    try:
        fig.update_layout(barcornerradius=6)
    except (ValueError, TypeError):
        pass
    return fig


def _lf_routes(load: pd.Series, unload: pd.Series):
    """เส้นทางจาก Loading ↔ Unloading: วิ่งสลับทิศนับเป็นเส้นทางเดียวกัน
    ชื่อเส้นทางเรียงตามทิศที่วิ่งบ่อยที่สุด (แบบเดียวกับหน้า Transportation Cost)"""
    def clean(s):
        s = s.astype("string").fillna("").str.replace(r"\s+", " ", regex=True).str.strip()
        return s.mask(s.eq("") | s.str.casefold().isin(["nan", "none", "<na>"]), "ไม่ระบุ")

    a, b = clean(load), clean(unload)
    key = pd.Series(["|".join(sorted(p)) for p in zip(a, b)], index=a.index)
    top = (
        pd.DataFrame({"k": key, "a": a, "b": b})
        .groupby(["k", "a", "b"]).size().reset_index(name="n")
        .sort_values(["k", "n", "a"], ascending=[True, False, True])
        .drop_duplicates("k")
    )
    main = {k: (x, y) for k, x, y in zip(top["k"], top["a"], top["b"])}
    names = []
    for k, x, y in zip(key, a, b):
        p, q = main[k]
        if x == "ไม่ระบุ" and y == "ไม่ระบุ":
            names.append("ไม่ระบุเส้นทาง")
        elif x == y:
            names.append(f"{x} (ภายในพื้นที่)")
        else:
            names.append(f"{p} ↔ {q}")
    return pd.Series(names, index=a.index), (a + " → " + b)


def _level_table(filtered, by, label, top_rank):
    """ตารางระดับชนิดรถ / เส้นทาง: LF = ผลรวม ÷ ผลรวมความจุ (ไม่รวม Volume Outlier ในปริมาตร)"""
    t = (
        filtered.groupby(by, dropna=False)
        .agg({
            "Trip Key Unique": "nunique",
            "_Weight": "sum",
            "_Capacity": "sum",
            "_VolumeAgg": "sum",
            "_VolumeCapacityAgg": "sum",
        })
        .reset_index()
    )
    t["LF_W"] = t["_Weight"].div(t["_Capacity"].replace(0, pd.NA))
    t["LF_V"] = t["_VolumeAgg"].div(t["_VolumeCapacityAgg"].replace(0, pd.NA))
    t = t.sort_values("Trip Key Unique", ascending=False).reset_index(drop=True)
    t["_Rank"] = range(1, len(t) + 1)
    return t


# =========================================================
# DASHBOARD
# =========================================================

def render_load_factor_dashboard(raw_load_factor_df, source_labels=None):
    """Load Factor Dashboard — ข้อมูลจริงจากไฟล์ Load Factor เท่านั้น"""
    if raw_load_factor_df is None or raw_load_factor_df.empty:
        st.info("ยังไม่มีข้อมูล Load Factor — ไปที่ Data Management แล้วอัปโหลด "
                "`ค่าเดินทาง+Revenue3ปี=Loadfactorใหม่.xlsx`")
        return

    df = raw_load_factor_df.copy()
    df.columns = [" ".join(str(c).strip().split()) for c in df.columns]

    required = [
        "Trip Key Unique", "Trip Date", "Trip Year", "Trip Vehicle Model",
        "Trip Loading", "Trip Unloading", "Route Key", "Trip Weight",
        "Trip Weight Capacity",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error("ไฟล์ Load Factor ขาดคอลัมน์ที่จำเป็น: " + ", ".join(missing))
        return

    # ---------------- เตรียมข้อมูล (ตรรกะเดิม) ----------------
    df["_TripDate"] = pd.to_datetime(df["Trip Date"], errors="coerce", dayfirst=True)
    df["_MonthNum"] = df["_TripDate"].dt.month
    df["_Weight"] = _num(df["Trip Weight"])
    df["_Capacity"] = _num(df["Trip Weight Capacity"])
    df["_Volume"] = (_num(df["Trip Volume"]) if "Trip Volume" in df.columns
                     else pd.Series(pd.NA, index=df.index, dtype="Float64"))
    df["_VolumeCapacity"] = (_num(df["Trip Volume Capacity"]) if "Trip Volume Capacity" in df.columns
                             else pd.Series(pd.NA, index=df.index, dtype="Float64"))

    if "Trip Weight Loadfactor" in df.columns:
        df["_WeightLF"] = _lf_numeric_ratio(df["Trip Weight Loadfactor"])
    else:
        df["_WeightLF"] = df["_Weight"] / df["_Capacity"].replace(0, pd.NA)

    if "Trip Volume Loadfactor" in df.columns:
        df["_VolumeLF"] = _lf_numeric_ratio(df["Trip Volume Loadfactor"])
    else:
        df["_VolumeLF"] = df["_Volume"] / df["_VolumeCapacity"].replace(0, pd.NA)

    # Volume LF > 150% = Check/Outlier: เก็บแถวและค่าจริงไว้ แต่ไม่นับใน Volume LF รวม
    df["_VolumeOutlier"] = df["_VolumeLF"].notna() & (df["_VolumeLF"] > 1.50)
    df["_VolumeStatus"] = "OK"
    df.loc[df["_VolumeOutlier"], "_VolumeStatus"] = "Check/Outlier"
    df["_VolumeAgg"] = df["_Volume"].where(~df["_VolumeOutlier"], 0.0)
    df["_VolumeCapacityAgg"] = df["_VolumeCapacity"].where(~df["_VolumeOutlier"], 0.0)

    for c in ["Trip Year", "Trip Vehicle Model", "Trip Loading", "Trip Unloading",
              "Route Key", "Trip Key Unique"]:
        df[c] = df[c].astype("string").fillna("").str.strip()

    # Route Key = ระดับเส้นทาง (↔) / Trip Direction = ทิศทางวิ่งจริง (→) — ห้ามสลับกัน
    if "Trip Direction" not in df.columns:
        df["Trip Direction"] = (
            df["Trip Loading"].fillna("").astype(str).str.strip()
            + " → "
            + df["Trip Unloading"].fillna("").astype(str).str.strip()
        ).str.strip(" →")
    df["Trip Direction"] = df["Trip Direction"].astype("string").fillna("").str.strip()
    df["Route Key"] = df["Route Key"].astype("string").fillna("").str.strip()

    # เส้นทางจาก Loading ↔ Unloading (ใช้ในส่วน "สรุปตามเส้นทาง")
    df["_LFRoute"], df["_LFDir"] = _lf_routes(df["Trip Loading"], df["Trip Unloading"])

    # ระดับเที่ยว: 1 แถว = 1 Trip Key ไม่ซ้ำ
    trip_df = (
        df[df["Trip Key Unique"].ne("")]
        .sort_index()
        .drop_duplicates(subset=["Trip Key Unique"], keep="first")
        .copy()
    )

    st.markdown(PAGE_CSS, unsafe_allow_html=True)

    # ---------------- ตัวกรอง ----------------
    def opts(c):
        return ["ทั้งหมด"] + sorted({
            str(x).strip() for x in trip_df[c].dropna()
            if str(x).strip() not in {"", "<NA>", "nan"}
        })

    fcard = _card("filters")
    fcard.markdown('<div class="lfx-title">🔎 ตัวกรองข้อมูล</div>', unsafe_allow_html=True)
    f1, f2, f3, f4, f5 = fcard.columns([0.85, 1.15, 1.45, 2.3, 0.9])
    with f1:
        year = st.selectbox("ปี (พ.ศ.)", opts("Trip Year"), key="lf3_year")
    with f2:
        vehicle = st.selectbox("ชนิดรถ", opts("Trip Vehicle Model"), key="lf3_vehicle")
    with f3:
        route = st.selectbox("เส้นทาง (Route Key)", opts("Route Key"), key="lf3_route")
    with f4:
        search = st.text_input(
            "ค้นหา (รถ, เส้นทาง, ทะเบียน, ลูกค้า, เลขที่เที่ยว)",
            key="lf3_search", placeholder="ค้นหา...",
        )
    with f5:
        st.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)
        if st.button("⟳ รีเฟรชข้อมูล", key="lf3_refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    filtered = trip_df.copy()
    if year != "ทั้งหมด":
        filtered = filtered[filtered["Trip Year"] == year]
    if vehicle != "ทั้งหมด":
        filtered = filtered[filtered["Trip Vehicle Model"] == vehicle]
    if route != "ทั้งหมด":
        filtered = filtered[filtered["Route Key"] == route]
    if search.strip():
        q = search.strip().casefold()
        search_cols = [c for c in [
            "Trip Vehicle Model", "Route Key", "Trip Direction", "Trip Loading", "Trip Unloading",
            "License Plate", "Customer", "Trip Customer", "Trip Key Unique",
        ] if c in filtered.columns]
        mask = pd.Series(False, index=filtered.index)
        for c in search_cols:
            mask |= filtered[c].astype(str).str.casefold().str.contains(q, na=False, regex=False)
        filtered = filtered[mask]

    if filtered.empty:
        st.warning("ไม่พบข้อมูลตามตัวกรองที่เลือก")
        return

    # ---------------- KPI: จำนวนเที่ยว + อัตราการใช้ความจุ (เลือกน้ำหนัก/ปริมาตร) ----------------
    trips = filtered["Trip Key Unique"].nunique()
    wlf = _lf_safe_ratio(filtered["_Weight"], filtered["_Capacity"])
    vlf = (
        _lf_safe_ratio(filtered["_VolumeAgg"], filtered["_VolumeCapacityAgg"])
        if filtered["_VolumeAgg"].notna().any() and filtered["_VolumeCapacityAgg"].notna().any()
        else None
    )
    n_outlier = int(filtered["_VolumeOutlier"].sum())

    def kpi(icon, bg, label, value, sub, meter_ratio=None):
        meter = ""
        if meter_ratio is not None and pd.notna(meter_ratio):
            color = GROUP_COLORS.get(_group(meter_ratio), "#CBD5E1")
            width = max(0.0, min(float(meter_ratio), 1.0)) * 100
            meter = f'<div class="lfx-meter"><span style="width:{width:.1f}%;background:{color}"></span></div>'
        return (
            f'<div class="lfx-kpi flat"><div class="lfx-kpi-icon" style="background:{bg}">{icon}</div>'
            f'<div class="lfx-kpi-body"><div class="lfx-kpi-label">{esc(label)}</div>'
            f'<div class="lfx-kpi-value">{esc(value)}</div>'
            f'<div class="lfx-kpi-sub">{esc(sub)}</div>{meter}</div></div>'
        )

    with _card("kpi"):
        k1, k2 = st.columns([1, 1.8], gap="large")
        with k1:
            st.markdown(
                kpi("🚚", "#FFE8EC", "จำนวนเที่ยวทั้งหมด", f"{trips:,}", "เที่ยว (นับ Trip Key ไม่ซ้ำ)"),
                unsafe_allow_html=True,
            )
        with k2:
            v1, v2 = st.columns([1.6, 1])
            with v2:
                metric = st.selectbox(
                    "ตัวชี้วัด (ใช้กับทั้งหน้า)", ["น้ำหนัก", "ปริมาตร"], key="lf3_metric_sel",
                )
            if metric == "น้ำหนัก":
                lf_value, icon, bg = wlf, "⚖️", "#FFF0E6"
                sub = "น้ำหนักรวม ÷ ความจุน้ำหนักรวม"
            else:
                lf_value, icon, bg = vlf, "📦", "#E6F4FA"
                sub = (f"ไม่นับ {n_outlier:,} เที่ยวที่ Volume LF > 150%" if n_outlier
                       else "ปริมาตรรวม ÷ ความจุปริมาตรรวม")
            with v1:
                st.markdown(
                    kpi(icon, bg, f"อัตราการใช้ความจุ ({metric})",
                        _fmt_pct(lf_value) if lf_value is not None else "—", sub, lf_value),
                    unsafe_allow_html=True,
                )
    metric_col = "_WeightLF" if metric == "น้ำหนัก" else "_VolumeLF"

    # ---------------- วิเคราะห์ Load Factor ----------------
    with _card("analysis"):
        st.markdown(f"#### วิเคราะห์ Load Factor ({metric})")
        st.caption("เปลี่ยนตัวชี้วัดได้ที่การ์ดอัตราการใช้ความจุด้านบน")
        filtered["_LFGroup"] = filtered[metric_col].map(_group)
        dist = (
            filtered.groupby("_LFGroup")["Trip Key Unique"].nunique()
            .reindex(ORDER, fill_value=0).reset_index(name="Trips")
        )
        total = int(dist["Trips"].sum())
        dist["Pct"] = dist["Trips"] / total * 100 if total else 0.0
        by_group = dict(zip(dist["_LFGroup"], dist["Trips"]))
        pct_of = (lambda n: n / total * 100 if total else 0.0)

        # ข้อสังเกตสำคัญ
        low = by_group.get(ORDER[0], 0)
        over = by_group.get(ORDER[3], 0) + by_group.get(ORDER[4], 0)
        good = by_group.get(ORDER[2], 0)
        ins = [
            (GROUP_COLORS[ORDER[0]], "🪶", "เที่ยวที่ใช้ความจุต่ำ (≤ 40%)",
             f"{low:,} เที่ยว", f"{pct_of(low):.1f}% ของเที่ยวที่มีข้อมูล {metric} · โอกาสรวมเที่ยว/ลดขนาดรถ"),
            (GROUP_COLORS[ORDER[2]], "✅", "เที่ยวที่ใช้ความจุสูง (> 70 – 100%)",
             f"{good:,} เที่ยว", f"{pct_of(good):.1f}% · ช่วงที่คุ้มค่าที่สุด"),
            (GROUP_COLORS[ORDER[4]], "⚠️", "เที่ยวที่เกินความจุ (> 100%)",
             f"{over:,} เที่ยว", f"{pct_of(over):.1f}% · ควรตรวจสอบข้อมูล/การปฏิบัติงาน"),
        ]
        st.markdown(
            '<div class="lfx-ins-grid">' + "".join(
                f'<div class="lfx-ins"><div class="lfx-ins-title">'
                f'<span class="lfx-ins-icon" style="background:{_tint(c)}">{icon}</span>{esc(title)}</div>'
                f'<div class="lfx-ins-metric" style="color:{INS_TEXT.get(c, TEXT)}">'
                f'{esc(value)}</div><div class="lfx-ins-sub">{esc(sub)}</div></div>'
                for c, icon, title, value, sub in ins
            ) + "</div>",
            unsafe_allow_html=True,
        )

    # ---------------- การกระจาย + สัดส่วน ----------------
    a, b = st.columns([1.35, 1], gap="medium")
    with a:
        with _card("dist"):
            st.markdown(f"#### การกระจายของอัตราการใช้ความจุ ({metric})")
            st.caption("จำนวนเที่ยวในแต่ละช่วง (รายเที่ยว)")
            fig = go.Figure(go.Bar(
                x=dist["_LFGroup"], y=dist["Trips"],
                marker_color=[GROUP_COLORS[g] for g in dist["_LFGroup"]],
                text=[f"{int(n):,}<br>({p:.1f}%)" for n, p in zip(dist["Trips"], dist["Pct"])],
                textposition="outside", cliponaxis=False,
                textfont=dict(color="#334155", size=12),
                customdata=[STATUS_MAP[g] for g in dist["_LFGroup"]],
                hovertemplate="%{x} · %{customdata}<br>%{y:,} เที่ยว<extra></extra>",
            ))
            y_max = float(dist["Trips"].max() or 1)
            fig.update_layout(
                height=360, margin=dict(l=10, r=10, t=30, b=30), showlegend=False, bargap=0.35,
                xaxis=dict(title=f"อัตราการใช้ความจุ ({metric})"),
                yaxis=dict(title="จำนวนเที่ยว", tickformat=",", range=[0, y_max * 1.25]),
            )
            _style(fig)
            st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)

    with b:
        with _card("share"):
            st.markdown(f"#### สัดส่วนกลุ่มการใช้งาน ({metric})")
            p1, p2 = st.columns([1, 1.25], gap="small")
            with p1:
                fig = go.Figure(go.Pie(
                    labels=[STATUS_MAP[g] for g in dist["_LFGroup"]], values=dist["Trips"],
                    hole=0.64, sort=False, direction="clockwise",
                    marker=dict(colors=[GROUP_COLORS[g] for g in dist["_LFGroup"]],
                                line=dict(color="white", width=3)),
                    text=[f"{p:.0f}%" if p >= 6 else "" for p in dist["Pct"]],
                    textinfo="text", textposition="inside",
                    insidetextfont=dict(color="#3F2A2E", size=12, family=FONT),
                    hovertemplate="%{label}<br>%{value:,} เที่ยว<br>%{percent}<extra></extra>",
                ))
                fig.update_layout(
                    height=280, showlegend=False, margin=dict(l=0, r=0, t=10, b=0),
                    annotations=[dict(
                        text=f"<span style='font-size:12px;color:{MUTED}'>เที่ยวทั้งหมด</span>"
                             f"<br><b style='font-size:19px;color:{TEXT}'>{total:,}</b>",
                        x=0.5, y=0.5, showarrow=False,
                    )],
                )
                _style(fig)
                st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
            with p2:
                rows = "".join(
                    f'<div class="lfx-leg-row"><span class="lfx-sw" style="background:{GROUP_COLORS[g]}"></span>'
                    f'<span class="lfx-leg-name">{esc(STATUS_MAP[g])}<small>{esc(g)} · {esc(MEANING[g])}</small></span>'
                    f'<span class="lfx-leg-val">{int(n):,}</span>'
                    f'<span class="lfx-leg-pct">{p:.1f}%</span></div>'
                    for g, n, p in zip(dist["_LFGroup"], dist["Trips"], dist["Pct"])
                )
                st.markdown(f'<div class="lfx-legend">{rows}</div>', unsafe_allow_html=True)

    # ---------------- ตารางชนิดรถ / เส้นทาง ----------------
    def level_card(name, title, by, label, key_base, caption):
        with _card(name):
            st.markdown(f"#### {title}")
            options = ["ทั้งหมด"] + sorted(filtered[by].dropna().astype(str).unique().tolist())
            pick = st.selectbox(f"ตัวกรอง{label}", options, index=0, key=_wkey(key_base, options))
            t = _level_table(filtered, by, label, top_rank=True)
            if pick != "ทั้งหมด":
                t = t[t[by].astype(str).eq(str(pick))]
            else:
                t = t.head(10)
            body = []
            for r in t.to_dict("records"):
                body.append(
                    "<tr>"
                    f'<td class="lfx-rank">{int(r["_Rank"])}</td>'
                    f'<td>{esc(str(r[by]) or "ไม่ระบุ")}</td>'
                    f'<td class="lfx-num">{int(r["Trip Key Unique"]):,}</td>'
                    + _lf_cell(r["LF_W"]) + _lf_cell(r["LF_V"])
                    + "</tr>"
                )
            st.markdown(
                _table_html(["#", label, "จำนวนเที่ยว", "LF น้ำหนัก", "LF ปริมาตร"], body,
                            right_cols={2, 3, 4}, max_height=400),
                unsafe_allow_html=True,
            )
            st.caption(caption)

    d1, d2 = st.columns(2, gap="medium")
    with d1:
        level_card(
            "vehicle", "10 อันดับ ชนิดรถ (เรียงตามจำนวนเที่ยว)", "Trip Vehicle Model", "ชนิดรถ",
            "lf3_vehicle_filter",
            "LF = ผลรวม ÷ ผลรวมความจุ (ไม่ใช่ค่าเฉลี่ยรายเที่ยว) · เลือกชนิดรถเพื่อดูเฉพาะคัน",
        )
    with d2:
        level_card(
            "route", "10 อันดับ เส้นทาง (เรียงตามจำนวนเที่ยว)", "Route Key", "เส้นทาง",
            "lf3_route_filter",
            "ROUTE LEVEL: ใช้ Route Key (↔) · จำนวนเที่ยว = COUNT UNIQUE(Trip Key Unique)",
        )

    # ---------------- สรุปตามเส้นทาง (Loading ↔ Unloading) ----------------
    status_color = {v: GROUP_COLORS[k] for k, v in STATUS_MAP.items()}
    status_color["Check/Outlier"] = OUTLIER_COLOR

    def badge(text):
        color = status_color.get(text, "#CBD5E1")
        return (f'<span class="lfx-badge" style="background:{_tint(color, 0.7)};color:#3F2A2E">'
                f'{esc(text)}</span>')

    route_total = filtered.groupby("_LFRoute")["Trip Key Unique"].nunique()
    lf_key = "LF_W" if metric == "น้ำหนัก" else "LF_V"

    with _card("trips"):
        st.markdown("#### สรุปตามเส้นทาง (เลือกกลุ่มเพื่อดูรายละเอียด)")
        st.caption(
            "เส้นทางจาก Loading ↔ Unloading (วิ่งสลับทิศนับเป็นเส้นทางเดียวกัน) · "
            f"แบ่งกลุ่มเที่ยวตาม{metric} · LF ของเส้นทาง = ผลรวม ÷ ผลรวมความจุ"
        )
        tab_labels = [f"ทั้งหมด ({total:,})"] + [
            f"{STATUS_MAP[g]} ({by_group.get(g, 0):,})" for g in ORDER
        ]
        tabs = st.tabs(tab_labels)
        for tab, grp in zip(tabs, [None] + ORDER):
            with tab:
                x = filtered if grp is None else filtered[filtered["_LFGroup"] == grp]
                if x.empty:
                    st.info("ไม่มีเที่ยวในกลุ่มนี้")
                    continue
                rs = (
                    x.groupby("_LFRoute")
                    .agg({
                        "Trip Key Unique": "nunique",
                        "_Weight": "sum", "_Capacity": "sum",
                        "_VolumeAgg": "sum", "_VolumeCapacityAgg": "sum",
                    })
                    .reset_index()
                    .rename(columns={"Trip Key Unique": "Trips"})
                )
                rs["LF_W"] = rs["_Weight"].div(rs["_Capacity"].replace(0, pd.NA))
                rs["LF_V"] = rs["_VolumeAgg"].div(rs["_VolumeCapacityAgg"].replace(0, pd.NA))
                rs["Share"] = rs["Trips"] / rs["_LFRoute"].map(route_total) * 100
                rs = rs.sort_values("Trips", ascending=False).reset_index(drop=True)
                outlier_routes = set(x.loc[x["_VolumeOutlier"], "_LFRoute"])

                dir_counts = (
                    x.groupby(["_LFRoute", "_LFDir"])["Trip Key Unique"].nunique()
                    .reset_index(name="n").sort_values("n", ascending=False)
                )
                def dirs_block(g):
                    """ทิศทางวิ่ง: แถบสัดส่วน + บรรทัดละทิศทาง (สีเข้ม = ทิศที่วิ่งบ่อยกว่า)"""
                    total_n = float(g["n"].sum()) or 1.0
                    colors = [DIR_COLORS[min(k, len(DIR_COLORS) - 1)] for k in range(len(g))]
                    bar = "".join(
                        f'<span style="width:{n / total_n * 100:.1f}%;background:{c}"></span>'
                        for n, c in zip(g["n"], colors)
                    )
                    lines = "".join(
                        f'<div class="lfx-dir"><span class="lfx-dir-sw" style="background:{c}"></span>'
                        f'<span class="lfx-dir-name">{esc(str(d)).replace(" → ", ARROW)}</span>'
                        f'<b>{int(n):,}</b><small>{n / total_n * 100:.0f}%</small></div>'
                        for d, n, c in zip(g["_LFDir"], g["n"], colors)
                    )
                    return f'<div class="lfx-dirs"><div class="lfx-split">{bar}</div>{lines}</div>'

                dir_text = {r: dirs_block(g) for r, g in dir_counts.groupby("_LFRoute")}

                head = ["#", "เส้นทาง", "จำนวนเที่ยว"]
                if grp is not None:
                    head.append("% ของเที่ยวในเส้นทาง")
                head += ["ทิศทางการวิ่ง", "LF น้ำหนัก", "LF ปริมาตร", "สถานะเส้นทาง"]
                body = []
                for i, r in enumerate(rs.head(300).to_dict("records"), 1):
                    lf_v = r[lf_key]
                    if pd.notna(lf_v):
                        status = STATUS_MAP.get(_group(lf_v), "ไม่ระบุ")
                    elif metric == "ปริมาตร" and r["_LFRoute"] in outlier_routes:
                        status = "Check/Outlier"   # มีแต่เที่ยว Volume LF > 150% จึงไม่มี LF รวม
                    else:
                        status = "ไม่ระบุ"
                    cells = [
                        f'<td class="lfx-rank">{i}</td>',
                        f'<td><b>{esc(r["_LFRoute"])}</b></td>',
                        f'<td class="lfx-num">{int(r["Trips"]):,}</td>',
                    ]
                    if grp is not None:
                        cells.append(f'<td class="lfx-num lfx-muted">{r["Share"]:.1f}%</td>')
                    cells.append(f'<td class="lfx-dirs-cell">{dir_text.get(r["_LFRoute"], "")}</td>')
                    cells += [_lf_cell(r["LF_W"]), _lf_cell(r["LF_V"]), f"<td>{badge(status)}</td>"]
                    body.append("<tr>" + "".join(cells) + "</tr>")
                n_num = 4 if grp is not None else 3
                right = {2, n_num + 1, n_num + 2} | ({3} if grp is not None else set())
                st.markdown(_table_html(head, body, right_cols=right, max_height=420),
                            unsafe_allow_html=True)

                export = pd.DataFrame({
                    "เส้นทาง": rs["_LFRoute"],
                    "จำนวนเที่ยว": rs["Trips"],
                    **({"% ของเที่ยวในเส้นทาง": rs["Share"].round(1)} if grp is not None else {}),
                    "LF น้ำหนัก (%)": (rs["LF_W"].astype("float64") * 100).round(2),
                    "LF ปริมาตร (%)": (rs["LF_V"].astype("float64") * 100).round(2),
                })
                st.download_button(
                    f"⬇️ ดาวน์โหลด {len(rs):,} เส้นทาง (CSV)",
                    export.to_csv(index=False).encode("utf-8-sig"),
                    file_name="load_factor_routes.csv", mime="text/csv",
                    key=f"lf3_dl_route_{grp or 'all'}",
                )

        # ---------- ดูรายเที่ยวของเส้นทางที่เลือก ----------
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        route_opts = route_total.sort_values(ascending=False).index.tolist()
        r1, r2 = st.columns([2, 1])
        with r1:
            pick_route = st.selectbox(
                "ดูรายเที่ยวของเส้นทาง", ["— เลือกเส้นทาง —"] + route_opts,
                key=_wkey("lf3_trip_route", route_opts),
            )
        if pick_route != "— เลือกเส้นทาง —":
            x = filtered[filtered["_LFRoute"] == pick_route]
            dir_opts = x["_LFDir"].value_counts().index.tolist()
            with r2:
                pick_dir = st.selectbox("ทิศทางวิ่ง", ["ทั้งหมด"] + dir_opts,
                                        key=_wkey("lf3_trip_dir", dir_opts))
            if pick_dir != "ทั้งหมด":
                x = x[x["_LFDir"] == pick_dir]
            show = x.head(200)
            # สถานะตามน้ำหนัก (เหมือนเดิม) แต่ Volume LF > 150% จะเป็น Check/Outlier เสมอ
            status = show["_WeightLF"].map(
                lambda v: STATUS_MAP.get(_group(v), "ไม่ระบุ") if pd.notna(v) else "ไม่ระบุ"
            )
            status = status.where(~show["_VolumeStatus"].eq("Check/Outlier"), "Check/Outlier")
            body = []
            for (_, r), s in zip(show.iterrows(), status):
                date_txt = r["_TripDate"].strftime("%d/%m/%Y") if pd.notna(r["_TripDate"]) else "—"
                direction = esc(str(r["_LFDir"])).replace(" → ", ' <span class="lfx-arrow">→</span> ')
                body.append(
                    "<tr>"
                    f'<td class="lfx-muted">{date_txt}</td>'
                    f"<td>{direction}</td>"
                    f'<td class="lfx-muted">{esc(str(r["Trip Vehicle Model"]))}</td>'
                    + _lf_cell(r["_WeightLF"]) + _lf_cell(r["_VolumeLF"])
                    + f"<td>{badge(s)}</td></tr>"
                )
            st.caption(f"{len(x):,} เที่ยว · แสดงสูงสุด 200 เที่ยว")
            st.markdown(
                _table_html(
                    ["วันที่", "ทิศทางการวิ่ง", "ชนิดรถ",
                     "อัตราการใช้ความจุ (น้ำหนัก)", "อัตราการใช้ความจุ (ปริมาตร)", "สถานะ"],
                    body, right_cols={3, 4}, max_height=380,
                ),
                unsafe_allow_html=True,
            )
            export = pd.DataFrame({
                "วันที่": x["_TripDate"].dt.strftime("%d/%m/%Y"),
                "เส้นทาง": x["_LFRoute"],
                "ทิศทางการวิ่ง": x["_LFDir"],
                "ชนิดรถ": x["Trip Vehicle Model"],
                "LF น้ำหนัก (%)": (x["_WeightLF"].astype("float64") * 100).round(2),
                "LF ปริมาตร (%)": (x["_VolumeLF"].astype("float64") * 100).round(2),
                "สถานะปริมาตร": x["_VolumeStatus"],
            })
            st.download_button(
                f"⬇️ ดาวน์โหลด {len(x):,} เที่ยว (CSV)",
                export.to_csv(index=False).encode("utf-8-sig"),
                file_name="load_factor_trips.csv", mime="text/csv", key="lf3_dl_trips",
            )


    st.markdown(
        '<div class="lfx-note">📌 <b>Volume LF &gt; 150%</b> — เก็บค่าจริงและแถวข้อมูลไว้ทั้งหมดในรายการเที่ยว '
        "โดยไม่ปรับเป็น 100% และไม่ลบแถว แต่จัดเป็น <b>Check/Outlier</b> "
        "และไม่นำเที่ยวดังกล่าวมาคำนวณ Volume LF รวม (ภาพรวม / ชนิดรถ / เส้นทาง)</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="lfx-source">Source (Load Factor only): '
        + esc(" | ".join(source_labels) if source_labels else "ค่าเดินทาง+Revenue3ปี=Loadfactorใหม่.xlsx")
        + "</div>",
        unsafe_allow_html=True,
    )