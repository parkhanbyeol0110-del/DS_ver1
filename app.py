import io
from datetime import datetime

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="월별 매출 대시보드", layout="wide")

# -------------- 유틸 --------------
def fmt_money(x: float | int) -> str:
    try:
        return f"{int(x):,}"
    except Exception:
        return str(x)

def fmt_pct(x: float) -> str:
    s = f"{x:.1f}%"
    return f"+{s}" if x > 0 else s

def compute_cum(values):
    out = []
    s = 0
    for v in values:
        s += v
        out.append(s)
    return out

def parse_dataframe(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    기대 컬럼: 월(YYYY-MM), 매출액, 전년동월, 증감률
    숫자에 콤마가 있어도 처리
    """
    df = df_raw.copy()
    # 컬럼 존재 확인
    need_cols = ["월", "매출액", "전년동월", "증감률"]
    missing = [c for c in need_cols if c not in df.columns]
    if missing:
        raise ValueError(f"필수 컬럼 누락: {', '.join(missing)}")

    # 공백/콤마 제거 후 숫자로
    for c in ["매출액", "전년동월", "증감률"]:
        df[c] = (
            df[c]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace(" ", "", regex=False)
        )
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # 월 형식 정규화 YYYY-MM
    df["월"] = df["월"].astype(str).str.strip()
    if not df["월"].str.match(r"^\d{4}-\d{2}$").all():
        bad = df.loc[~df["월"].str.match(r"^\d{4}-\d{2}$"), "월"].head(3).tolist()
        raise ValueError(f"월 형식(YYYY-MM) 오류 예: {bad}")

    # 정렬
    df = df.sort_values("월").reset_index(drop=True)

    # 누적
    df["누적매출"] = compute_cum(df["매출액"].tolist())

    # 월번호/라벨
    df["월번호"] = df["월"].str[-2:].astype(int)
    return df

# -------------- 샘플 데이터 (업로드 없을 때) --------------
SAMPLE = pd.DataFrame({
    "월": ["2024-01","2024-02","2024-03","2024-04","2024-05"],
    "매출액": [12000000,13500000,11000000,18000000,21000000],
    "전년동월": [10500000,11200000,12800000,15200000,18500000],
    "증감률": [14.3,20.5,-14.1,18.4,13.5],
})

# -------------- 사이드바 --------------
st.sidebar.title("데이터")
uploaded = st.sidebar.file_uploader("CSV 업로드 (월, 매출액, 전년동월, 증감률)", type=["csv"])
use_sample = st.sidebar.toggle("샘플 데이터 사용", value=uploaded is None)

# -------------- 데이터 로딩 --------------
try:
    if uploaded and not use_sample:
        df_in = pd.read_csv(uploaded)
    else:
        df_in = SAMPLE.copy()

    df = parse_dataframe(df_in)
except Exception as e:
    st.error(f"데이터 해석 오류: {e}")
    st.stop()

# -------------- 헤더 영역 --------------
left, right = st.columns([1, 1], gap="large")
with left:
    st.title("월별 매출 대시보드")
    date_range = f"{df['월'].iloc[0]} ~ {df['월'].iloc[-1]}"
    st.caption(f"기간: {date_range}")

with right:
    # 원본/정제본 다운로드
    st.write("")
    st.write("")
    orig_csv = df_in.to_csv(index=False).encode("utf-8-sig")
    clean_csv = df.to_csv(index=False).encode("utf-8-sig")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "원본 CSV 다운로드",
            data=orig_csv,
            file_name="original.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "정제 CSV 다운로드",
            data=clean_csv,
            file_name="clean.csv",
            mime="text/csv",
            use_container_width=True,
        )

# -------------- KPI --------------
last = df.iloc[-1]
max_idx = int(df["매출액"].idxmax())
min_idx = int(df["매출액"].idxmin())
total = int(df["매출액"].sum())

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.metric(
        "이번 달 매출",
        f"{fmt_money(last['매출액'])} 원",
        help=f"{last['월']} 기준",
    )
with k2:
    st.metric(
        "전년 동월 대비 증가율",
        fmt_pct(last["증감률"]),
    )
with k3:
    st.metric(
        "연간 누적 매출",
        f"{fmt_money(total)} 원",
        help=f"{df['월'].iloc[0]} ~ {df['월'].iloc[-1]}",
    )
with k4:
    st.metric(
        "최고 · 최저 매출 달",
        f"{df.loc[max_idx, '월']} / {df.loc[min_idx, '월']}",
        help=f"최고 {fmt_money(df.loc[max_idx,'매출액'])} · 최저 {fmt_money(df.loc[min_idx,'매출액'])}",
    )

st.divider()

# -------------- 1. 월별 매출 & 전년동월 비교 (라인) --------------
c1, c2 = st.columns(2)
with c1:
    st.subheader("① 월별 매출액 & 전년동월 비교")
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=df["월"], y=df["매출액"], mode="lines+markers", name="매출액"
    ))
    fig1.add_trace(go.Scatter(
        x=df["월"], y=df["전년동월"],
        mode="lines+markers", name="전년동월",
        line=dict(dash="dash")
    ))
    fig1.update_layout(
        hovermode="x unified",
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_tickformat=",",
    )
    st.plotly_chart(fig1, use_container_width=True)

# -------------- 2. 전년 대비 증감률 (막대) --------------
with c2:
    st.subheader("② 전년 대비 증감률")
    colors = ["#ff6b6b" if v < 0 else "#7bd389" for v in df["증감률"]]
    fig2 = go.Figure(data=[go.Bar(
        x=df["월"], y=df["증감률"], marker_color=colors, name="증감률"
    )])
    fig2.add_hline(y=0, line_color="#888", line_width=1)
    fig2.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_ticksuffix="%",
    )
    st.plotly_chart(fig2, use_container_width=True)

# -------------- 3. 최고 · 최저 매출 달 (강조 라인) --------------
c3, c4 = st.columns(2)
with c3:
    st.subheader("③ 최고 · 최저 매출 달")
    marker_sizes = [6] * len(df)
    marker_colors = ["#1f77b4"] * len(df)
    marker_sizes[max_idx] = 12; marker_colors[max_idx] = "#7bd389"  # 최고
    marker_sizes[min_idx] = 12; marker_colors[min_idx] = "#ff6b6b"  # 최저

    fig3 = go.Figure(data=[go.Scatter(
        x=df["월"], y=df["매출액"], mode="lines+markers", name="매출액",
        marker=dict(size=marker_sizes, color=marker_colors)
    )])
    fig3.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_tickformat=",",
    )
    st.plotly_chart(fig3, use_container_width=True)

# -------------- 4. 누적 매출 추세 (에어리어 라인) --------------
with c4:
    st.subheader("④ 누적 매출 추세")
    fig4 = go.Figure(data=[go.Scatter(
        x=df["월"], y=df["누적매출"], mode="lines+markers", fill="tozeroy", name="누적 매출"
    )])
    fig4.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_tickformat=",",
    )
    st.plotly_chart(fig4, use_container_width=True)

# -------------- 5. 월별 평균 증감률 히트맵 --------------
c5, c6 = st.columns(2)
with c5:
    st.subheader("⑤ 월별 평균 증감률 히트맵")
    # 단일 연도 데이터라면 '평균 = 현재값' 개념으로 표시
    months = df["월"].tolist()
    z = [df["증감률"].tolist()]  # 1 x N
    fig5 = go.Figure(data=go.Heatmap(
        z=z,
        x=months,
        y=["증감률"],
        colorscale=[  # 커스텀 diverging
            [0.0, "#ff6b6b"],
            [0.5, "#2a375a"],
            [1.0, "#7bd389"],
        ],
        colorbar=dict(ticksuffix="%", title=""),
        zmid=0,
    ))
    fig5.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(tickangle=-0),
    )
    st.plotly_chart(fig5, use_container_width=True)

# -------------- 6. 데이터 미리보기 (테이블) --------------
with c6:
    st.subheader("⑥ 데이터 미리보기")
    st.dataframe(
        df[["월","매출액","전년동월","증감률","누적매출"]]
        .assign(
            매출액=lambda d: d["매출액"].map(fmt_money),
            전년동월=lambda d: d["전년동월"].map(fmt_money),
            증감률=lambda d: d["증감률"].map(fmt_pct),
            누적매출=lambda d: d["누적매출"].map(fmt_money),
        ),
        use_container_width=True,
        hide_index=True
    )

# -------------- 푸터 --------------
st.caption("CSV 형식: 월(YYYY-MM), 매출액, 전년동월, 증감률  |  예시 데이터 포함")
