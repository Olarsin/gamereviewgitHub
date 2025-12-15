import streamlit as st
import pandas as pd
import os
import ast
import plotly.express as px

# page configuration
st.set_page_config(page_title="Review Explorer", page_icon="🔍", layout="wide")

# ========================================================
# 1. DATA LOADING (Robust & Independent)
# ========================================================
@st.cache_data(ttl=600)
def load_data():
    # Find latest folder dynamically
    base_dir = "data"
    paths = []
    if os.path.exists(base_dir):
        subdirs = [os.path.join(base_dir, d) for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
        subdirs.sort(reverse=True)
        if subdirs:
            latest = subdirs[0]
            # Prioritize analyzed_refined.csv
            paths = [
                os.path.join(latest, "analyzed_refined.csv"),
                os.path.join(latest, "clustered.csv"),
                os.path.join(latest, "analyzed.csv"),
                os.path.join(latest, "preprocessed.csv")
            ]

    for p in paths:
        if os.path.exists(p):
            try:
                df = pd.read_csv(p)
                # Date conversion
                if "at" in df.columns:
                    df["at"] = pd.to_datetime(df["at"], errors="coerce")
                    df = df.dropna(subset=["at"])
                
                # Numeric safe conversion
                for col in ["score", "thumbsUpCount", "intensity"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                        
                # List parsing
                for col in ["keywords", "categories", "appeal_points"]:
                    if col in df.columns:
                        df[col] = df[col].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) and x.startswith("[") else [])
                
                return df
            except Exception as e:
                pass
                
    return pd.DataFrame()

df = load_data()

if df.empty:
    st.error("데이터를 찾을 수 없습니다. 분석 파이프라인(pipeline_v2.py)을 먼저 실행해주세요.")
    st.stop()

# ========================================================
# 2. CONTEXT AWARENESS & SIDEBAR FILTERS
# ========================================================
# [Connectivity] Check Session State Filters
nav_version = st.session_state.get('nav_version', None)
nav_ids = st.session_state.get('filter_review_ids', None)

if nav_version or nav_ids:
    st.info(f"🔗 Context Active: Version='{nav_version}' | IDs={len(nav_ids) if nav_ids else 0}")
    if st.button("🔄 Reset Context"):
        st.session_state['nav_version'] = None
        st.session_state['filter_review_ids'] = None
        st.rerun()

st.sidebar.title("🔍 검색 설정")

# A. Primary Filters (Always Visible)
st.sidebar.caption("🗓️ 기본 설정")
min_date = df["at"].min().date()
max_date = df["at"].max().date()
date_range = st.sidebar.date_input("기간", value=(min_date, max_date), min_value=min_date, max_value=max_date)

version_col = next((c for c in ["reviewCreatedVersion", "appVersion", "version"] if c in df.columns), None)
sel_versions = []
if version_col:
    all_versions = sorted(df[version_col].dropna().unique().astype(str), reverse=True)
    # If nav_version is set, default to it
    default_vers = [str(nav_version)] if nav_version and str(nav_version) in all_versions else []
    sel_versions = st.sidebar.multiselect("버전 (비워두면 전체)", all_versions, default=default_vers)

sel_scores = st.sidebar.multiselect("평점", [1, 2, 3, 4, 5], default=[1, 2, 3, 4, 5])

# B. Advanced Filters (Collapsible)
st.sidebar.markdown("---")
with st.sidebar.expander("🛠️ 상세 필터 (토픽/위험도/검색)", expanded=False):
    # Topic/Cluster Filter
    cat_col = next((c for c in ["refined_topic", "cluster_label", "topic", "categories"] if c in df.columns), None)
    sel_cats = []
    if cat_col:
        # If list, explode needed? Or just simplistic unique
        if df[cat_col].apply(lambda x: isinstance(x, list)).any():
             all_cats = sorted(set([x for sublist in df[cat_col] if isinstance(sublist, list) for x in sublist]))
        else:
             all_cats = sorted(df[cat_col].astype(str).unique())
        
        sel_cats = st.multiselect("📂 토픽/클러스터", all_cats, default=[])

    # Risk Status
    sel_risk = []
    if "risk_status" in df.columns:
        risks = df["risk_status"].dropna().unique().tolist()
        if risks:
            sel_risk = st.multiselect("🚨 이탈 위험도", risks, default=[])

    # Intensity
    int_range = (1, 5)
    if "intensity" in df.columns:
        int_range = st.slider("🔥 감정 강도 (Intensity)", 1, 5, (1, 5))

    # Keyword Search
    keyword_q = st.text_input("💬 내용 검색", placeholder="예: 렉, 결제...")

# ========================================================
# 3. FILTERING LOGIC
# ========================================================
# [Connectivity] ID Filter First (Strongest)
mask = pd.Series(True, index=df.index)

if nav_ids:
    # Filter by Index (Assuming review_ids are indices)
    mask &= df.index.isin(nav_ids)

# Date
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_d, end_d = date_range
    mask &= (df["at"].dt.date >= start_d) & (df["at"].dt.date <= end_d)

# Version
if version_col and sel_versions:
    mask &= df[version_col].astype(str).isin(sel_versions)

# Score
mask &= df["score"].isin(sel_scores)

# Category
if cat_col and sel_cats:
    if df[cat_col].apply(lambda x: isinstance(x, list)).any():
        mask &= df[cat_col].apply(lambda x: any(item in sel_cats for item in x) if isinstance(x, list) else str(x) in sel_cats)
    else:
        mask &= df[cat_col].isin(sel_cats)

# Risk
if "risk_status" in df.columns and sel_risk:
    mask &= df["risk_status"].isin(sel_risk)

# Intensity
if "intensity" in df.columns:
    mask &= (df["intensity"] >= int_range[0]) & (df["intensity"] <= int_range[1])

# Keyword
if keyword_q:
    mask &= (
        df["content"].astype(str).str.contains(keyword_q, case=False) | 
        df["issue_summary"].astype(str).str.contains(keyword_q, case=False)
    )

filtered_df = df[mask].copy().sort_values("at", ascending=False)

# ========================================================
# 4. MAIN UI: CHARTS & STATS
# ========================================================
st.title("🔎 Review Explorer")
# st.caption("필터링된 리뷰 데이터를 정밀하게 탐색하고 분석 결과를 확인합니다.")

# KPI Rows
c1, c2, c3, c4 = st.columns(4)
c1.metric("검색된 리뷰", f"{len(filtered_df):,}건")
c2.metric("평균 평점", f"{filtered_df['score'].mean():.2f}")

risk_cnt = 0
if "risk_status" in filtered_df.columns:
    risk_cnt = len(filtered_df[filtered_df["risk_status"].isin(["이탈위험", "이탈확정", "불만"])])
c3.metric("리스크 리뷰", f"{risk_cnt}건", delta="Risk" if risk_cnt > 0 else None, delta_color="inverse")

if "sentiment" in filtered_df.columns:
    pos_ratio = (filtered_df["sentiment"] == "긍정").mean() * 100
    c4.metric("긍정 비율", f"{pos_ratio:.1f}%")

st.markdown("---")

# Charts Section (3 Columns now)
chart_c1, chart_c2, chart_c3 = st.columns(3)

# 1. Score Distribution
with chart_c1:
    st.subheader("⭐ 별점 분포")
    if not filtered_df.empty:
        score_counts = filtered_df["score"].value_counts().sort_index()
        fig_score = px.bar(x=score_counts.index, y=score_counts.values, labels={'x': '별점', 'y': '리뷰 수'}, 
                           template="plotly_white", color_discrete_sequence=['#FFC107'])
        fig_score.update_layout(height=250, margin=dict(l=20, r=20, t=10, b=20))
        st.plotly_chart(fig_score, use_container_width=True)

# 2. Intensity Distribution (NEW)
with chart_c2:
    st.subheader("🔥 감정 강도 분포")
    if not filtered_df.empty and "intensity" in filtered_df.columns:
        int_counts = filtered_df["intensity"].value_counts().sort_index()
        fig_int = px.bar(x=int_counts.index, y=int_counts.values, labels={'x': '감정 강도 (1-5)', 'y': '리뷰 수'},
                         template="plotly_white", color=int_counts.index, color_continuous_scale='Reds')
        fig_int.update_layout(height=250, margin=dict(l=20, r=20, t=10, b=20), showlegend=False)
        st.plotly_chart(fig_int, use_container_width=True)
    else:
        st.info("감정 강도 데이터가 없습니다.")

# 3. Topic Distribution
with chart_c3:
    st.subheader("📂 토픽 분포")
    if not filtered_df.empty and cat_col:
        # Handle list expansion for counting
        if filtered_df[cat_col].apply(lambda x: isinstance(x, list)).any():
            cats_exploded = filtered_df.explode(cat_col)[cat_col].value_counts().head(10)
        else:
            cats_exploded = filtered_df[cat_col].value_counts().head(10)
            
        fig_cat = px.bar(
            x=cats_exploded.values, y=cats_exploded.index, orientation='h',
            labels={'x': '리뷰 수', 'y': '토픽'}, color=cats_exploded.values,
            color_continuous_scale='Viridis', template="plotly_white"
        )
        fig_cat.update_layout(yaxis={'categoryorder':'total ascending'}, height=250, margin=dict(l=20, r=20, t=10, b=20))
        st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("토픽 데이터가 없습니다.")

st.markdown("---")

# ========================================================
# 5. GRID & DETAIL
# ========================================================
# Prepare display columns
cols_to_show = ["reviewId", "at", "score", "content"]
if "issue_summary" in df.columns: cols_to_show.insert(3, "issue_summary")
if "sentiment" in df.columns: cols_to_show.insert(3, "sentiment")
if "risk_status" in df.columns: cols_to_show.insert(4, "risk_status")
if "intensity" in df.columns: cols_to_show.insert(5, "intensity")
if cat_col: cols_to_show.insert(3, cat_col)
if version_col: cols_to_show.insert(2, version_col)

# Configure Column Config for better visuals
col_config = {
    "at": st.column_config.DateColumn("날짜", format="YYYY-MM-DD"),
    "score": st.column_config.NumberColumn("⭐", format="%d"),
    "intensity": st.column_config.NumberColumn("🔥", format="%d"),
    "content": st.column_config.TextColumn("리뷰 내용", width="large"),
    "issue_summary": st.column_config.TextColumn("이슈 요약", width="medium"),
    "risk_status": st.column_config.TextColumn("위험도", help="일반/불만/이탈위험"),
    "sentiment": st.column_config.TextColumn("감정"),
}

col_config_display = {k: v for k, v in col_config.items() if k in cols_to_show}

# Interactive Dataframe
selection = st.dataframe(
    filtered_df[cols_to_show],
    column_config=col_config_display,
    use_container_width=True,
    height=400,
    hide_index=True,
    on_select="rerun", # Enables selection!
    selection_mode="single-row"
)

# Detail View
if selection.selection["rows"]:
    idx = selection.selection["rows"][0]
    try:
        row = filtered_df.iloc[idx]
        
        st.markdown("---")
        st.subheader("📑 리뷰 상세 분석")
        
        # Header Info
        hc1, hc2, hc3, hc4 = st.columns(4)
        hc1.info(f"**작성일**: {row['at'].strftime('%Y-%m-%d')}")
        hc2.info(f"**평점**: {'⭐' * int(row['score'])}")
        hc3.info(f"**감정**: {row.get('sentiment', 'N/A')}")
        hc4.info(f"**버전**: {row.get(version_col, 'N/A')}")
        
        # Content Box
        st.markdown("#### 🗣️ 리뷰 원문")
        st.code(row["content"], language="text")
        
        # Analysis Cards
        ac1, ac2 = st.columns(2)
        
        with ac1:
            st.markdown("#### 🕵️ 시스템 진단 (Defect/Risk)")
            if pd.notna(row.get("issue_summary")):
                st.write(f"**요약**: {row['issue_summary']}")
            if pd.notna(row.get("risk_status")):
                color = "red" if row["risk_status"] in ["이탈위험", "이탈확정"] else "orange" if row["risk_status"] == "불만" else "green"
                st.markdown(f"**상태**: :{color}[{row['risk_status']}]")
            if pd.notna(row.get("categories")):
                st.write(f"**카테고리**: {row['categories']}")
            if pd.notna(row.get("keywords")):
                st.write(f"**키워드**: {row['keywords']}")
            if pd.notna(row.get("intensity")):
                 st.write(f"**감정 강도**: {row['intensity']}/5")
                
        with ac2:
            st.markdown("#### ✨ 기회 요인 (Opportunity)")
            if pd.notna(row.get("viral_hook")):
                st.write(f"**바이럴 훅**: {row['viral_hook']}")
            if pd.notna(row.get("retention_hook")):
                st.write(f"**지속 플레이 동기**: {row['retention_hook']}")
            if pd.notna(row.get("labels")): # If legacy labels exist
                st.write(f"**라벨**: {row['labels']}")

    except Exception as e:
        st.error(f"상세 보기를 로드하는 중 오류가 발생했습니다: {e}")
        
else:
    st.info("👆 위 목록에서 리뷰를 클릭하면 상세 분석 내용을 볼 수 있습니다.")

st.markdown("---")
