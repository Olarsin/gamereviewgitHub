import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import ast

# ------------------------------------------------------
# PAGE CONFIG
# ------------------------------------------------------
st.set_page_config(
    page_title="Strategic Insight Report",
    page_icon="📋",
    layout="wide",
)

st.title("📋 Strategic Insight Report")
st.markdown("### 🔍 심층 진단 및 조치 제안 (Deep Dive)")

# Load Data
if "current_date" not in st.session_state:
    st.error("⚠ 데이터를 로드하지 않았습니다. Main 페이지로 이동하여 데이터를 불러오세요.")
    st.stop()

def get_df(key):
    return st.session_state.get(key, None)

diag_df = get_df("diagnosis_df")
growth_df = get_df("growth_df")

# [Connectivity] Handle Drill-Down from Overview
target_cluster_id = st.session_state.get('nav_cluster_id', None)
if target_cluster_id:
    st.info(f"🔎 Filtered by Issue Cluster: {target_cluster_id}")
    if st.button("🔄 Reset Filter"):
        st.session_state['nav_cluster_id'] = None
        st.rerun()
        
    # Logic to filter diag_df by cluster
    # 1. Get review IDs for this cluster from main df
    main_df = st.session_state.get("cluster_df")
    if main_df is not None:
        # Convert cluster col to str
        cluster_reviews = main_df[main_df["cluster"].astype(str) == str(target_cluster_id)].index.tolist()
        
        # 2. Filter diag_df where 'review_ids' overlaps with cluster_reviews
        # diag_df['review_ids'] is string "[...]"
        def has_overlap(r_ids_str):
            try:
                if isinstance(r_ids_str, str): ids = ast.literal_eval(r_ids_str)
                else: ids = r_ids_str
                # Check intersection
                return not set(ids).isdisjoint(cluster_reviews)
            except: 
                return False
                
        diag_df = diag_df[diag_df["review_ids"].apply(has_overlap)]

# ========================================================
# DEFECT ACTION CENTER
# ========================================================
if diag_df is None or diag_df.empty:
    st.info("진단된 결함 이슈가 없습니다.")
else:
    # Preprocessing for Visualization
    def count_reviews(val):
        try:
            if isinstance(val, str):
                l = ast.literal_eval(val)
                return len(l) if isinstance(l, list) else 1
            return 1
        except:
            return 1
            
    if "review_count" not in diag_df.columns:
        diag_df["review_count"] = diag_df["review_ids"].apply(count_reviews)
        
    # 1. Bubble Chart: Strategic Priority Matrix (Confirmed Only)
    st.subheader("🚨 전략적 우선순위 매트릭스 (Strategic Priority Matrix)")
    st.caption("진단이 완료된 **핵심 결함 이슈(Confirmed Diagnosis)**를 긴급도와 빈도 기준으로 시각화합니다.")
    
    # Plot only Diagnosed items
    fig_bubble = px.scatter(
        diag_df,
        x="review_count",
        y="urgency_score",
        size="review_count", 
        color="target_department",
        hover_name="issue_title",
        text="issue_title",
        labels={"review_count": "발생 빈도(Frequency)", "urgency_score": "긴급도(Urgency Score)"},
        title="Confirmed Issues Matrix",
        height=500,
        log_x=True
    )
    fig_bubble.update_traces(textposition='top center')
    fig_bubble.add_hline(y=7.0, line_dash="dash", line_color="red", annotation_text="Critical Threshold")
    
    st.plotly_chart(fig_bubble, use_container_width=True)
    
    # 2. Kanban Board Style
    st.markdown("---")
    st.subheader("📋 조치 보드 (Kanban Style)")
    
    # Group by Department
    depts = diag_df["target_department"].unique()
    
    # Create columns for departments (limit to 3-4 for layout)
    cols = st.columns(len(depts))
    
    for idx, dept in enumerate(depts):
        with cols[idx]:
            st.markdown(f"#### 🏛️ {dept}")
            
            # Filter items
            dept_items = diag_df[diag_df["target_department"] == dept].sort_values("urgency_score", ascending=False)
            
            for _, row in dept_items.iterrows():
                # Card Style
                urgency_icon = "🔴" if row["urgency_score"] >= 8 else ("Wg" if row["urgency_score"] >= 5 else "🟢")
                
                with st.expander(f"{urgency_icon} {row['issue_title']} (Urg: {row['urgency_score']})"):
                    st.markdown(f"**Diagnosis**\n\n{row.get('diagnosis_summary', '-')}")
                    st.markdown(f"**Action**\n\n{row.get('technical_recommendation', '-')}")
                    st.caption(f"Severity: {row.get('severity_level', 'N/A')} | Count: {row.get('review_count', 0)}")
                    
                    # [Connectivity] Evidence Button
                    if st.button("🔎 Check Evidence", key=f"btn_{row.get('issue_title', 'unknown')}_{idx}"):
                        try:
                            # Parse IDs and send to Evidence Page
                            r_ids_str = row['review_ids']
                            if isinstance(r_ids_str, str): r_ids = ast.literal_eval(r_ids_str)
                            else: r_ids = r_ids_str
                            
                            st.session_state['filter_review_ids'] = r_ids
                            st.switch_page("pages/2_🔍_Review_Explorer.py")
                        except Exception as e:
                            st.error(f"Nav Error: {e}")
