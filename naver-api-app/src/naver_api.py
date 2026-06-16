"""
이 모듈은 네이버 OpenAPI(데이터랩 통합 검색어 트렌드, 쇼핑인사이트, 검색 API)와 통신하여
데이터를 수집하고 Pandas DataFrame 형태로 변환하는 기능을 제공합니다.

주요 기능:
- 네이버 데이터랩 통합 검색어 트렌드 조회
- 네이버 데이터랩 쇼핑인사이트 분야별 트렌드 조회
- 블로그, 카페글, 뉴스, 쇼핑 검색 API 호출 및 HTML 태그 정제
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
