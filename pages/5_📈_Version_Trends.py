import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ast
import json
import os

# ------------------------------------------------------
# PAGE CONFIG
# ------------------------------------------------------
st.set_page_config(
    page_title="Version Insight Engine",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Version Insight Engine")
st.markdown("### 🧬 Release Quality DNA Analysis")

# ========================================================
# Load Data
# ========================================================
if "trend_df" not in st.session_state:
    st.error("⚠ 버전 트렌드 데이터가 없습니다. Main 페이지에서 데이터를 로드해 주세요.")
    st.stop()

trend_df = st.session_state["trend_df"].copy()
clean_df = st.session_state.get("clean_df", None)

if trend_df.empty:
    st.warning("버전 트렌드 데이터가 비어 있습니다.")
    st.stop()

# Ensure types
if "version" not in trend_df.columns and "appVersion" in trend_df.columns:
    trend_df = trend_df.rename(columns={"appVersion": "version"})
trend_df["version"] = trend_df["version"].astype(str)

# Filter Top N Versions
with st.sidebar:
    st.markdown("### ⚙️ Chart Filter")
    num_versions = st.slider("최신 버전 개수", 5, 20, 10)

# Sort: Newest to Oldest for Table, Oldest to Newest for Line Chart
# We assume input is somewhat sorted. Let's make sure we have 'Newest' at head for display
# For charts, we usually want X-axis Left->Right (Old->New)

# Let's simple reverse it if it looks descending (which is typical for tables)
if len(trend_df) > 1:
     # Heuristic: if index 0 is "higher" than index 1, it's descending.
     # But string comparison is weak. Just rely on user config or assume Descending input.
     trend_df_chart = trend_df.iloc[::-1]
else:
     trend_df_chart = trend_df
     
filtered_trend_df = trend_df_chart.tail(num_versions) # Take 'latest' N which are at the end of chart df

# ========================================================
# 0. STRATEGIC DELTA INSIGHTS
# ========================================================
st.subheader("📊 Version Delta Insights (Strategic Report)")
st.caption("최근 패치의 성과를 **변화량(Delta)** 중심으로 분석하여, 이번 업데이트가 '성공'인지 '위기'인지 판단합니다.")

if not filtered_trend_df.empty:
    # Latest Version Data
    latest_ver = filtered_trend_df.iloc[-1]
    prev_ver = filtered_trend_df.iloc[-2] if len(filtered_trend_df) > 1 else None
    
    # 1. Waterfall Chart: Sentiment Bridge (Changes Summary)
    st.markdown("#### 1️⃣ 변화 요약 (Sentiment Impact Waterfall)")
    
    val_prev = prev_ver['sentiment_score'] if prev_ver is not None else 0
    val_delta = latest_ver['delta_sentiment']
    val_curr = latest_ver['sentiment_score']
    
    fig_water = go.Figure(go.Waterfall(
        name="Sentiment Change",
        orientation="v",
        measure=["relative", "relative", "total"],
        x=["Previous Ver", "Delta Impact", "Current Ver"],
        textposition="outside",
        text=[f"{val_prev:.2%}", f"{val_delta:+.2%}", f"{val_curr:.2%}"],
        y=[val_prev, val_delta, 0], # Waterfall logic needs refinement for 'total'
        # Plotly Waterfall: 'relative' adds to running total, 'total' shows final result.
        # So: y=[val_prev, val_delta, None] is computed automatically?
        # Actually for 'total', 'y' is ignored usually if we compute it.
        # Better: [val_prev, val_delta, None] with measure [relative, relative, total]
        # But step 1 'Previous' is actually a base. 
        # Correct logic:
        # 1. Base (relative, val_prev) - treating as jump from 0
        # 2. Delta (relative, val_delta)
        # 3. Final (total, None)
    ))
    
    # Simpler Go.Waterfall
    fig_water = go.Figure(go.Waterfall(
        measure = ["relative", "relative", "total"],
        x = ["Previous Sentiment", "Update Impact (Delta)", "Current Sentiment"],
        text = [f"{val_prev:.2f}", f"{val_delta:+.2f}", f"{val_curr:.2f}"],
        y = [val_prev, val_delta, 0],
        connector = {"mode":"between", "line":{"width":4, "color":"rgb(0, 0, 0)", "dash":"solid"}},
        decreasing = {"marker":{"color":"#EF553B"}},
        increasing = {"marker":{"color":"#00CC96"}},
        totals = {"marker":{"color":"#636EFA"}}
    ))
    fig_water.update_layout(title=f"Update Impact Analysis: {latest_ver['version']}", height=400)
    
    c_w1, c_w2 = st.columns([1, 1])
    with c_w1:
        st.plotly_chart(fig_water, use_container_width=True)
    with c_w2:
        st.info(f"**💡 Insight**: 최신 버전({latest_ver['version']})의 긍정 비율은 **{val_curr:.0%}**입니다.\n\n"
                f"지난 버전 대비 **{val_delta:+.2f} ({val_delta*100:+.1f}%)** 변화했습니다.\n"
                f"{'📈 **민심 개선 성공**' if val_delta > 0 else '📉 **민심 하락 경고**'}")
        
    st.markdown("---")
    
    # 2. Strategic Patch Matrix (Quadrant)
    st.markdown("#### 2️⃣ 패치 성공/실패 매트릭스 (Strategic Matrix)")
    st.caption("X축: 관심도 변화(Volume Delta), Y축: 민심 변화(Sentiment Delta)")
    
    quad_df = filtered_trend_df.copy()
    
    fig_quad = px.scatter(
        quad_df,
        x="delta_volume",
        y="delta_sentiment",
        text="version",
        color="delta_sentiment",
        color_continuous_scale="RdBu",
        size="review_count", # Bubble size = Total Volume
        hover_data=["defect_score", "growth_score"],
        title="Patch Decision Matrix: Interest vs Sentiment",
        labels={"delta_volume": "Interest Change (Delta Volume)", "delta_sentiment": "Sentiment Change"},
    )
    
    # Add Quadrant Backgrounds
    # Q1 (Top-Right): Mega Hit (Vol+, Sent+)
    # Q2 (Bottom-Right): Crisis (Vol+, Sent-)
    # Q3 (Bottom-Left): Stagnant (Vol-, Sent-)
    # Q4 (Top-Left): Niche/Solid (Vol-, Sent+)
    
    # Use Shapes or Annotations? Annotations are easier for labels.
    fig_quad.add_hline(y=0, line_dash="dash", line_color="gray")
    fig_quad.add_vline(x=0, line_dash="dash", line_color="gray")
    
    # Quadrant Labels
    max_x = max(quad_df["delta_volume"].abs().max(), 10)
    max_y = max(quad_df["delta_sentiment"].abs().max(), 0.1)
    
    fig_quad.add_annotation(x=max_x/2, y=max_y/2, text="🚀 Mega Hit<br>(관심↑ 호평↑)", showarrow=False, font=dict(color="green", size=14))
    fig_quad.add_annotation(x=max_x/2, y=-max_y/2, text="🔥 Crisis<br>(관심↑ 혹평↓)", showarrow=False, font=dict(color="red", size=14))
    fig_quad.add_annotation(x=-max_x/2, y=-max_y/2, text="💤 Stagnant<br>(관심↓ 혹평↓)", showarrow=False, font=dict(color="gray", size=14))
    fig_quad.add_annotation(x=-max_x/2, y=max_y/2, text="🛡️ Solid/Niche<br>(관심↓ 호평↑)", showarrow=False, font=dict(color="blue", size=14))

    fig_quad.update_traces(textposition='top center')
    st.plotly_chart(fig_quad, use_container_width=True)

    st.markdown("---")

    st.markdown("---")

    # 3. Delta Trend Line (Volume removed to improve scale visibility)
    st.markdown("#### 3️⃣ 품질 변화 추세선 (Quality Delta Trend)")
    st.caption(
        "**모든 지표는 '높을수록 긍정적'인 방향으로 정렬되었습니다.** (Up = Good)\n"
        "- **안정성 개선**: 값이 양수(+)이면 버그/부정 이슈가 **감소**했다는 뜻입니다.\n"
        "- **긍정 요소 & 민심**: 값이 양수(+)이면 호평이 **증가**했다는 뜻입니다."
    )
    
    # Exclude 'delta_volume' as it dwarfs other metrics
    # Create descriptive labels for the Legend
    plot_df = filtered_trend_df.copy()
    
    # [VISUAL FIX] Invert Defect Delta so Up is Good (Stability Improvement)
    if "delta_defect" in plot_df.columns:
        plot_df["delta_defect"] = plot_df["delta_defect"] * -1
    
    rename_map = {
        "delta_defect": "🛡️ 안정성 개선 (Issues ↓)",
        "delta_growth": "✨ 긍정 요소 (Growth) 증감",
        "delta_sentiment": "💖 종합 민심 (Sentiment) 변화"
    }
    plot_df = plot_df.rename(columns=rename_map)
    
    quality_cols_kr = list(rename_map.values())
    
    fig_line = px.line(
        plot_df,
        x="version",
        y=quality_cols_kr,
        markers=True,
        title="버전별 품질 지표 변화 추이 (Quality Trends)",
        labels={"value": "변화량 (Delta)", "variable": "지표 (Metric)", "version": "버전"}
    )
    # Add zero line for reference
    fig_line.add_hline(y=0, line_dash="dash", line_color="gray")
    st.plotly_chart(fig_line, use_container_width=True)
    
    st.markdown("---")
    st.markdown("---")
    
    # ========================================================
    # 3. DETAILED VERSION CARDS
    # ========================================================
    st.subheader("🔍 릴리즈 상세 리포트 (Deep Dive)")

version_list = filtered_trend_df["version"].tolist()[::-1]
if not version_list:
    st.info("표시할 버전 데이터가 없습니다.")
else:
    # Load Deep Dive Data
    dd_data = {}
    
    # Dynamic Path based on session state
    current_date = st.session_state.get("current_date", "2025-12-10") # Fallback just in case
    dd_path = os.path.join("data", current_date, "version_trend_deep_dive.json")
    
    if os.path.exists(dd_path):
        try:
            with open(dd_path, "r", encoding="utf-8") as f:
                raw_dd = json.load(f)
                # Map version -> data
                for item in raw_dd:
                    dd_data[item["version"]] = item["data"]
        except Exception as e:
            st.error(f"Deep Dive 데이터 로딩 중 오류 발생: {e}")

    tabs = st.tabs(version_list)
    for i, ver in enumerate(version_list):
        row = filtered_trend_df[filtered_trend_df["version"] == ver].iloc[0]
        with tabs[i]:
            c1, c2, c3 = st.columns(3)
            c1.metric("Defect Score", f"{row['defect_score']:.2f}", delta=f"{-row.get('delta_defect',0):.2f}", delta_color="inverse")
            c2.metric("Growth Score", f"{row['growth_score']:.2f}", delta=f"{row.get('delta_growth',0):.2f}")
            c3.metric("Volume", f"{row['review_count']}", delta=f"{row.get('delta_volume',0):.0f}")
            
            # [Connectivity] Raw Voice Link
            if st.button("🔊 원문 보기 (Raw Voice)", key=f"btn_raw_{ver}"):
                 st.session_state['nav_version'] = ver
                 st.session_state['filter_review_ids'] = None
                 st.switch_page("pages/2_🔍_Review_Explorer.py")
            
            # --- Deep Dive UI ---
            if ver in dd_data:
                dd = dd_data[ver]
                
                # 1. Top Defects
                st.markdown("#### 🔥 Top Defects Deep Dive")
                if "defects" in dd and dd["defects"]:
                    for d in dd["defects"]:
                        if not isinstance(d, dict): continue # Robustness check
                        
                        owner = d.get('owner', 'TBD')
                        with st.expander(f"💥 [{owner}] {d.get('name', 'Issue')} (Count: {d.get('count',0)}, Delta: {d.get('delta',0):+d})", expanded=True):
                            st.markdown(f"**주요 불만 요약:**\n{d.get('summary', '-')}")
                            st.markdown("**대표 리뷰 문장:**")
                            for s in d.get("sentences", []):
                                st.info(f"\"{s}\"")
                            st.caption(f"담당 부서: {owner} | 핵심 키워드: {', '.join(d.get('keywords', []))}")
                else:
                    st.info("심각한 Defect가 발견되지 않았습니다.")

                # 2. Top Appeals
                st.markdown("#### ✨ Top Appeals Deep Dive")
                if "appeals" in dd and dd["appeals"]:
                    for a in dd["appeals"]:
                         if not isinstance(a, dict): continue # Robustness check
                         
                         owner = a.get('owner', 'TBD')
                         with st.expander(f"🌟 [{owner}] {a.get('name', 'Appeal')} (Count: {a.get('count',0)}, Delta: {a.get('delta',0):+d})", expanded=True):
                            st.markdown(f"**주요 호응 포인트:**\n{a.get('summary', '-')}")
                            st.markdown("**긍정 리뷰 대표 문장:**")
                            for s in a.get("sentences", []):
                                st.success(f"\"{s}\"")
                            st.caption(f"담당 부서: {owner} | 핵심 키워드: {', '.join(a.get('keywords', []))}")
                else:
                    st.info("뚜렷한 호응 요소가 발견되지 않았습니다.")
            
            else:
                st.info("적절한 리뷰를 찾지 못하였습니다.")
