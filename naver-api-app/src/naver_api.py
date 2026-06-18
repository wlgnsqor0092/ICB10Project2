"""
이 모듈은 네이버 OpenAPI(데이터랩 통합 검색어 트렌드, 쇼핑인사이트, 검색 API)와 통신하여
데이터를 수집하고 Pandas DataFrame 형태로 변환하는 기능을 제공합니다.

주요 기능:
- 네이버 데이터랩 통합 검색어 트렌드 조회
- 네이버 데이터랩 쇼핑인사이트 분야별 트렌드 조회
- 블로그, 카페글, 뉴스, 쇼핑 검색 API 호출 및 HTML 태그 정제
- ThreadPoolExecutor를 사용한 다중 검색어 및 다중 채널(뉴스, 블로그, 카페) 병렬 검색 데이터 수집
- 가벼운 텍스트 처리를 통한 단어 빈도 분석(한국어 불용어 필터링 지원)
"""
import requests
import pandas as pd

def get_headers(client_id, client_secret):
    """
    네이버 API 호출을 위한 인증 헤더를 반환합니다.
    """
    return {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
        "Content-Type": "application/json"
    }

def get_search_trend(client_id, client_secret, start_date, end_date, time_unit, keyword_groups):
    """
    네이버 데이터랩 통합 검색어 트렌드 API를 호출하여 DataFrame으로 반환합니다.
    """
    url = "https://openapi.naver.com/v1/datalab/search"
    headers = get_headers(client_id, client_secret)
    
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": time_unit,
        "keywordGroups": keyword_groups
    }
    
    response = requests.post(url, headers=headers, json=body)
    
    if response.status_code != 200:
        raise Exception(f"검색어 트렌드 API 호출 실패 (상태 코드: {response.status_code}): {response.text}")
        
    res_data = response.json()
    results = res_data.get("results", [])
    
    records = []
    for group in results:
        title = group.get("title")
        data_points = group.get("data", [])
        for dp in data_points:
            records.append({
                "날짜": dp.get("period"),
                "검색어그룹": title,
                "검색비율": dp.get("ratio")
            })
            
    if not records:
        return pd.DataFrame(columns=["날짜", "검색어그룹", "검색비율"])
        
    df = pd.DataFrame(records)
    df["날짜"] = pd.to_datetime(df["날짜"])
    return df

def get_shopping_trend(client_id, client_secret, start_date, end_date, time_unit, category_list):
    """
    네이버 데이터랩 쇼핑인사이트 분야별 트렌드 API를 호출하여 DataFrame으로 반환합니다.
    """
    url = "https://openapi.naver.com/v1/datalab/shopping/categories"
    headers = get_headers(client_id, client_secret)
    
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": time_unit,
        "category": category_list
    }
    
    response = requests.post(url, headers=headers, json=body)
    
    if response.status_code != 200:
        raise Exception(f"쇼핑 트렌드 API 호출 실패 (상태 코드: {response.status_code}): {response.text}")
        
    res_data = response.json()
    results = res_data.get("results", [])
    
    records = []
    for cat in results:
        title = cat.get("title")
        data_points = cat.get("data", [])
        for dp in data_points:
            records.append({
                "날짜": dp.get("period"),
                "카테고리": title,
                "클릭비율": dp.get("ratio")
            })
            
    if not records:
        return pd.DataFrame(columns=["날짜", "카테고리", "클릭비율"])
        
    df = pd.DataFrame(records)
    df["날짜"] = pd.to_datetime(df["날짜"])
    return df

def search_naver(client_id, client_secret, category, query, display=30, start=1, sort="sim"):
    """
    네이버 검색 API(블로그, 카페글, 뉴스, 쇼핑)를 호출하여 DataFrame으로 반환합니다.
    """
    # 쇼핑 검색 API만 엔드포인트명이 'shop'이고 나머지는 해당 카테고리명을 사용함
    api_name = "shop" if category == "shopping" else category
    url = f"https://openapi.naver.com/v1/search/{api_name}.json"
    
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    
    params = {
        "query": query,
        "display": display,
        "start": start,
        "sort": sort
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code != 200:
        raise Exception(f"{category} 검색 API 호출 실패 (상태 코드: {response.status_code}): {response.text}")
        
    res_data = response.json()
    items = res_data.get("items", [])
    
    if not items:
        return pd.DataFrame()
        
    df = pd.DataFrame(items)
    
    # HTML 태그 제거 및 텍스트 정리 함수
    def clean_html(text):
        if not isinstance(text, str):
            return text
        # <b>, </b> 및 &quot; 등 간단한 태그와 엔티티 정리
        import re
        text = re.sub(r'<[^>]*>', '', text)
        text = text.replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        return text

    # 데이터 정제
    if "title" in df.columns:
        df["title_clean"] = df["title"].apply(clean_html)
    if "description" in df.columns:
        df["description_clean"] = df["description"].apply(clean_html)
        
    return df

def fetch_all_channels(client_id, client_secret, queries, categories=["news", "blog", "cafearticle"], display=30, sort="sim"):
    """
    여러 검색어(queries)와 카테고리(categories) 조합에 대하여
    ThreadPoolExecutor를 이용해 병렬로 네이버 검색 API를 호출하고 통합 DataFrame을 반환합니다.
    """
    from concurrent.futures import ThreadPoolExecutor
    results = []
    
    # 병렬 호출을 위한 내부 작업 함수
    def fetch_single(query, category):
        try:
            df = search_naver(client_id, client_secret, category, query, display=display, sort=sort)
            if not df.empty:
                df["검색어"] = query
                df["채널"] = "뉴스" if category == "news" else "블로그" if category == "blog" else "카페"
                return df
        except Exception as e:
            # 개별 API 오류 시 전체 프로세스가 중단되지 않도록 로깅 후 빈 df 반환
            import streamlit as st
            st.warning(f"⚠️ API 호출 실패 ({query} - {category}): {str(e)}")
        return pd.DataFrame()

    # 스레드 풀 실행 (최대 스레드 수 10개)
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for q in queries:
            for cat in categories:
                futures.append(executor.submit(fetch_single, q, cat))
        
        for future in futures:
            df_res = future.result()
            if not df_res.empty:
                results.append(df_res)
                
    if not results:
        return pd.DataFrame()
        
    return pd.concat(results, ignore_index=True)

def analyze_word_frequency(texts, top_n=10):
    """
    수집된 텍스트 목록(texts)에 대하여 형태소 분석기 없이 가벼운 단어 빈도 분석을 수행합니다.
    공백 기준으로 나눈 뒤 2글자 이상인 단어만 필터링하며, 내장된 불용어(조사 등) 리스트를 제거합니다.
    """
    import re
    from collections import Counter
    
    # 기본 한국어 불용어 (조사, 접속사, 지시어 등)
    stopwords = {
        "그리고", "하지만", "그러나", "그래서", "또한", "따라서", "이러한", "대한", "대해",
        "위해", "통해", "통하여", "의해", "대해서", "위해서", "통해서", "의해서", "것입니다", "있는",
        "하는", "할", "수", "있습니다", "없습니다", "합니다", "입니다", "그", "이", "저",
        "것", "때문", "때문에", "가장", "매우", "정말", "진짜", "많이", "조금", "특히",
        "우선", "먼저", "모든", "어떤", "이것", "그것", "저것", "의", "을", "를", "은", "는",
        "이", "가", "에", "게", "과", "와", "로", "으로", "에서", "에게", "한테", "까지",
        "부터", "마저", "조차", "마냥", "보다", "더", "하고", "이며", "라며", "하고", "등",
        "및", "혹은", "또는", "기타", "포함", "관련", "현재", "최근", "오늘", "내일", "어제",
        "이번", "지난", "다음", "바로", "다시", "모두", "함께", "같이", "서로", "매일", "자주"
    }
    
    words = []
    for text in texts:
        if not isinstance(text, str):
            continue
        # 정규식을 이용해 한글, 영문, 숫자 외 기호 및 특수문자 제거
        clean_text = re.sub(r'[^a-zA-Z0-9가-힣\s]', ' ', text)
        for word in clean_text.split():
            # 단어 끝에 붙은 조사 간단 제거 (은/는/이/가/을/를/에/의/로/으로/와/과/에서 등)
            word = re.sub(r'(은|는|이|가|을|를|에|의|로|으로|와|과|에서|에게|한테|까지|부터)$', '', word)
            word = word.strip()
            
            # 2글자 이상이고 불용어에 포함되지 않는 단어 필터링
            if len(word) >= 2 and word not in stopwords:
                words.append(word)
                
    counter = Counter(words)
    return counter.most_common(top_n)
