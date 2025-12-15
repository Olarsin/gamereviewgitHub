import streamlit as st
import pandas as pd
import plotly.express as px

# ------------------------------------------------------
# PAGE CONFIG
# ------------------------------------------------------
st.set_page_config(
    page_title="Update Impact Checker",
    page_icon="⚙️",
    layout="wide",
)

st.title("⚙️ Update Impact Checker")
st.markdown("### 릴리즈 노트와 실제 유저 반응을 비교하여 업데이트 효과를 확인하세요.")

# ========================================================
# maincopy.py(Session Setup)에서 만든 세션 데이터 불러오기
# ========================================================
# 우선순위: 클러스터까지 끝난 경우 cluster_df 사용, 아니면 clean_df 사용 
if "cluster_df" in st.session_state:
    df = st.session_state["cluster_df"].copy()
elif "clean_df" in st.session_state:
    df = st.session_state["clean_df"].copy()
else:
    st.error("⚠ 먼저 maincopy.py(Session Setup)에서 데이터를 업로드/전처리해 주세요.")
    st.stop()

# -----------------------------
# 필수 컬럼 체크 (날짜 포함)
# -----------------------------
required_cols = ["content", "score", "at"]
missing = [c for c in required_cols if c not in df.columns]
if missing:
    st.error(f"데이터프레임에 다음 컬럼이 있어야 합니다: {missing}")
    st.stop()

# 날짜/점수 안전하게 변환
df["at"] = pd.to_datetime(df["at"], errors="coerce")
df = df.dropna(subset=["at"])

if df.empty:
    st.error("유효한 날짜(at)가 있는 리뷰 데이터가 없습니다.")
    st.stop()

# Score safe conversion
df["score"] = pd.to_numeric(df["score"], errors="coerce")
df = df.dropna(subset=["score"])
try:
    df["score"] = df["score"].astype(int)
except:
    pass


# ======================================================
# 릴리즈 노트 입력 (세션에 저장해서 유지)
# ======================================================
st.subheader("📝 릴리즈 노트 입력")

# 세션에 기본 값 준비
if "release_text" not in st.session_state:
    st.session_state["release_text"] = ""

# 입력 방식 선택 (직접 / CSV)
method = st.radio(
    "릴리즈 노트 입력 방식 선택",
    ["직접 입력", "CSV 파일 업로드"],
    key="release_method"
)

release_text = ""

# 1) 직접 복사-붙여넣기
if method == "직접 입력":
    release_text = st.text_area(
        "릴리즈 노트 내용을 입력하세요",
        height=200,
        placeholder="예: 로그인 지연 버그 수정\nUI 버튼 클릭 오류 해결\n게임 밸런스 조정",
        key="release_text_area",
        value=st.session_state["release_text"],  # ▶ 이전 내용 유지
    )
    # 사용자가 새로 입력한 값으로 세션 업데이트
    st.session_state["release_text"] = release_text

# 2) CSV 업로드 후, 텍스트 컬럼 선택
else:
    release_file = st.file_uploader(
        "릴리즈 노트 CSV 파일 업로드",
        type=["csv"],
        key="release_csv"
    )

    if release_file is not None:
        rel_df = pd.read_csv(release_file)

        # 문자열(object) 컬럼 후보만 보여주기
        text_cols = rel_df.select_dtypes(include=["object"]).columns.tolist()

        if not text_cols:
            st.error("텍스트(문자열) 컬럼이 없는 CSV 입니다. 릴리즈 노트가 들어있는 컬럼이 필요합니다.")
        else:
            col_name = st.selectbox(
                "릴리즈 노트가 들어있는 컬럼을 선택하세요",
                text_cols,
                key="release_text_col"
            )
            # 선택한 컬럼의 텍스트를 줄바꿈으로 이어 붙여 릴리즈 노트처럼 사용
            release_text = "\n".join(
                rel_df[col_name].dropna().astype(str).tolist()
            )

            # CSV에서 읽어온 내용도 세션에 저장해서 유지
            st.session_state["release_text"] = release_text

    # CSV 업로드 전에는, 이전에 저장되어 있던 텍스트를 사용
    release_text = st.session_state["release_text"]

# 최종적으로 release_text가 세션에서 가져온 값이 되도록 통일
release_text = st.session_state["release_text"]

if not release_text.strip():
    st.info("릴리즈 노트를 입력하거나 CSV를 업로드하면 분석이 시작됩니다.")
    st.stop()

# ------------------------------------------------------
# 릴리즈 노트에서 변경항목 분리
# ------------------------------------------------------
changes = [line.strip() for line in release_text.split("\n") if line.strip()]

st.markdown("### 📌 감지된 변경 사항")
for c in changes:
    st.write(f"- {c}")

# ======================================================
# 업데이트 날짜 선택
# ======================================================
st.subheader("📅 업데이트 날짜 선택")

min_date = df["at"].min().date()
max_date = df["at"].max().date()

update_date = st.date_input(
    "업데이트 날짜를 선택하세요",
    value=max_date,
    min_value=min_date,
    max_value=max_date,
)

update_date = pd.to_datetime(update_date)

# 업데이트 전/후 구분
before_df = df[df["at"] < update_date]
after_df = df[df["at"] >= update_date]

if before_df.empty or after_df.empty:
    st.warning("업데이트 전/후 리뷰가 충분하지 않습니다. 날짜를 다른 값으로 조정해주세요.")
    st.stop()

# ======================================================
# 업데이트 영향 요약
# ======================================================
st.subheader("📊 업데이트 전/후 요약")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("업데이트 전 리뷰 수", len(before_df))

with col2:
    st.metric("업데이트 후 리뷰 수", len(after_df))

with col3:
    st.metric(
        "평균 별점 변화",
        f"{before_df['score'].mean():.2f} → {after_df['score'].mean():.2f}",
    )

# ------------------------------------------------------
# 전/후 전체 평점 변화 라인 차트
# ------------------------------------------------------
st.markdown("#### 📈 업데이트 전/후 평점 추이")

# 날짜별 평균 별점
daily = df.groupby(df["at"].dt.date).agg({"score": "mean"}).reset_index()
daily["at"] = pd.to_datetime(daily["at"])

fig_line = px.line(
    daily,
    x="at",
    y="score",
    title="평균 별점 변화",
)

# 🔹 업데이트 시점 표시 (vline 대신 점 + 텍스트)
update_dt = pd.to_datetime(update_date)

# 업데이트 날짜에 해당하는 점 찾기 (없으면 가장 가까운 날짜 사용)
if (daily["at"] == update_dt).any():
    y_val = daily.loc[daily["at"] == update_dt, "score"].iloc[0]
else:
    idx = (daily["at"] - update_dt).abs().idxmin()
    y_val = daily.loc[idx, "score"]
    update_dt = daily.loc[idx, "at"]

fig_line.add_scatter(
    x=[update_dt],
    y=[y_val],
    mode="markers+text",
    text=["업데이트"],
    textposition="top center",
    marker=dict(size=10, color="red"),
)

st.plotly_chart(fig_line, use_container_width=True)

# ======================================================
# 변경점별 영향 분석
# ======================================================
st.subheader("🔧 변경점 별 영향 분석")

results = []

for change in changes:
    # 공백 줄 방지
    tokens = change.split()
    if not tokens:
        continue

    # 첫 단어 기준 키워드
    keyword = tokens[0]

    # 정규식 사용 X, 단순 문자열 검색
    before_match = before_df["content"].fillna("").str.contains(
        keyword,
        case=False,   # 대소문자 무시
        na=False,
        regex=False,  # << 여기가 핵심!
    )
    after_match = after_df["content"].fillna("").str.contains(
        keyword,
        case=False,
        na=False,
        regex=False,
    )

    before_sub = before_df[before_match]
    after_sub = after_df[after_match]

    before_avg = before_sub["score"].mean() if len(before_sub) > 0 else None
    after_avg = after_sub["score"].mean() if len(after_sub) > 0 else None

    results.append(
        {
            "change": change,
            "before_count": len(before_sub),
            "after_count": len(after_sub),
            "before_avg": before_avg,
            "after_avg": after_avg,
        }
    )

impact_df = pd.DataFrame(results)

st.dataframe(impact_df, use_container_width=True)

# ------------------------------------------------------
# 변경 사항별 시각화
# ------------------------------------------------------
st.markdown("#### 📉 변경점별 리뷰 수 변화")

if not impact_df.empty:
    fig_change = px.bar(
        impact_df,
        x="change",
        y=["before_count", "after_count"],
        title="변경점별 리뷰 수 Before / After",
        barmode="group",
    )
    st.plotly_chart(fig_change, use_container_width=True)

# ------------------------------------------------------
# 개선도 점수 (Placeholder 계산식)
# ------------------------------------------------------
st.subheader("🏆 개선도 점수 (임시 계산)")

def compute_score(row):
    """기본 임시 점수 계산: 리뷰가 줄고 별점이 오르면 높은 점수"""
    s = 0
    if row["before_count"] > 0:
        ratio = (row["before_count"] - row["after_count"]) / row["before_count"]
        s += ratio * 50  # 불만 감소 반영

    if row["before_avg"] is not None and row["after_avg"] is not None:
        s += (row["after_avg"] - row["before_avg"]) * 10

    return round(max(s, 0), 2)

impact_df["impact_score"] = impact_df.apply(compute_score, axis=1)

st.dataframe(
    impact_df[["change", "impact_score"]],
    use_container_width=True,
)

st.success("업데이트 영향 분석이 완료되었습니다 🎉")
