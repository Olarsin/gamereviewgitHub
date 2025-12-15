import streamlit as st

st.set_page_config(
    page_title="Scraping Guide",
    page_icon="🧲",
    layout="wide"
)

st.title("🧲 Google Play 리뷰 Scraper (Colab Style)")

st.markdown(
    """
원하는 **App ID**, **리뷰 개수**, **언어/스토어**를 선택하면  
Google Colab에서 바로 실행 가능한 **스크래핑 + 정제 + CSV 다운로드** 코드를 자동으로 생성합니다.

> ⚠ 이 페이지에서는 실제 스크래핑을 하지 않고, **코드만 만들어서 보여주는 용도**입니다.
"""
)
st.markdown("---")

# --------------------------------------------------------
# 0) 언어 / 스토어 매핑
# --------------------------------------------------------
LANG_MAP = {
    "한국어 🇰🇷 (한국 스토어)": {
        "lang": "ko",
        "country": "kr",
        "is_korean": True,
        "desc": "한국어 리뷰 + 한국 스토어 기준"
    },
    "영어 🇺🇸 (미국 스토어)": {
        "lang": "en",
        "country": "us",
        "is_korean": False,
        "desc": "영어 리뷰 + 미국 스토어 기준"
    },
    "일본어 🇯🇵 (일본 스토어)": {
        "lang": "ja",
        "country": "jp",
        "is_korean": False,
        "desc": "일본어 리뷰 + 일본 스토어 기준"
    },
    "중국어 번체 🇹🇼 (대만 스토어)": {
        "lang": "zh",
        "country": "tw",
        "is_korean": False,
        "desc": "중국어(번체) 리뷰 + 대만 스토어 기준"
    },
    "독일어 🇩🇪 (독일 스토어)": {
        "lang": "de",
        "country": "de",
        "is_korean": False,
        "desc": "독일어 리뷰 + 독일 스토어 기준"
    },
}

# --------------------------------------------------------
# 1) 사용자 입력 (App ID + 리뷰 수 + 언어 선택)
# --------------------------------------------------------
st.header("1️⃣ 스크래핑 옵션 설정")

col1, col2, col3 = st.columns([2.2, 1.3, 1.5])

with col1:
    app_id = st.text_input(
        "App ID 입력",
        placeholder="예: com.nexon.devcat.mabinogi_m",
        help="Google Play URL의 id= 뒤에 나오는 문자열이 App ID 입니다."
    )

with col2:
    review_count = st.number_input(
        "리뷰 수 (max_reviews)",
        min_value=100,
        max_value=50000,
        value=30000,
        step=500,
        help="스크랩할 리뷰 최대 개수"
    )

with col3:
    lang_label = st.selectbox(
        "언어 / 스토어 선택",
        options=list(LANG_MAP.keys()),
        index=0
    )

lang_info = LANG_MAP[lang_label]
lang_code = lang_info["lang"]
country_code = lang_info["country"]
is_korean = lang_info["is_korean"]

st.caption(f"🌍 선택한 옵션: `{lang_code}-{country_code}` · {lang_info['desc']}")
st.caption("💡 App ID만 바꾸면 원하는 앱의 리뷰를 가져올 수 있습니다.")
st.markdown("---")

# --------------------------------------------------------
# 2) 언어별 정제 코드 블럭 생성
# --------------------------------------------------------
if is_korean:
    # 한국어 전용: 한글 비율 필터 + 노이즈 제거 + content_clean
    cleaning_block = """
# ===============================
# 4. 한국어 비율 기반 필터링 + 노이즈 제거
# ===============================

# 4-1) 결측/중복 정리
df["content"] = df["content"].fillna("").astype(str).str.strip()
df = df.drop_duplicates(subset=["reviewId"])

# 4-2) 한글 비율 계산 함수
_hangul = re.compile(r"[\\uac00-\\ud7a3]")   # 가-힣

def korean_ratio(text: str) -> float:
    if not text:
        return 0.0
    hangul_cnt = len(_hangul.findall(text))
    return hangul_cnt / max(len(text), 1)

# 4-3) 한국어 리뷰만 필터 (비율 임계값 0.6)
THRESH = 0.6
df["ko_ratio"] = df["content"].apply(korean_ratio)
ko_df = df[df["ko_ratio"] >= THRESH].copy()

# 4-4) 노이즈 제거: URL/이모지/여백
url_pat = r"https?://\\S+|www\\.\\S+"
emoji_pat = r"[\\U00010000-\\U0010ffff]"  # 대부분 이모지 범위

ko_df["content_clean"] = (
    ko_df["content"]
      .str.replace(url_pat, " ", regex=True)
      .str.replace(emoji_pat, " ", regex=True)
      .str.replace(r"\\s+", " ", regex=True)
      .str.strip()
)

print("원본 리뷰 개수:", len(df))
print("한국어 필터링 후 개수:", len(ko_df))
ko_df[["userName","score","content_clean"]].head()

clean_df = ko_df  # 이후 공통 처리용
"""
    output_name = "reviews_clean_ko.csv"
else:
    # 기타 언어: 기본 정제 + content_clean
    cleaning_block = """
# ===============================
# 4. 기본 텍스트 정제 (공통)
# ===============================

# 4-1) 결측/중복 정리
df["content"] = df["content"].fillna("").astype(str).str.strip()
df = df.drop_duplicates(subset=["reviewId"])

# 4-2) 노이즈 제거: URL/이모지/여백
url_pat = r"https?://\\S+|www\\.\\S+"
emoji_pat = r"[\\U00010000-\\U0010ffff]"  # 대부분 이모지 범위

df["content_clean"] = (
    df["content"]
      .str.replace(url_pat, " ", regex=True)
      .str.replace(emoji_pat, " ", regex=True)
      .str.replace(r"\\s+", " ", regex=True)
      .str.strip()
)

print("정제 후 리뷰 개수:", len(df))
df[["userName","score","content_clean"]].head()

clean_df = df  # 이후 공통 처리용
"""
    output_name = f"reviews_clean_{lang_code}.csv"

# --------------------------------------------------------
# 3) Colab 코드 전체 생성
# --------------------------------------------------------
st.header("2️⃣ Colab에서 실행할 코드 미리보기")

if not app_id.strip():
    st.info("👆 **먼저 App ID를 입력하면 아래에 Colab 코드가 생성됩니다.**")
else:
    code_block = f"""
# ===============================
# 0. Google Play Scraper 설치
# ===============================
!pip install google-play-scraper

# ===============================
# 1. 라이브러리 로드
# ===============================
from google_play_scraper import reviews, Sort
import pandas as pd
import re

# ===============================
# 2. 스크래핑 기본 설정
# ===============================
app_id = "{app_id}"          # 스크랩할 앱 ID
max_reviews = {review_count} # 최대 리뷰 개수

lang = "{lang_code}"         # 언어 코드
country = "{country_code}"   # 스토어 국가 코드

# ===============================
# 3. 리뷰 스크래핑 실행
# ===============================
result, continuation_token = reviews(
    app_id,
    lang=lang,
    country=country,
    count=max_reviews,
    sort=Sort.NEWEST
)

df = pd.DataFrame(result)

print("스크래핑 완료! 원본 리뷰 개수:", len(df))
df.head()
{cleaning_block}

# ===============================
# 5. 정제된 리뷰 CSV 저장 & 다운로드
# ===============================
output_path = "{output_name}"
clean_df.to_csv(output_path, index=False, encoding="utf-8-sig")

print("정제된 리뷰 CSV 저장 완료 →", output_path)

from google.colab import files
files.download(output_path)
"""

    st.code(code_block, language="python")
    st.success("✅ 위 코드 블록을 Colab에 그대로 붙여넣으면 스크래핑 → 정제 → CSV 다운로드까지 한 번에 실행됩니다.")

    st.markdown("---")
    st.header("3️⃣ 사용 방법 요약")
    st.markdown(
        """
1. **Google Colab** 새 노트를 연다.  
2. 위 코드 전체를 **하나의 셀에 붙여넣고 실행**한다.  
3. 실행이 끝나면  
   - `reviews_clean_*.csv` 파일이 생성되고  
   - 자동으로 다운로드 팝업이 뜬다.  
4. 다운로드한 CSV 파일을 이 Streamlit 앱의 **Session Setup(maincopy.py)** 페이지에서 업로드하면  
   → 전처리 · 클러스터링 · LLM 분석까지 바로 이어서 사용할 수 있다.
"""
    )

st.info("❗ Streamlit 쪽에서는 실제 스크래핑을 하지 않기 때문에, 추가 라이브러리 설치 없이 안전하게 돌아갑니다.")
