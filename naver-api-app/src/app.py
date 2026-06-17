"""
이 애플리케이션은 네이버 OpenAPI를 연동하여 다양한 검색 및 트렌드 데이터를 시각화 분석하는 Streamlit 대시보드입니다.

주요 기능:
- 사이드바를 통한 안전한 API 키(Client ID, Client Secret) 입력 및 세션 상태 관리
- 네이버 데이터랩 검색어 트렌드 다중 비교 시계열 분석
- 네이버 쇼핑인사이트 주요 카테고리별 클릭 비율 트렌드 비교
- 블로그, 카페글, 뉴스, 쇼핑 검색 데이터 수집 및 분석 (가격 분포, 도메인/출처 분석, 발행 추이 등)
- Plotly 기반의 뉴브루탈리즘 스타일 인터랙티브 시각화 차트 제공
"""

import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
from urllib.parse import urlparse
import sys
import os
from dotenv import load_dotenv

# 상대 경로 임포트를 위한 path 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from naver_api import get_search_trend, get_shopping_trend, search_naver

# .env 파일 로드 (.env 파일이 존재하면 환경변수로 등록)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path=env_path)

# 1. 페이지 설정
st.set_page_config(
    layout="wide",
    page_title="Naver API Data Analysis Dashboard",
    page_icon="📊"
)

# 뉴브루탈리즘 스타일의 스타일링을 위한 커스텀 CSS 주입
st.markdown("""
<style>
    /* 메인 컨테이너 패딩 조정 */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    /* Bento Grid 느낌의 박스 스타일 */
    .metric-card {
        background-color: #f8f9fa;
        border: 2px solid #000000;
        border-radius: 8px;
        padding: 1.5rem;
        box-shadow: 4px 4px 0px #000000;
        margin-bottom: 1rem;
    }
    .metric-title {
        font-size: 0.9rem;
        color: #6c757d;
        font-weight: bold;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 900;
        color: #000000;
    }
    .metric-delta {
        font-size: 0.9rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# 세션 상태 초기화 (Secrets 또는 .env 파일에 설정된 값이 있다면 공백을 제거하고 기본값으로 사용)
if 'client_id' not in st.session_state:
    cid_val = ""
    try:
        if "naver_api" in st.secrets:
            cid_val = st.secrets["naver_api"].get("client_id", "")
        elif "client_id" in st.secrets:
            cid_val = st.secrets.get("client_id", "")
    except Exception:
        pass
    if not cid_val:
        cid_val = os.getenv('NAVER_CLIENT_ID', '')
    st.session_state['client_id'] = cid_val.strip() if cid_val else ''

if 'client_secret' not in st.session_state:
    csec_val = ""
    try:
        if "naver_api" in st.secrets:
            csec_val = st.secrets["naver_api"].get("client_secret", "")
        elif "client_secret" in st.secrets:
            csec_val = st.secrets.get("client_secret", "")
    except Exception:
        pass
    if not csec_val:
        csec_val = os.getenv('NAVER_CLIENT_SECRET', '')
    st.session_state['client_secret'] = csec_val.strip() if csec_val else ''

# 2. 사이드바 구성
# Secrets 또는 .env 파일에 키 정보가 이미 로드되어 있는 경우 사이드바 입력 폼을 생략하여 깔끔하게 UI 구성
cid_loaded = False
try:
    if "naver_api" in st.secrets and st.secrets["naver_api"].get("client_id") and st.secrets["naver_api"].get("client_secret"):
        cid_loaded = True
    elif "client_id" in st.secrets and "client_secret" in st.secrets and st.secrets["client_id"] and st.secrets["client_secret"]:
        cid_loaded = True
except Exception:
    pass

if not cid_loaded:
    cid_env = os.getenv('NAVER_CLIENT_ID', '').strip()
    csec_env = os.getenv('NAVER_CLIENT_SECRET', '').strip()
    if cid_env and csec_env:
        cid_loaded = True

if not cid_loaded:
    st.sidebar.title("🛠️ 네이버 API 설정")
    st.sidebar.warning("⚠️ Secrets 설정 또는 .env 파일에 API 정보가 없습니다. 아래에 입력해 주세요.")
    st.sidebar.text_input(
        "Client ID",
        key="client_id",
        type="password",
        help="네이버 개발자 센터에서 발급받은 Client ID를 입력하세요."
    )
    st.sidebar.text_input(
        "Client Secret",
        key="client_secret",
        type="password",
        help="네이버 개발자 센터에서 발급받은 Client Secret을 입력하세요."
    )
    st.sidebar.markdown("---")
st.sidebar.title("🔍 검색 및 분석 필터")

# 분석 키워드 입력
query_input = st.sidebar.text_input(
    "분석 검색어 (쉼표 ','로 구분)",
    value="네이버,카카오,구글",
    help="트렌드 비교 및 데이터 수집에 사용할 검색어들을 입력해 주세요."
)
keywords = [k.strip() for k in query_input.split(",") if k.strip()]

# 분석 기간 설정
today = datetime.date.today()
three_months_ago = today - datetime.timedelta(days=90)
start_date = st.sidebar.date_input("분석 시작일", value=three_months_ago)
end_date = st.sidebar.date_input("분석 종료일", value=today)

if start_date > end_date:
    st.sidebar.error("시작일이 종료일보다 늦을 수 없습니다.")

st.sidebar.markdown("---")
# 대시보드 페이지 분기 선택
page = st.sidebar.radio(
    "메뉴 선택",
    [
        "🏠 홈 및 사용 가이드",
        "📈 검색어 트렌드 분석",
        "🛍️ 쇼핑 카테고리 트렌드",
        "🔍 검색 데이터 상세 분석"
    ]
)

# API 인증 정보 검증 함수
def check_api_credentials():
    cid = ""
    csec = ""
    
    # 1순위: Streamlit Secrets (배포용 설정)
    try:
        if "naver_api" in st.secrets:
            cid = st.secrets["naver_api"].get("client_id", "")
            csec = st.secrets["naver_api"].get("client_secret", "")
        elif "client_id" in st.secrets:
            cid = st.secrets.get("client_id", "")
            csec = st.secrets.get("client_secret", "")
    except Exception:
        pass
        
    # 2순위: 로컬 환경 변수 (.env 로드값)
    if not cid:
        cid = os.getenv('NAVER_CLIENT_ID', '').strip()
    if not csec:
        csec = os.getenv('NAVER_CLIENT_SECRET', '').strip()
        
    # 3순위: 사이드바 수동 입력값
    if not cid and 'client_id' in st.session_state:
        cid = st.session_state['client_id'].strip()
    if not csec and 'client_secret' in st.session_state:
        csec = st.session_state['client_secret'].strip()
        
    if not cid or not csec:
        st.warning("⚠️ Streamlit Secrets, .env 파일 또는 사이드바에 네이버 API Client ID와 Client Secret을 올바르게 설정해 주세요.")
        return False
        
    # 최종 모듈 주입을 위해 세션 상태 갱신
    st.session_state['client_id'] = cid
    st.session_state['client_secret'] = csec
    return True

# 3. 메인 화면 구성
if page == "🏠 홈 및 사용 가이드":
    st.title("📊 네이버 API 데이터 통합 분석 대시보드")
    st.markdown("본 대시보드는 네이버 OpenAPI를 통해 실시간 트렌드 및 검색 데이터를 수집하고 시각화 분석을 수행하는 비즈니스 인텔리전스 도구입니다.")
    
    # API 연결 상태 확인
    col1, col2 = st.columns(2)
    with col1:
        # Secrets 또는 .env 파일 또는 세션에서 로드된 정보가 유효한지 검증
        cid_loaded = False
        try:
            if ("naver_api" in st.secrets and st.secrets["naver_api"].get("client_id")) or st.secrets.get("client_id"):
                cid_loaded = True
        except Exception:
            pass
        if not cid_loaded:
            cid_loaded = bool(os.getenv('NAVER_CLIENT_ID', '').strip() or st.session_state.get('client_id', '').strip())
            
        if cid_loaded:
            st.success("✅ 네이버 API 인증 정보가 설정되었습니다. (연동 완료)")
        else:
            st.info("ℹ️ 현재 API 인증 정보가 필요합니다. Secrets 설정 또는 .env 파일에 기입하거나 사이드바에 직접 입력해 주세요.")
            
    st.markdown("""
    ### 🚀 주요 제공 기능
    1. **검색어 트렌드 분석**
       - 네이버 통합검색 내 다중 검색어들의 상대적 클릭 트렌드를 실시간 시계열 그래프로 비교 분석합니다.
       - 기간별 최고 검색율이 발생한 시점 및 평균 점유율을 추적합니다.
    2. **쇼핑 카테고리 트렌드**
       - 쇼핑인사이트 API를 활용하여 패션, 가전, 식품 등 주요 쇼핑 분류의 트렌드 변화를 분석합니다.
    3. **검색 데이터 상세 분석**
       - 입력한 핵심 키워드에 대해 네이버 블로그, 카페글, 뉴스, 쇼핑 리스트 데이터를 즉시 수집합니다.
       - 상품 가격 분포(박스플롯), 뉴스 언론사별 보도 비중(파이차트), 콘텐츠 작성자/플랫폼 분포 등을 심층 시각화합니다.

    ### 📖 사용 가이드
    1. [네이버 개발자 센터](https://developers.naver.com/)에 로그인합니다.
    2. **Application > 애플리케이션 등록** 메뉴에서 필요한 API(데이터랩, 검색)를 선택하여 등록합니다.
    3. 발급받은 **Client ID**와 **Client Secret** 키를 사이드바의 입력란에 기입합니다.
    4. 분석할 키워드와 기간을 설정하고 메뉴를 이동하여 분석을 시작하세요!
    """)

elif page == "📈 검색어 트렌드 분석":
    st.title("📈 네이버 검색어 트렌드 분석 (Datalab)")
    
    if check_api_credentials() and start_date <= end_date:
        if not keywords:
            st.warning("최소 한 개 이상의 검색어를 입력해 주세요.")
        else:
            # 트렌드 조사를 위한 변수 준비
            time_unit = st.selectbox("분석 주기", ["date", "week", "month"], index=1, format_func=lambda x: "일간" if x=="date" else "주간" if x=="week" else "월간")
            
            # API 전송 포맷에 맞게 keywordGroups 생성 (최대 5개 제한)
            anal_keywords = keywords[:5]
            if len(keywords) > 5:
                st.info("⚠️ 네이버 검색어 트렌드 API는 최대 5개 키워드 그룹까지만 동시 비교를 지원합니다. 상위 5개 키워드만 비교합니다.")
            
            keyword_groups = [{"groupName": kw, "keywords": [kw]} for kw in anal_keywords]
            
            # API 호출 및 캐싱
            @st.cache_data(show_spinner=False)
            def load_search_trend(cid, csec, s_date, e_date, t_unit, kw_groups):
                return get_search_trend(cid, csec, s_date.strftime("%Y-%m-%d"), e_date.strftime("%Y-%m-%d"), t_unit, kw_groups)
            
            try:
                with st.spinner("네이버 검색어 트렌드 데이터를 수집하는 중..."):
                    df_trend = load_search_trend(
                        st.session_state['client_id'],
                        st.session_state['client_secret'],
                        start_date,
                        end_date,
                        time_unit,
                        keyword_groups
                    )
                
                if df_trend.empty:
                    st.warning("수집된 검색어 트렌드 데이터가 없습니다. 검색어와 기간을 확인해 주세요.")
                else:
                    # Bento Grid 스타일의 KPI 카드 배치
                    st.subheader("🔑 주요 트렌드 지표 (KPI)")
                    cols = st.columns(len(anal_keywords))
                    
                    for i, kw in enumerate(anal_keywords):
                        df_kw = df_trend[df_trend["검색어그룹"] == kw]
                        with cols[i]:
                            if not df_kw.empty:
                                max_ratio = df_kw["검색비율"].max()
                                max_date = df_kw[df_kw["검색비율"] == max_ratio]["날짜"].dt.strftime("%Y-%m-%d").values[0]
                                avg_ratio = df_kw["검색비율"].mean()
                                
                                st.markdown(f"""
                                <div class="metric-card">
                                    <div class="metric-title">{kw} (최대 비율)</div>
                                    <div class="metric-value">{max_ratio:.1f}%</div>
                                    <div class="metric-delta" style="color: #28a745;">📅 {max_date}</div>
                                    <div style="font-size: 0.85rem; color: #6c757d; margin-top: 0.5rem;">평균 비율: {avg_ratio:.1f}%</div>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.write(f"{kw} 데이터 없음")
                    
                    # 시계열 차트 그리기
                    st.subheader("📈 트렌드 흐름 시각화")
                    fig = px.line(
                        df_trend, 
                        x="날짜", 
                        y="검색비율", 
                        color="검색어그룹",
                        title=f"검색어별 상대적 검색 비율 ({start_date} ~ {end_date})",
                        labels={"검색비율": "상대 검색 비율 (%)", "날짜": "기간"},
                        color_discrete_sequence=px.colors.qualitative.Bold
                    )
                    fig.update_layout(
                        hovermode="x unified",
                        plot_bgcolor="white",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#f0f0f0')
                    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#f0f0f0')
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 데이터 테이블 및 다운로드
                    with st.expander("📄 데이터 원본 상세 보기"):
                        st.dataframe(df_trend, use_container_width=True)
                        csv = df_trend.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="📥 CSV 다운로드",
                            data=csv,
                            file_name=f"naver_search_trend_{start_date}_{end_date}.csv",
                            mime="text/csv"
                        )
            
            except Exception as e:
                st.error(f"오류가 발생했습니다: {str(e)}")

elif page == "🛍️ 쇼핑 카테고리 트렌드":
    st.title("🛍️ 쇼핑 카테고리별 클릭 트렌드 (Datalab)")
    
    if check_api_credentials() and start_date <= end_date:
        # 카테고리 맵 정의
        cat_map = {
            "패션의류": "50000000",
            "패션잡화": "50000001",
            "화장품/미용": "50000002",
            "디지털/가전": "50000003",
            "가구/인테리어": "50000004",
            "출산/육아": "50000005",
            "식품": "50000006",
            "스포츠/레저": "50000007",
            "생활/건강": "50000008",
            "여가/생활편의": "50000009",
            "면세점": "50000010",
            "도서": "50005542"
        }
        
        selected_cats = st.multiselect(
            "비교 분석할 쇼핑 카테고리를 선택하세요 (최대 5개)",
            list(cat_map.keys()),
            default=["패션의류", "디지털/가전", "식품"]
        )
        
        if not selected_cats:
            st.warning("최소 한 개 이상의 쇼핑 카테고리를 선택해 주세요.")
        elif len(selected_cats) > 5:
            st.error("최대 5개 카테고리까지만 동시에 비교가 가능합니다.")
        else:
            time_unit = st.selectbox("분석 주기", ["date", "week", "month"], index=1, format_func=lambda x: "일간" if x=="date" else "주간" if x=="week" else "월간")
            
            category_list = [{"name": cat_name, "param": [cat_map[cat_name]]} for cat_name in selected_cats]
            
            @st.cache_data(show_spinner=False)
            def load_shopping_trend(cid, csec, s_date, e_date, t_unit, cat_list):
                return get_shopping_trend(cid, csec, s_date.strftime("%Y-%m-%d"), e_date.strftime("%Y-%m-%d"), t_unit, cat_list)
            
            try:
                with st.spinner("쇼핑 카테고리별 클릭 추이 데이터를 불러오는 중..."):
                    df_shop = load_shopping_trend(
                        st.session_state['client_id'],
                        st.session_state['client_secret'],
                        start_date,
                        end_date,
                        time_unit,
                        category_list
                    )
                    
                if df_shop.empty:
                    st.warning("데이터가 존재하지 않습니다.")
                else:
                    # KPI Bento Grid
                    st.subheader("🔑 카테고리별 클릭 성능 (KPI)")
                    cols = st.columns(len(selected_cats))
                    for i, cat_name in enumerate(selected_cats):
                        df_cat = df_shop[df_shop["카테고리"] == cat_name]
                        with cols[i]:
                            if not df_cat.empty:
                                max_click = df_cat["클릭비율"].max()
                                max_date = df_cat[df_cat["클릭비율"] == max_click]["날짜"].dt.strftime("%Y-%m-%d").values[0]
                                avg_click = df_cat["클릭비율"].mean()
                                
                                st.markdown(f"""
                                <div class="metric-card">
                                    <div class="metric-title">{cat_name} (최대 클릭비율)</div>
                                    <div class="metric-value">{max_click:.1f}%</div>
                                    <div class="metric-delta" style="color: #007bff;">📅 {max_date}</div>
                                    <div style="font-size: 0.85rem; color: #6c757d; margin-top: 0.5rem;">평균 클릭비율: {avg_click:.1f}%</div>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.write(f"{cat_name} 데이터 없음")
                                
                    # Plotly 시계열 차트
                    st.subheader("📈 클릭 트렌드 변화 시각화")
                    fig = px.line(
                        df_shop,
                        x="날짜",
                        y="클릭비율",
                        color="카테고리",
                        title="카테고리별 상대적 쇼핑 클릭 비율",
                        labels={"클릭비율": "상대 클릭 비율 (%)", "날짜": "기간"},
                        color_discrete_sequence=px.colors.qualitative.Dark2
                    )
                    fig.update_layout(
                        hovermode="x unified",
                        plot_bgcolor="white",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#f0f0f0')
                    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#f0f0f0')
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    with st.expander("📄 데이터 원본 상세 보기"):
                        st.dataframe(df_shop, use_container_width=True)
                        csv = df_shop.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="📥 CSV 다운로드",
                            data=csv,
                            file_name=f"naver_shopping_trend_{start_date}_{end_date}.csv",
                            mime="text/csv"
                        )
                        
            except Exception as e:
                st.error(f"오류가 발생했습니다: {str(e)}")

elif page == "🔍 검색 데이터 상세 분석":
    st.title("🔍 네이버 검색 데이터 입체 분석")
    
    if check_api_credentials():
        if not keywords:
            st.warning("분석할 키워드를 입력해 주세요.")
        else:
            # 분석 키워드 선택
            target_query = st.selectbox(
                "상세 분석할 핵심 키워드를 선택하세요",
                keywords,
                help="사이드바에 입력한 키워드 목록 중 하나를 선택해 검색 데이터를 수집합니다."
            )
            
            # 검색 설정
            col1, col2 = st.columns(2)
            with col1:
                display_num = st.slider("수집 데이터 건수", min_value=10, max_value=100, value=50, step=10)
            with col2:
                sort_option = st.selectbox(
                    "정렬 기준", 
                    ["sim", "date"], 
                    format_func=lambda x: "유사도/정확도순" if x=="sim" else "최신 발행일순"
                )
            
            # 4개의 탭 생성
            tab_blog, tab_cafe, tab_news, tab_shop = st.tabs([
                "📝 블로그 분석", 
                "☕ 카페글 분석", 
                "📰 뉴스 보도 분석", 
                "🛒 쇼핑 상품 분석"
            ])
            
            # 캐싱된 검색 함수 정의
            @st.cache_data(show_spinner=False)
            def get_search_data(cid, csec, cat, query, d_num, s_opt):
                return search_naver(cid, csec, cat, query, display=d_num, sort=s_opt)
            
            # ----------------------------------------------------
            # 1. 블로그 분석 탭
            # ----------------------------------------------------
            with tab_blog:
                st.subheader(f"📝 '{target_query}' 블로그 검색 데이터")
                try:
                    with st.spinner("블로그 포스트를 수집하는 중..."):
                        df_blog = get_search_data(
                            st.session_state['client_id'],
                            st.session_state['client_secret'],
                            "blog",
                            target_query,
                            display_num,
                            sort_option
                        )
                        
                    if df_blog.empty:
                        st.info("검색 결과가 존재하지 않습니다.")
                    else:
                        # 1. 시각화 영역
                        col_chart1, col_chart2 = st.columns(2)
                        
                        # 날짜 기준 발행 추이
                        with col_chart1:
                            st.write("📅 **포스트 발행 추이**")
                            df_blog["postdate"] = pd.to_datetime(df_blog["postdate"])
                            df_date = df_blog.groupby("postdate").size().reset_index(name="발행수")
                            fig_date = px.bar(
                                df_date, 
                                x="postdate", 
                                y="발행수",
                                title="일자별 블로그 글 발행수",
                                labels={"postdate": "발행일", "발행수": "게시글 수"}
                            )
                            fig_date.update_layout(plot_bgcolor="white")
                            st.plotly_chart(fig_date, use_container_width=True)
                            
                        # 블로그 채널 점유율
                        with col_chart2:
                            st.write("🗣️ **주요 블로그 출처 점유율**")
                            df_blogger = df_blog["bloggername"].value_counts().reset_index(name="count")
                            df_blogger.columns = ["블로그명", "포스트수"]
                            # 상위 10개 외에는 '기타'로 묶음
                            if len(df_blogger) > 10:
                                top_blogger = df_blogger.head(9)
                                other_count = df_blogger.iloc[9:]["포스트수"].sum()
                                top_blogger = pd.concat([top_blogger, pd.DataFrame([{"블로그명": "기타", "포스트수": other_count}])], ignore_index=True)
                            else:
                                top_blogger = df_blogger
                                
                            fig_pie = px.pie(
                                top_blogger, 
                                values="포스트수", 
                                names="블로그명", 
                                title="상위 블로그 출처 비중"
                            )
                            st.plotly_chart(fig_pie, use_container_width=True)
                            
                        # 데이터 리스트 표기
                        st.write("📄 **수집된 블로그 리스트**")
                        st.dataframe(
                            df_blog[["title_clean", "bloggername", "postdate", "link"]].rename(
                                columns={
                                    "title_clean": "제목",
                                    "bloggername": "블로그 출처",
                                    "postdate": "발행일",
                                    "link": "링크"
                                }
                            ),
                            use_container_width=True
                        )
                        
                except Exception as e:
                    st.error(f"블로그 데이터 수집 오류: {str(e)}")
            
            # ----------------------------------------------------
            # 2. 카페글 분석 탭
            # ----------------------------------------------------
            with tab_cafe:
                st.subheader(f"☕ '{target_query}' 카페 게시글 검색 데이터")
                try:
                    with st.spinner("카페 포스트를 수집하는 중..."):
                        df_cafe = get_search_data(
                            st.session_state['client_id'],
                            st.session_state['client_secret'],
                            "cafearticle",
                            target_query,
                            display_num,
                            sort_option
                        )
                        
                    if df_cafe.empty:
                        st.info("검색 결과가 존재하지 않습니다.")
                    else:
                        # 카페 출처 점유율 시각화
                        st.write("💬 **주요 카페 커뮤니티 출처 비중**")
                        df_cafename = df_cafe["cafename"].value_counts().reset_index(name="count")
                        df_cafename.columns = ["카페명", "게시글수"]
                        if len(df_cafename) > 10:
                            top_cafe = df_cafename.head(9)
                            other_cafe_count = df_cafename.iloc[9:]["게시글수"].sum()
                            top_cafe = pd.concat([top_cafe, pd.DataFrame([{"카페명": "기타", "게시글수": other_cafe_count}])], ignore_index=True)
                        else:
                            top_cafe = df_cafename
                            
                        fig_cafe_pie = px.pie(
                            top_cafe,
                            values="게시글수",
                            names="카페명",
                            title="상위 카페 출처 비중",
                            color_discrete_sequence=px.colors.qualitative.Pastel
                        )
                        st.plotly_chart(fig_cafe_pie, use_container_width=True)
                        
                        # 데이터 표기
                        st.write("📄 **수집된 카페 게시글 리스트**")
                        st.dataframe(
                            df_cafe[["title_clean", "cafename", "link"]].rename(
                                columns={
                                    "title_clean": "제목",
                                    "cafename": "카페 출처",
                                    "link": "링크"
                                }
                            ),
                            use_container_width=True
                        )
                        
                except Exception as e:
                    st.error(f"카페글 데이터 수집 오류: {str(e)}")
                    
            # ----------------------------------------------------
            # 3. 뉴스 보도 분석 탭
            # ----------------------------------------------------
            with tab_news:
                st.subheader(f"📰 '{target_query}' 뉴스 언론사 보도 데이터")
                try:
                    with st.spinner("뉴스 데이터를 수집하는 중..."):
                        df_news = get_search_data(
                            st.session_state['client_id'],
                            st.session_state['client_secret'],
                            "news",
                            target_query,
                            display_num,
                            sort_option
                        )
                        
                    if df_news.empty:
                        st.info("검색 결과가 존재하지 않습니다.")
                    else:
                        # 언론사 도메인 추출 기능 추가
                        def extract_domain(url):
                            try:
                                domain = urlparse(url).netloc
                                return domain.replace("www.", "")
                            except:
                                return "기타"
                                
                        df_news["언론사도메인"] = df_news["originallink"].apply(extract_domain)
                        
                        # 시각화 영역
                        col_news1, col_news2 = st.columns(2)
                        
                        with col_news1:
                            st.write("📅 **뉴스 발행 타임라인**")
                            # 날짜 형식 파싱 (Mon, 26 Sep 2016 07:50:00 +0900 -> yyyy-mm-dd)
                            df_news["pubDate"] = pd.to_datetime(df_news["pubDate"], errors="coerce")
                            df_news_date = df_news.groupby(df_news["pubDate"].dt.date).size().reset_index(name="보도수")
                            fig_news_date = px.bar(
                                df_news_date, 
                                x="pubDate", 
                                y="보도수",
                                title="일자별 뉴스 보도 추이",
                                labels={"pubDate": "보도일", "보도수": "기사 건수"}
                            )
                            st.plotly_chart(fig_news_date, use_container_width=True)
                            
                        with col_news2:
                            st.write("✍️ **언론사 도메인별 보도 비중**")
                            df_domain = df_news["언론사도메인"].value_counts().reset_index(name="count")
                            df_domain.columns = ["도메인", "기사수"]
                            if len(df_domain) > 10:
                                top_domain = df_domain.head(9)
                                other_domain_count = df_domain.iloc[9:]["기사수"].sum()
                                top_domain = pd.concat([top_domain, pd.DataFrame([{"도메인": "기타", "기사수": other_domain_count}])], ignore_index=True)
                            else:
                                top_domain = df_domain
                                
                            fig_news_pie = px.pie(
                                top_domain,
                                values="기사수",
                                names="도메인",
                                title="보도 기사 출처 점유율",
                                color_discrete_sequence=px.colors.qualitative.Safe
                            )
                            st.plotly_chart(fig_news_pie, use_container_width=True)
                            
                        # 데이터 리스트
                        st.write("📄 **수집된 뉴스 기사 리스트**")
                        st.dataframe(
                            df_news[["title_clean", "언론사도메인", "pubDate", "link"]].rename(
                                columns={
                                    "title_clean": "제목",
                                    "언론사도메인": "언론사 도메인",
                                    "pubDate": "보도시간",
                                    "link": "네이버뉴스 링크"
                                }
                            ),
                            use_container_width=True
                        )
                        
                except Exception as e:
                    st.error(f"뉴스 데이터 수집 오류: {str(e)}")
            
            # ----------------------------------------------------
            # 4. 쇼핑 상품 분석 탭
            # ----------------------------------------------------
            with tab_shop:
                st.subheader(f"🛒 '{target_query}' 쇼핑 등록 상품 데이터")
                try:
                    with st.spinner("상품 정보를 수집하는 중..."):
                        df_shop = get_search_data(
                            st.session_state['client_id'],
                            st.session_state['client_secret'],
                            "shopping",
                            target_query,
                            display_num,
                            sort_option
                        )
                        
                    if df_shop.empty:
                        st.info("검색 결과가 존재하지 않습니다.")
                    else:
                        # 가격 수치형 데이터 변환 (lprice, hprice)
                        df_shop["lprice"] = pd.to_numeric(df_shop["lprice"], errors="coerce").fillna(0)
                        df_shop["hprice"] = pd.to_numeric(df_shop["hprice"], errors="coerce").fillna(0)
                        
                        # 쇼핑 시각화 탭 분리
                        shop_tab1, shop_tab2 = st.tabs(["💰 가격 및 시장 분포", "🏪 쇼핑몰 및 제조사 정보"])
                        
                        with shop_tab1:
                            # 1. 가격 분포 분석
                            col_p1, col_p2 = st.columns(2)
                            with col_p1:
                                st.write("📊 **최저가 가격 분포도 (Box Plot)**")
                                fig_box = px.box(
                                    df_shop[df_shop["lprice"] > 0], 
                                    y="lprice", 
                                    points="all",
                                    title="상품 최저가 분포 범위",
                                    labels={"lprice": "최저 가격 (원)"}
                                )
                                st.plotly_chart(fig_box, use_container_width=True)
                                
                            with col_p2:
                                st.write("💸 **최저 가격대 빈도 분포 (Histogram)**")
                                fig_hist = px.histogram(
                                    df_shop[df_shop["lprice"] > 0],
                                    x="lprice",
                                    nbins=20,
                                    title="가격대별 상품 개수",
                                    labels={"lprice": "최저 가격대 (원)", "count": "상품 수"}
                                )
                                fig_hist.update_layout(yaxis_title="상품 수")
                                st.plotly_chart(fig_hist, use_container_width=True)
                                
                            # 초저가 상품 탑 5
                            st.write("🏆 **최저가 상위 5개 상품**")
                            df_cheap = df_shop[df_shop["lprice"] > 0].sort_values("lprice").head(5)
                            st.dataframe(
                                df_cheap[["title_clean", "lprice", "mallName", "link"]].rename(
                                    columns={
                                        "title_clean": "상품명",
                                        "lprice": "최저가",
                                        "mallName": "판매처",
                                        "link": "이동링크"
                                    }
                                ),
                                use_container_width=True
                            )
                            
                        with shop_tab2:
                            # 2. 쇼핑몰 및 제조사
                            col_m1, col_m2 = st.columns(2)
                            with col_m1:
                                st.write("🏪 **주요 입점 쇼핑몰 비중**")
                                df_mall = df_shop["mallName"].value_counts().reset_index(name="count")
                                df_mall.columns = ["쇼핑몰명", "상품수"]
                                if len(df_mall) > 10:
                                    top_mall = df_mall.head(9)
                                    other_mall_count = df_mall.iloc[9:]["상품수"].sum()
                                    top_mall = pd.concat([top_mall, pd.DataFrame([{"쇼핑몰명": "기타", "상품수": other_mall_count}])], ignore_index=True)
                                else:
                                    top_mall = df_mall
                                    
                                fig_mall = px.pie(
                                    top_mall, 
                                    values="상품수", 
                                    names="쇼핑몰명", 
                                    title="판매 쇼핑몰 점유율"
                                )
                                st.plotly_chart(fig_mall, use_container_width=True)
                                
                            with col_m2:
                                st.write("🏭 **주요 제조사 비중**")
                                df_maker = df_shop[df_shop["maker"] != ""]["maker"].value_counts().reset_index(name="count")
                                df_maker.columns = ["제조사명", "상품수"]
                                if df_maker.empty:
                                    st.info("제조사 정보가 비어있습니다.")
                                else:
                                    if len(df_maker) > 10:
                                        top_maker = df_maker.head(9)
                                        other_maker_count = df_maker.iloc[9:]["상품수"].sum()
                                        top_maker = pd.concat([top_maker, pd.DataFrame([{"제조사명": "기타", "상품수": other_maker_count}])], ignore_index=True)
                                    else:
                                        top_maker = df_maker
                                        
                                    fig_maker = px.pie(
                                        top_maker,
                                        values="상품수",
                                        names="제조사명",
                                        title="제조사별 상품 비중"
                                    )
                                    st.plotly_chart(fig_maker, use_container_width=True)
                                    
                        # 상품 전체 리스트 표기
                        st.write("📄 **수집된 쇼핑 상품 전체 리스트**")
                        st.dataframe(
                            df_shop[["title_clean", "lprice", "mallName", "brand", "maker", "link"]].rename(
                                columns={
                                    "title_clean": "상품명",
                                    "lprice": "최저가",
                                    "mallName": "판매처",
                                    "brand": "브랜드",
                                    "maker": "제조사",
                                    "link": "링크"
                                }
                            ),
                            use_container_width=True
                        )
                        
                except Exception as e:
                    st.error(f"쇼핑 데이터 수집 오류: {str(e)}")
