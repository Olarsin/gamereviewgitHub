import streamlit as st
import pandas as pd
import plotly.express as px

# ------------------------------------------------------
# PAGE CONFIG
# ------------------------------------------------------
st.set_page_config(
    page_title="Action Items Dashboard",
    page_icon="🛠️",
    layout="wide",
)

st.title("🛠️ Action Items Dashboard")
st.markdown("### 🚨 이슈 진단 및 🚀 성장 전략 실행 가이드")
st.markdown("LLM이 심층 분석한 **구체적인 해결 방안**과 **전략**을 부서별로 확인하세요.")
st.markdown("---")

# ========================================================
# LOAD DATA
# ========================================================
if "diagnosis_df" not in st.session_state and "growth_df" not in st.session_state:
    st.error("⚠ 분석 데이터가 로드되지 않았습니다. Main 페이지에서 데이터를 먼저 로드해주세요.")
    st.stop()

# Get DataFrames (handle cases where one might be missing)
diag_df = st.session_state.get("diagnosis_df", pd.DataFrame())
growth_df = st.session_state.get("growth_df", pd.DataFrame())

if diag_df is None: diag_df = pd.DataFrame()
if growth_df is None: growth_df = pd.DataFrame()

# ========================================================
# TABS: Diagnosis (Defects) vs Growth (Opportunity)
# ========================================================
tab_diag, tab_growth = st.tabs(["🔥 긴급 대응 (Fix It)", "🌟 성장 전략 (Grow It)"])

# --------------------------------------------------------
# TAB 1: Diagnosis Report
# --------------------------------------------------------
with tab_diag:
    if diag_df.empty:
        st.info("🚨 발견된 긴급 이슈 리포트가 없습니다.")
    else:
        # 1. Filters
        c1, c2 = st.columns([1, 3])
        with c1:
            # Department Filter
            if "target_department" in diag_df.columns:
                depts = ["All"] + sorted(list(diag_df["target_department"].dropna().unique()))
                sel_dept = st.selectbox("🎯 담당 부서 필터", depts)
            else:
                sel_dept = "All"
                
            # Sort Order
            sort_opts = ["긴급도 높은순 (Urgency)", "긴급도 낮은순"]
            sel_sort = st.radio("정렬 기준", sort_opts)

        # Apply Filters
        d_view = diag_df.copy()
        if sel_dept != "All":
            d_view = d_view[d_view["target_department"] == sel_dept]
            
        if sel_sort == "긴급도 높은순 (Urgency)":
            d_view = d_view.sort_values(by="urgency_score", ascending=False)
        else:
            d_view = d_view.sort_values(by="urgency_score", ascending=True)

        # 2. Key Metrics (Filtered)
        with c2:
            m1, m2, m3 = st.columns(3)
            m1.metric("확인된 이슈", f"{len(d_view)}건")
            avg_urg = d_view["urgency_score"].mean() if not d_view.empty else 0
            m2.metric("평균 긴급도", f"{avg_urg:.1f}")
            # Top Department
            if not d_view.empty and "target_department" in d_view.columns:
                top_d = d_view["target_department"].mode()[0]
                m3.metric("최다 발생 부서", top_d)

        st.divider()

        # 3. List Items
        for idx, row in d_view.iterrows():
            # Color code based on urgency
            urgency = row.get("urgency_score", 0)
            prefix = "🔴 [Critical]" if urgency >= 80 else "🟠 [Major]" if urgency >= 50 else "🟡 [Minor]"
            
            with st.expander(f"{prefix} {row['issue_title']} (Score: {urgency:.1f})", expanded=(idx < 2)): # Expand top 2
                
                ec1, ec2 = st.columns([2, 1])
                
                with ec1:
                    st.markdown(f"**💬 진단 요약:** {row.get('diagnosis_summary', '-')}")
                    
                    st.markdown("#### 🕵️ 재현 경로 (Reproduction Steps)")
                    st.info(row.get('reproduction_steps', '정보 없음'))
                    
                    st.markdown("#### 🛠️ 기술적/기획적 권장 사항")
                    st.success(row.get('technical_recommendation', '-'))

                with ec2:
                    st.markdown("**📂 담당 부서**")
                    st.write(f"`{row.get('target_department', 'Unknown')}`")
                    
                    st.markdown("**🛡️ 심각도 (Severity)**")
                    st.write(f"`{row.get('severity_level', '-')}`")

                    st.markdown("**🗣️ 유저 인용 (Quotes)**")
                    quotes = row.get('user_quotes', [])
                    if isinstance(quotes, str):
                        # Simple parsing if it looks like list string
                        try:
                            import ast
                            quotes = ast.literal_eval(quotes)
                        except:
                            quotes = [quotes]
                    
                    for q in quotes[:3]:
                        st.markdown(f"> *\"{q}\"*")

# --------------------------------------------------------
# TAB 2: Growth Strategy
# --------------------------------------------------------
with tab_growth:
    if growth_df.empty:
        st.info("🚀 제안된 성장 전략 리포트가 없습니다.")
    else:
        # 1. Filters (Simplified)
        g_view = growth_df.sort_values(by="potential_score", ascending=False)
        
        st.markdown(f"### 총 {len(g_view)}건의 성장 기회가 감지되었습니다.")
        
        for idx, row in g_view.iterrows():
            pot = row.get('potential_score', 0)
            icon = "🌟" if pot >= 80 else "✨"
            
            with st.container():
                st.subheader(f"{icon} {row['core_appeal']}")
                st.caption(f"Potential Score: {pot:.1f}")
                
                gc1, gc2 = st.columns(2)
                
                with gc1:
                    st.markdown("**📈 전략적 제안 (Growth Strategy)**")
                    st.info(row.get('growth_strategy', '-'))
                    
                with gc2:
                    st.markdown("**💡 유저 피드백/건의 (Constructive Feedback)**")
                    st.warning(row.get('constructive_feedback', '-'))
                
                st.markdown("**🗣️ 대표 칭찬/건의**")
                st.markdown(f"> {row.get('user_quote', '-')}")
                
                st.divider()
