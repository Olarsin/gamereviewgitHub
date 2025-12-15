import streamlit as st
import pandas as pd
import os
import datetime
import ast
from collections import Counter

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="Game Review Viewer",
    page_icon="🔎",
    layout="wide",
)

# [Connectivity] Initialize Session State for Navigation
if 'nav_cluster_id' not in st.session_state:
    st.session_state['nav_cluster_id'] = None
if 'nav_version' not in st.session_state:
    st.session_state['nav_version'] = None
if 'filter_review_ids' not in st.session_state:
    st.session_state['filter_review_ids'] = None

st.title("🔎 Game Review Analysis Viewer")
st.markdown("자동화 파이프라인(`pipeline_v2.py`)이 생성한 분석 결과를 날짜별로 조회합니다.")
st.markdown("---")

# =========================================================
# 1. Sidebar: Data Selection
# =========================================================
BASE_DIR = "data"

if not os.path.exists(BASE_DIR):
    st.error(f"데이터 폴더('{BASE_DIR}')가 없습니다. 먼저 pipeline_v2.py를 실행하세요.")
    st.stop()

# Find subdirectories (dates)
subdirs = [d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))]
subdirs.sort(reverse=True)  # Newest first

if not subdirs:
    st.warning("분석 결과가 없습니다. `python pipeline_v2.py`를 실행하여 데이터를 생성하세요.")
    st.stop()

selected_date = st.sidebar.selectbox("📅 분석 날짜 선택", subdirs, index=0)
selected_path = os.path.join(BASE_DIR, selected_date)

st.sidebar.markdown("---")
st.sidebar.info(f"선택된 경로:\n`{selected_path}`")

# =========================================================
# 2. Data Loading Logic
# =========================================================
@st.cache_data(show_spinner="데이터 로딩 중...")
def load_data(folder_path):
    data = {}
    
    # 1. Analyzed Data (Main)
    refined_path = os.path.join(folder_path, "analyzed_refined.csv")
    clustered_path = os.path.join(folder_path, "clustered.csv")
    analyzed_path = os.path.join(folder_path, "analyzed.csv")
    
    # Use refined > clustered > analyzed
    main_df = None
    if os.path.exists(refined_path):
        main_df = pd.read_csv(refined_path)
    elif os.path.exists(clustered_path):
        main_df = pd.read_csv(clustered_path)
    elif os.path.exists(analyzed_path):
        main_df = pd.read_csv(analyzed_path)
    
    if main_df is not None:
        # Essential preprocessing for UI
        if "at" in main_df.columns:
            main_df["at"] = pd.to_datetime(main_df["at"], errors="coerce")
        if "content_clean" in main_df.columns and "content" not in main_df.columns:
             main_df["content"] = main_df["content_clean"] # UI expects 'content'
        
        # Ensure cluster column exists
        if "cluster" not in main_df.columns:
            main_df["cluster"] = "-1"
        
        # Determine cluster ID type (ensure consistency)
        main_df["cluster"] = main_df["cluster"].astype(str)
            
        data["dataframe"] = main_df

        # Generate cluster info (keywords) for visualization
        cluster_info = {}
        if "keywords" in main_df.columns:
            for cid in main_df["cluster"].unique():
                if cid == "-1": continue
                kws = []
                # Sample up to 50 rows for speed
                sample = main_df[main_df["cluster"] == cid].head(50)
                for k_str in sample["keywords"].dropna():
                    try:
                        actual_list = ast.literal_eval(k_str)
                        if isinstance(actual_list, list):
                            kws.extend(actual_list)
                        else:
                            kws.append(str(k_str))
                    except:
                        kws.append(str(k_str))
                
                # Top 10 keywords
                cluster_info[cid] = [k for k, v in Counter(kws).most_common(10)]
        data["cluster_info"] = cluster_info



    # 1.5 Keyword Analysis Report
    kw_path = os.path.join(folder_path, "keyword_analysis.csv")
    if os.path.exists(kw_path):
        data["keyword_df"] = pd.read_csv(kw_path)

    # 2. Reports (Dual Track)
    # Diagnosis
    diag_path = os.path.join(folder_path, "diagnosis_report.csv")
    if os.path.exists(diag_path):
        data["diagnosis_df"] = pd.read_csv(diag_path)

    # Growth
    growth_path = os.path.join(folder_path, "growth_strategy_report_growth.csv")
    if os.path.exists(growth_path):
        data["growth_df"] = pd.read_csv(growth_path)

    # Action Items (Markdown)
    action_path = os.path.join(folder_path, "action_items.md")
    if os.path.exists(action_path):
        with open(action_path, "r", encoding="utf-8") as f:
            data["action_items"] = f.read()

    # 3. Version Trend Data
    trend_path = os.path.join(folder_path, "version_trend.csv")
    if os.path.exists(trend_path):
         data["trend_df"] = pd.read_csv(trend_path)

    return data

# =========================================================
# 3. Main Execution
# =========================================================

# Load data when date changes
if "current_date" not in st.session_state or st.session_state["current_date"] != selected_date:
    loaded = load_data(selected_path)
    
    if "dataframe" in loaded:
        df = loaded["dataframe"]
        st.session_state["raw_df"] = df
        st.session_state["clean_df"] = df
        st.session_state["cluster_df"] = df  # Unified
        st.session_state["cluster_info"] = loaded.get("cluster_info", {})
        st.session_state["action_items"] = loaded.get("action_items", None)
        st.session_state["action_items"] = loaded.get("action_items", None)
        st.session_state["trend_df"] = loaded.get("trend_df", None)
        st.session_state["keyword_df"] = loaded.get("keyword_df", None) # New
        
        # Dual Track Reports
        if "diagnosis_df" in loaded:
            st.session_state["diagnosis_df"] = loaded["diagnosis_df"]
        else:
            st.session_state["diagnosis_df"] = None

        if "growth_df" in loaded:
            st.session_state["growth_df"] = loaded["growth_df"]
        else:
            st.session_state["growth_df"] = None
        
        st.session_state["current_date"] = selected_date
        
        # NOTE: Legacy Markdown generation removed in favor of using DataFrames directly in pages.
             
        st.success(f"✅ {selected_date} 데이터 로드 완료! ({len(df)}건)")
    else:
        st.error("데이터 파일(analyzed.csv 또는 clustered.csv)을 찾을 수 없습니다.")

# =========================================================
# 4. Display Summary
# =========================================================
if "clean_df" in st.session_state:
    df = st.session_state["clean_df"]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("총 리뷰 수", f"{len(df):,}")
    col2.metric("평균 평점", f"{df['score'].mean():.2f}")
    
    # Summary Dashboard
    st.markdown("### 📊 분석 요약")
    
    d_df = st.session_state.get("diagnosis_df")
    g_df = st.session_state.get("growth_df")
    
    tab1, tab2 = st.tabs(["🔥 긴급 이슈 (Defect)", "🚀 성장 기회 (Growth)"])
    
    with tab1:
        if d_df is not None and not d_df.empty:
            for idx, row in d_df.head(3).iterrows():
                with st.expander(f"{row['issue_title']} (Score: {row.get('urgency_score', 0)})"):
                    st.write(f"**진단**: {row['diagnosis_summary']}")
                    st.write(f"**해결**: {row['technical_recommendation']}")
        else:
            st.info("발견된 주요 이슈가 없습니다.")
            
    with tab2:
        if g_df is not None and not g_df.empty:
            for idx, row in g_df.head(3).iterrows():
                with st.expander(f"{row['core_appeal']} (Potential: {row.get('potential_score', 0)})"):
                    st.write(f"**전략**: {row['growth_strategy']}")
        else:
            st.info("성장 기회 리포트가 없습니다.")
else:
    st.info("좌측 사이드바에서 날짜를 선택해주세요.")
