import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import urllib3
import requests
from dotenv import load_dotenv
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.cache import cache

# SSL 인증서 검증 비활성화 경고 억제
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 프로젝트 루트 경로
BASE_DIR = Path(__file__).resolve().parent.parent

# 한국수출입은행 환율 API 엔드포인트
KOREAEXIM_API_URL = "https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON"

# 캐시 키 및 유효 시간 (초) - 15분
CACHE_KEY_EXCHANGE = "koreaexim_exchange_rates_v1"
CACHE_TIMEOUT = 900

# 비즈니스 우선 통화 정렬 순서 (USD, JPY, EUR, CNH 등)
PRIORITY_CURRENCIES = [
    "USD", "JPY(100)", "EUR", "CNH", "GBP", 
    "AUD", "CAD", "CHF", "SGD", "HKD",
    "NZD", "THB", "VND(100)", "INR", "TWD"
]

# API 키 부재 또는 외부 통신 전면 실패 시 비즈니스 연속성을 위한 기준 샘플 데이터
FALLBACK_SAMPLE_DATA = [
    {"cur_unit": "USD", "cur_nm": "미국 달러", "deal_bas_r": "1,335.50", "ttb": "1,322.14", "tts": "1,348.86", "bkpr": "1,335"},
    {"cur_unit": "JPY(100)", "cur_nm": "일본 100엔", "deal_bas_r": "895.40", "ttb": "886.44", "tts": "904.36", "bkpr": "895"},
    {"cur_unit": "EUR", "cur_nm": "유로", "deal_bas_r": "1,452.80", "ttb": "1,438.27", "tts": "1,467.33", "bkpr": "1,452"},
    {"cur_unit": "CNH", "cur_nm": "위안화", "deal_bas_r": "184.20", "ttb": "182.35", "tts": "186.05", "bkpr": "184"},
    {"cur_unit": "GBP", "cur_nm": "영국 파운드", "deal_bas_r": "1,712.30", "ttb": "1,695.17", "tts": "1,729.43", "bkpr": "1,712"},
    {"cur_unit": "AUD", "cur_nm": "호주 달러", "deal_bas_r": "882.10", "ttb": "873.27", "tts": "890.93", "bkpr": "882"},
    {"cur_unit": "CAD", "cur_nm": "캐나다 달러", "deal_bas_r": "985.60", "ttb": "975.74", "tts": "995.46", "bkpr": "985"},
    {"cur_unit": "CHF", "cur_nm": "스위스 프랑", "deal_bas_r": "1,520.40", "ttb": "1,505.19", "tts": "1,535.61", "bkpr": "1,520"},
    {"cur_unit": "SGD", "cur_nm": "싱가포르 달러", "deal_bas_r": "1,015.20", "ttb": "1,005.04", "tts": "1,025.36", "bkpr": "1,015"},
    {"cur_unit": "HKD", "cur_nm": "홍콩 달러", "deal_bas_r": "171.30", "ttb": "169.58", "tts": "173.02", "bkpr": "171"},
]


def fetch_exchange_rates(api_key: str):
    """
    한국수출입은행 API를 호출하여 최신 고시 환율 데이터를 조회합니다.
    - 한국 시간(KST) 기준으로 당일 11시 이전 또는 주말/공휴일인 경우 최근 영업일을 역추적합니다.
    - result == 1 인 정상 고시 데이터만 필터링합니다.
    """
    kst = ZoneInfo("Asia/Seoul")
    now_kst = datetime.now(kst)
    
    # 오전 11시 이전에는 당일 환율이 아직 미고시 상태일 수 있으므로
    # 당일 11시 이전이면 전일부터 역추적 시작
    start_offset = 0
    if now_kst.hour < 11:
        start_offset = 0  # 11시 전이라도 당일 혹시 조기 고시되었을 수 있으므로 당일부터 시도하되 빠르게 전일로 전환
        
    max_lookup_days = 10  # 연휴 대비 최대 10일까지 영업일 역추적
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "BI-CLOUD-SaaS/2.4 (Ethan Labs; Enterprise Financial Intelligence)",
        "Accept": "application/json",
    })
    
    for day_offset in range(start_offset, start_offset + max_lookup_days):
        target_date = now_kst - timedelta(days=day_offset)
        
        # 주말(토: 5, 일: 6)인 경우 건너뛰어 불필요한 API 호출 낭비 방지
        if target_date.weekday() in (5, 6):
            continue
            
        search_date_str = target_date.strftime("%Y%m%d")
        display_date_str = target_date.strftime("%Y년 %m월 %d일")
        
        params = {
            "authkey": api_key,
            "searchdate": search_date_str,
            "data": "AP01",
        }
        
        try:
            response = session.get(
                KOREAEXIM_API_URL,
                params=params,
                verify=False,
                timeout=4,
            )
            
            if response.status_code == 200:
                response.encoding = 'utf-8'
                data = response.json()
                
                # 데이터 유효성 정밀 검증 (result == 1 인지 확인)
                if isinstance(data, list) and len(data) > 0:
                    first_item = data[0]
                    # result 값이 1(성공)인 데이터만 취급
                    if first_item.get("result") == 1 and first_item.get("cur_unit"):
                        return data, display_date_str, False
        except Exception:
            continue
            
    return [], now_kst.strftime("%Y년 %m월 %d일"), True


def sort_rates_by_priority(rate_items: list) -> list:
    """
    대표님 및 비즈니스 사용자가 가장 자주 찾는 핵심 통화(USD, JPY, EUR, CNH 등)를 
    상단에 우선 배치하고 나머지는 통화코드 순으로 정렬합니다.
    """
    priority_map = {unit: idx for idx, unit in enumerate(PRIORITY_CURRENCIES)}
    
    def get_sort_key(item):
        unit = item.get("cur_unit", "")
        # 우선순위 목록에 있으면 해당 인덱스, 없으면 999 + 통화코드
        if unit in priority_map:
            return (0, priority_map[unit])
        return (1, unit)
        
    return sorted(rate_items, key=get_sort_key)


@login_required
def index(request):
    """
    실시간 환율 조회 및 스마트 양방향 환전 계산기 대시보드 뷰
    - 캐싱 레이어로 0.01초 초고속 렌더링
    - '?refresh=1' 파라미터 시 실시간 강제 갱신 지원
    """
    load_dotenv(BASE_DIR / '.env', override=True)
    api_key = os.getenv("EXCHANGE_API_KEY") or os.getenv("API_KEY", "").strip()
    force_refresh = request.GET.get("refresh") == "1"
    
    rates = []
    query_date = datetime.now().strftime("%Y년 %m월 %d일")
    is_sample = False
    error_message = None
    
    if not api_key:
        rates = FALLBACK_SAMPLE_DATA
        is_sample = True
        error_message = "한국수출입은행 API Key가 설정되지 않아 비즈니스 샘플 데이터를 표시 중입니다."
    else:
        # 캐시 확인 (강제 새로고침이 아닐 때)
        cached_result = cache.get(CACHE_KEY_EXCHANGE) if not force_refresh else None
        
        if cached_result and not force_refresh:
            rates_data, found_date, is_empty = cached_result
        else:
            rates_data, found_date, is_empty = fetch_exchange_rates(api_key)
            if not is_empty and rates_data:
                cache.set(CACHE_KEY_EXCHANGE, (rates_data, found_date, is_empty), timeout=CACHE_TIMEOUT)
                
        query_date = found_date
        
        if is_empty or not rates_data:
            rates = FALLBACK_SAMPLE_DATA
            is_sample = True
            error_message = "최근 영업일의 수출입은행 고시 환율을 불러올 수 없어 기준 데이터를 표시합니다."
        else:
            rates = rates_data
            is_sample = False
            error_message = None
            
    # 데이터 정제 및 타입 변환
    cleaned_rates = []
    for item in rates:
        raw_rate = str(item.get("deal_bas_r", "0")).replace(",", "")
        try:
            rate_val = float(raw_rate)
        except ValueError:
            rate_val = 0.0
            
        cur_unit = item.get("cur_unit", "")
        unit_multiplier = 100 if "(100)" in cur_unit else 1
        
        cleaned_rates.append({
            "cur_unit": cur_unit,
            "cur_nm": item.get("cur_nm", ""),
            "deal_bas_r": item.get("deal_bas_r", "-"),
            "ttb": item.get("ttb", "-"),
            "tts": item.get("tts", "-"),
            "bkpr": item.get("bkpr", "-"),
            "rate_val": rate_val,
            "unit_multiplier": unit_multiplier,
        })

    # 비즈니스 핵심 통화 우선순위 스마트 정렬
    cleaned_rates = sort_rates_by_priority(cleaned_rates)

    context = {
        "rates": cleaned_rates,
        "query_date": query_date,
        "is_sample": is_sample,
        "error_message": error_message,
        "has_data": len(cleaned_rates) > 0,
        "active_tab": "exchange",
    }
    
    return render(request, "exchange/index.html", context)

