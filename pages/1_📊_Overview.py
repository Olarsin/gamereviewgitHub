import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import re
import ast

# ----------------------------------------
# PAGE CONFIG
# ----------------------------------------
st.set_page_config(
    page_title="Overview Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Holistic Review Dashboard")
st.markdown("### 🦅 전체 리뷰 현황 및 인텔리전스 요약")

# ========================================================
# LOAD DATA
# ========================================================
if "cluster_df" in st.session_state:
    df = st.session_state["cluster_df"].copy()
elif "clean_df" in st.session_state:
    df = st.session_state["clean_df"].copy()
else:
    st.error("⚠ 먼저 Main 페이지에서 분석 데이터를 로드해주세요.")
    st.stop()

# Preprocessing
if "at" in df.columns:
    df["at"] = pd.to_datetime(df["at"], errors="coerce")
    df = df.dropna(subset=["at"])

if "score" in df.columns:
    df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0).astype(int)

# Map numeric 1-5 to Sentiment Group (Fallback)
def classify_sentiment_fallback(score):
    if score >= 4: return "Positive"
    elif score == 3: return "Neutral"
    else: return "Negative"

# Robust Semantic Version Parsing
def parse_version(v_str):
    """
    Parses version string into tuple (Major, Minor, Patch).
    Handles '1.2.3', 'v1.2', '1.2.3.4' etc.
    """
    if not isinstance(v_str, str): return (0, 0, 0)
    # Remove non-numeric prefixes/suffixes broadly
    clean_v = re.sub(r'[a-zA-Z_-]', '', v_str)
    # Find all number groups
    nums = [int(n) for n in re.findall(r'\d+', clean_v)]
    
    # Pad to at least 3 digits (Major, Minor, Patch)
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])

# ----------------------------------------
# Robust Parsing Helper
# ----------------------------------------
def robust_eval_list(val):
    if pd.isna(val) or val == "":
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        # Remove whitespace around brackets
        val = val.strip()
        # Handle simple cases or empty brackets
        if val == "[]": return []
        if val.startswith("[") and val.endswith("]"):
            try:
                return ast.literal_eval(val)
            except:
                pass
        # Fallback for comma-separated strings inside or outside brackets
        cleaned = val.replace("[", "").replace("]", "").replace("'", "").replace('"', "")
        return [x.strip() for x in cleaned.split(",") if x.strip()]
    return []

# Sentiment Labeling Logic (Robust)
if "sentiment" in df.columns:
    # Map Korean sentiment to English Label (Handle whitespace)
    def map_sentiment(s):
        s = str(s).strip()
        if s == "긍정": return "Positive"
        if s == "부정": return "Negative"
        return "Neutral"
    
    df["sentiment_label"] = df["sentiment"].apply(map_sentiment)
elif "sentiment_label" not in df.columns:
    df["sentiment_label"] = df["score"].apply(classify_sentiment_fallback)

# Ensure intensity is numeric
if "intensity" in df.columns:
    df["intensity"] = pd.to_numeric(df["intensity"], errors="coerce").fillna(1)
else:
    df["intensity"] = 1

# ========================================================
# 1. KPI CARDS
# ========================================================
# Helper for Numeric Sentiment (0-100)
def get_numeric_sentiment(label):
    if label == "Positive": return 100
    elif label == "Negative": return 0
    return 50

df["sentiment_score_val"] = df["sentiment_label"].apply(get_numeric_sentiment)

with st.container():
    c1, c2, c3 = st.columns(3)
    c1.metric("총 리뷰 수", f"{len(df):,}")
    c2.metric("평균 평점", f"{df['score'].mean():.2f}/5")
    
    # Average Sentiment Score
    avg_senti = df["sentiment_score_val"].mean()
    c3.metric("평균 감정점수", f"{avg_senti:.1f}/100", help="Positive(100), Neutral(50), Negative(0)")

st.markdown("---")

# ========================================================
# 0. CLUSTER IMPACT MATRIX (Issue Grouping)
# ========================================================
st.markdown("---")
st.subheader("0️⃣ 이슈 클러스터 분석 (Cluster Impact Matrix)")
st.caption("개별 키워드가 아닌 **유사한 리뷰 그룹(Cluster)** 단위로 분석하여, 더 큰 흐름을 파악합니다.")

# Use 'df' which implies cluster_df AND has sentiment_label calculated
if "cluster" in df.columns:
    c_df = df.copy()
    
    # Needs 'cluster' column
    # Filter out noise cluster usually labels as '-1' or empty
    c_df = c_df[c_df['cluster'].astype(str) != "-1"]
    
    # 1. Aggregation per Cluster
    # We need: Count, Avg Intensity, Main Sentiment, Representative Keywords
    
    # Helper for mode/top
    def get_top_item(series):
        try:
            vc = series.value_counts()
            if not vc.empty: return vc.index[0]
        except: pass
        return "Unknown"

    base_stats = c_df.groupby("cluster").agg(
        count=("reviewId", "count"),
        avg_intensity=("intensity", "mean"),
        avg_score=("score", "mean"),
        main_sentiment=("sentiment_label", get_top_item),
        main_category=("categories", get_top_item)
    ).reset_index()
    
    # Calculate Impact Score
    base_stats["impact_score"] = base_stats["count"] * base_stats["avg_intensity"]
    
    # Get Keywords
    cluster_kws = st.session_state.get("cluster_info", {})
    def get_cluster_label(cid):
        if cid in cluster_kws:
            return ", ".join(cluster_kws[cid][:3]) 
        return f"Cluster {cid}"
    base_stats["keywords_label"] = base_stats["cluster"].apply(get_cluster_label)

    # --------------------------------------------------------
    # 2. Relative Separation: Ensure we always have Neg/Pos
    # --------------------------------------------------------
    
    # --------------------------------------------------------
    # 2. Assign Group Type (Logic Update for N-/P- prefixes)
    # --------------------------------------------------------
    
    def determine_group_type(row):
        cid = str(row['cluster'])
        if cid.startswith("N-"): return "Negative (Risk)"
        if cid.startswith("P-"): return "Positive (Strength)"
        
        # Fallback: based on score
        if row['avg_score'] <= 3.2: return "Negative (Risk)"
        return "Positive (Strength)"
        
    base_stats["group_type"] = base_stats.apply(determine_group_type, axis=1)
    
    # 3. Take Top 5 Impact from Each Group
    final_neg = base_stats[base_stats["group_type"]=="Negative (Risk)"].sort_values("impact_score", ascending=False).head(5)
    final_pos = base_stats[base_stats["group_type"]=="Positive (Strength)"].sort_values("impact_score", ascending=False).head(5)
    
    # 4. Integrate for Visualization
    cluster_stats = pd.concat([final_neg, final_pos], ignore_index=True)
    
    if cluster_stats.empty:
        st.warning("표시할 클러스터가 없습니다.")
    else:
        # Scatter Plot using 'group_type' for consistent coloring
        fig_cls = px.scatter(
            cluster_stats,
            x="count",
            y="avg_intensity",
            size="impact_score",
            color="group_type", # Use the explicit group type
            text="keywords_label",
            hover_name="keywords_label",
            hover_data={"count":True, "avg_intensity":':.2f', "main_category":True, "cluster":True},
            labels={
                "count": "리뷰 수 (Log Scale)", 
                "avg_intensity": "평균 심각도/강도 (1~5)",
                "group_type": "구분(Sentiment)",
                "keywords_label": "대표 키워드"
            },
            title="Cluster Impact: Negative Risk vs Positive Strength",
            color_discrete_map={
                "Negative (Risk)": "#EF553B", 
                "Positive (Strength)": "#00CC96"
            },
            log_x=True,
            range_y=[1, 5.5]
        )
        
        # Improve Text Position so it doesn't overlap too much
        fig_cls.update_traces(textposition='top center')
    
        fig_cls.update_layout(height=600)
    
        st.plotly_chart(fig_cls, use_container_width=True)



# ========================================================
# 0. SENTIMENT BREAKDOWN (3-Column View)
# ========================================================
st.subheader("0️⃣ 감성별 핵심 키워드 (Sentiment Breakdown)")
st.caption("부정(Risk), 중립(Feedback), 긍정(Strength) 리뷰에서 가장 많이 언급된 키워드를 분석합니다.")

# Data Prep for Keywords
if "keywords" in df.columns:
    kw_df = df[["sentiment_label", "keywords"]].copy()
    kw_df["kw_list"] = kw_df["keywords"].apply(robust_eval_list)
    kw_df = kw_df.explode("kw_list")
    kw_df = kw_df[kw_df["kw_list"].notna()]
    kw_df = kw_df[kw_df["kw_list"] != ""]
    
    # [NORMALIZATION] Consolidate Synonyms & Handle Variations
    def normalize_kw_display(text):
        if not isinstance(text, str): return text
        text = text.strip()
        text_ns = text.replace(" ", "")
        
        # Manual Map (Consolidate to ID or Stop Target)
        map_dict = {
            "재미있는": "재미", "재밌는": "재미", "꿀잼": "재미", "존잼": "재미", "잼": "재미",
            "게임플레이": "게임", "플레이": "게임", "Game": "게임",
            "업뎃": "업데이트", "패치": "업데이트", "업그레이드": "업데이트",
            "타격": "타격감",
            "랙": "최적화", "렉": "최적화", "튕김": "최적화", "발열": "최적화", "버벅": "최적화", "끊김": "최적화",
            "캐릭": "캐릭터", "여캐": "캐릭터", "남캐": "캐릭터",
            "현질": "과금", "과금유도": "과금",
            "운영자": "운영", "개발자": "운영",
            "스토리": "스토리", # Keep
            "아트": "아트/그래픽", "그래픽": "아트/그래픽", "일러": "아트/그래픽", "일러스트": "아트/그래픽"
        }
        
        if text in map_dict: return map_dict[text]
        if text_ns in map_dict: return map_dict[text_ns]
        
        return text

    kw_df["kw_list"] = kw_df["kw_list"].apply(normalize_kw_display)

    # [FILTER] Remove generic/stop keywords from visualization
    STOP_KEYWORDS = {"재미", "게임", "Good", "Play", "하는", "할", "함", "전투", "유저", "사람", "것", "수", "저", "제"}
    kw_df = kw_df[~kw_df["kw_list"].isin(STOP_KEYWORDS)]
    
    # 2 Columns (Negative, Positive)
    col_neg, col_pos = st.columns(2)
    
    # Function to plot top keywords
    def plot_top_keywords(sent_filter, title, color_scale):
        subset = kw_df[kw_df["sentiment_label"] == sent_filter]
        if subset.empty:
            st.info(f"{title}: 데이터 없음 ({len(subset)}건)")
            return
            
        top_k = subset["kw_list"].value_counts().head(10).reset_index()
        top_k.columns = ["keyword", "count"]
        
        if top_k.empty:
             st.info(f"{title}: 키워드 없음")
             return

        fig = px.bar(
            top_k,
            x="count",
            y="keyword",
            orientation='h',
            title=title,
            labels={"count": "빈도", "keyword": "키워드"},
            color="count",
            color_continuous_scale=color_scale
        )
        fig.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False, height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col_neg:
        st.markdown("### 🔴 부정 (Negative)")
        plot_top_keywords("Negative", "Risk Keywords", "Reds")
        
    with col_pos:
        st.markdown("### 🔵 긍정 (Positive)")
        plot_top_keywords("Positive", "Strength Keywords", "Blues")

else:
    st.warning("키워드 데이터가 없어 분석할 수 없습니다.")

st.markdown("---")

st.markdown("---")

# ========================================================
# 1. HIERARCHICAL ANALYSIS (Treemap by Sentiment)
# ========================================================
st.subheader("1️⃣ 계층형 이슈 분석 (Treemap by Sentiment)")
st.caption("감성별로 **주제 → 키워드** 계층 구조를 시각화합니다. (박스 크기 = 빈도)")

# Prepare Data
# Prioritize 'refined_category' for consistent filtering if available
if "refined_category" in df.columns:
    df["categories"] = df["refined_category"]

# Prioritize 'refined_topic' (from cluster propagation)
possible_topics = ["refined_topic", "cluster_label", "categories", "category", "topic", "issue_summary"]
topic_col = next((c for c in possible_topics if c in df.columns), None)

# If no topic column, create a placeholder
if topic_col is None:
    df["topic_display"] = "General"
    topic_col = "topic_display"

# Clean Topic Column (Extract first item if list)
def clean_topic(val):
    if pd.isna(val): return "Etc"
    s_val = str(val).strip()
    
    # Empty cases
    if s_val in ["", "[]"]: return "Etc"
    
    # Check if it looks like a list string "['Topic']"
    if s_val.startswith("[") and s_val.endswith("]"):
        # Remove brackets and quotes to just get content
        cleaned = s_val.replace("[", "").replace("]", "").replace("'", "").replace('"', "")
        # Split by comma and take first item if exists
        items = [x.strip() for x in cleaned.split(",") if x.strip()]
        if items:
            return items[0]
        else:
            return "Etc"
            
    # Regular string (e.g. "성장") - Return as is
    return s_val

# Apply cleaning only if it looks like a list column (like categories) or ensure it's clean text
if topic_col in ["categories", "category", "topic", "refined_topic"]:
    df[topic_col] = df[topic_col].apply(clean_topic)

# Keyword Helper
def get_first_kw_robust(val):
    l = robust_eval_list(val)
    return l[0] if l else "Etc"
        
if "keywords" in df.columns:
    df["primary_keyword"] = df["keywords"].apply(get_first_kw_robust)
else:
    df["primary_keyword"] = "Unknown"

def plot_full_width_treemap(sent_label, color_scale, title):
    # Filter by Sentiment
    t_subset = df[df["sentiment_label"] == sent_label].copy()
    
    # Filter out Generic/Empty Topics & Keywords
    # We remove rows where Topic/Keyword is 'Etc', 'Unknown', 'None' etc.
    generic_terms = ["Etc", "Unknown", "None", "nan", ""]
    
    mask_valid_topic = ~t_subset[topic_col].astype(str).isin(generic_terms)
    # mask_valid_kw = ~t_subset["primary_keyword"].astype(str).isin(generic_terms)
    
    # Relaxed Filter: Show even if keyword is generic (user wants to see distribution)
    t_subset = t_subset[mask_valid_topic]

    if t_subset.empty:
        st.info(f"{title}: 유의미한 분석 데이터(Topic/Keyword)가 부족합니다.")
        return

    tree_data = t_subset.groupby([topic_col, "primary_keyword"]).size().reset_index(name="count")
    # Filter out low frequency keywords (Keep > 2)
    tree_data = tree_data[tree_data["count"] > 2] # Filter <= 2 
    
    if tree_data.empty:
        st.info(f"{title}: 표시할 데이터가 부족합니다.")
        return

    # Treemap
    fig_tm = px.treemap(
        tree_data,
        path=[px.Constant(sent_label), topic_col, "primary_keyword"],
        values="count",
        color="count", # Color by magnitude to use the scale
        color_continuous_scale=color_scale,
        title=title,
        height=500  # Taller for better view
    )
    fig_tm.update_layout(margin=dict(t=30, l=10, r=10, b=10))
    st.plotly_chart(fig_tm, use_container_width=True)

# 1. Negative (Red)
st.markdown("### 🔴 부정 (Negative)")
plot_full_width_treemap("Negative", "Reds", "Negative Issues (Risk)")

# 3. Positive (Blue)
st.markdown("---")
st.markdown("### 🔵 긍정 (Positive)")
plot_full_width_treemap("Positive", "Blues", "Positive Strengths (Growth)")

# ========================================================
# 3. SENTIMENT TREND (Stacked Area)
# ========================================================
st.markdown("---")
st.subheader("3️⃣ 감성 트렌드 변화 (Stacked Area)")
st.caption("시간 또는 버전 흐름에 따른 긍/부정 리뷰 발생량의 변화를 확인합니다.")

# Control
trend_by = st.radio("기준 선택", ["📅 일별 (Date)", "🏷️ 버전별 (Version)"], horizontal=True, index=0)

if "일별" in trend_by:
    x_col = "at"
    trend_df = df.set_index("at").groupby([pd.Grouper(freq="D"), "sentiment_label"]).size().unstack(fill_value=0).reset_index()
    x_title = "날짜"
else:
    # Version-based: Sort by Release Date (Min 'at')
    x_col = "appVersion"
    if "appVersion" not in df.columns:
        st.error("데이터에 'appVersion' 컬럼이 없습니다.")
        st.stop()
        
    # Calculate order (Semantic Version Sort)
    unique_versions = df["appVersion"].dropna().unique()
    try:
        # Try sorting by semantic versioning (Major.Minor.Patch)
        ver_order = sorted(unique_versions, key=parse_version)
    except:
        # Fallback to date min if parsing fails
        ver_order = df.groupby("appVersion")["at"].min().sort_values().index.tolist()
    
    trend_df = df.groupby(["appVersion", "sentiment_label"]).size().unstack(fill_value=0).reset_index()
    
    # Filter: Remove versions with <= 10 reviews to avoid distortion
    trend_df["Total_Count"] = trend_df[["Negative", "Neutral", "Positive"]].sum(axis=1)
    trend_df = trend_df[trend_df["Total_Count"] > 10]
    
    if trend_df.empty:
        st.warning("리뷰 수가 10개 초과인 버전이 없습니다.")
    
    # Sort
    trend_df["appVersion"] = pd.Categorical(trend_df["appVersion"], categories=ver_order, ordered=True)
    trend_df = trend_df.sort_values("appVersion")
    x_title = "버전 (리뷰 10개 초과)"

# Tabs
tab_vol, tab_ratio = st.tabs(["📊 리뷰 수 (Volume)", "📈 비율 (Ratio %)"])

with tab_vol:
    fig_area = px.area(
        trend_df,
        x=x_col,
        y=["Negative", "Neutral", "Positive"],
        color_discrete_map={
            "Positive": "#00CC96",
            "Neutral": "#AB63FA",
            "Negative": "#EF553B"
        },
        labels={"value": "리뷰 수", x_col: x_title},
        title=f"{x_title}별 감성 발생량 (절대값)"
    )
    st.plotly_chart(fig_area, use_container_width=True)

with tab_ratio:
    # Calculate Average Sentiment Score Trend
    if x_col == "at": # Date
        s_trend = df.set_index("at").groupby(pd.Grouper(freq="D"))["sentiment_score_val"].mean().reset_index()
    else: # Version
        s_trend = df.groupby("appVersion")["sentiment_score_val"].mean().reset_index()
        # Sort version logic using 'ver_order' from 'Volume' block
        # We assume 'ver_order' exists if x_col != "at"
        s_trend["appVersion"] = pd.Categorical(s_trend["appVersion"], categories=ver_order, ordered=True)
        s_trend = s_trend.sort_values("appVersion")

    fig_line = px.line(
        s_trend,
        x=x_col,
        y="sentiment_score_val",
        labels={"sentiment_score_val": "평균 감정점수", x_col: x_title},
        title=f"{x_title}별 평균 감정점수 변화 (Average Sentiment Score)"
    )
    fig_line.update_traces(line_color="#636EFA", mode="lines+markers")
    st.plotly_chart(fig_line, use_container_width=True)

# ========================================================
# 4. INTERACTIVE DATA TABLE
# ========================================================
st.markdown("---")
st.subheader("🔍 심층 데이터 탐색")

# Filters
f_col1, f_col2 = st.columns(2)
with f_col1:
    options_topic = sorted(df[topic_col].unique().astype(str))
    sel_topics = st.multiselect("주제(Topic) 필터", options=options_topic)
with f_col2:
    sel_senti = st.multiselect("감성(Sentiment) 필터", options=["Negative", "Neutral", "Positive"])

filtered_df = df.copy()
if sel_topics:
    # Ensure type match for filtering
    filtered_df = filtered_df[filtered_df[topic_col].astype(str).isin(sel_topics)]
if sel_senti:
    filtered_df = filtered_df[filtered_df["sentiment_label"].isin(sel_senti)]

# Sort by Thumbs Up Count
if "thumbsUpCount" in filtered_df.columns:
    filtered_df["thumbsUpCount"] = pd.to_numeric(filtered_df["thumbsUpCount"], errors="coerce").fillna(0).astype(int)
    filtered_df = filtered_df.sort_values("thumbsUpCount", ascending=False)
    
# Show Table with Clean Configuration
st.dataframe(
    filtered_df,
    column_order=["at", "thumbsUpCount", "score", "sentiment_label", topic_col, "primary_keyword", "content"],
    column_config={
        "at": st.column_config.DateColumn("작성일", format="YYYY-MM-DD"),
        "thumbsUpCount": st.column_config.NumberColumn("👍 공감", format="%d"),
        "score": st.column_config.NumberColumn("평점", format="%d ⭐"),
        "sentiment_label": "감성",
        topic_col: "주제",
        "primary_keyword": "키워드",
        "content": st.column_config.TextColumn("리뷰 내용", width="large"),
    },
    use_container_width=True,
    height=400,
    hide_index=True
)
