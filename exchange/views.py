import os
from datetime import datetime, timedelta
from pathlib import Path
import urllib3
import requests
from dotenv import load_dotenv
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# SSL 인증서 검증 비활성화 경고 억제
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 프로젝트 루트 경로
BASE_DIR = Path(__file__).resolve().parent.parent

# 한국수출입은행 환율 API 엔드포인트
KOREAEXIM_API_URL = "https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON"

# API 키가 없거나 통신 실패 시 제공하는 샘플 데이터
FALLBACK_SAMPLE_DATA = [
    {"cur_unit": "USD", "cur_nm": "미국 달러", "deal_bas_r": "1,335.50", "ttb": "1,322.14", "tts": "1,348.86", "bkpr": "1,335"},
    {"cur_unit": "EUR", "cur_nm": "유로", "deal_bas_r": "1,452.80", "ttb": "1,438.27", "tts": "1,467.33", "bkpr": "1,452"},
    {"cur_unit": "JPY(100)", "cur_nm": "일본 100엔", "deal_bas_r": "895.40", "ttb": "886.44", "tts": "904.36", "bkpr": "895"},
    {"cur_unit": "CNH", "cur_nm": "위안화", "deal_bas_r": "184.20", "ttb": "182.35", "tts": "186.05", "bkpr": "184"},
    {"cur_unit": "GBP", "cur_nm": "영국 파운드", "deal_bas_r": "1,712.30", "ttb": "1,695.17", "tts": "1,729.43", "bkpr": "1,712"},
    {"cur_unit": "AUD", "cur_nm": "호주 달러", "deal_bas_r": "882.10", "ttb": "873.27", "tts": "890.93", "bkpr": "882"},
    {"cur_unit": "CAD", "cur_nm": "캐나다 달러", "deal_bas_r": "985.60", "ttb": "975.74", "tts": "995.46", "bkpr": "985"},
    {"cur_unit": "CHF", "cur_nm": "스위스 프랑", "deal_bas_r": "1,520.40", "ttb": "1,505.19", "tts": "1,535.61", "bkpr": "1,520"},
    {"cur_unit": "HKD", "cur_nm": "홍콩 달러", "deal_bas_r": "171.30", "ttb": "169.58", "tts": "173.02", "bkpr": "171"},
    {"cur_unit": "SGD", "cur_nm": "싱가포르 달러", "deal_bas_r": "1,015.20", "ttb": "1,005.04", "tts": "1,025.36", "bkpr": "1,015"},
]


def fetch_exchange_rates(api_key: str):
    """
    한국수출입은행 API를 호출하여 최신 고시 환율 데이터를 조회합니다.
    (당일 오전 11시 이전 또는 주말/공휴일인 경우 최근 영업일 데이터를 자동 역추적)
    """
    today = datetime.now()
    max_lookup_days = 7  # 최대 7일 전까지 영업일 역추적
    
    for day_offset in range(max_lookup_days):
        target_date = today - timedelta(days=day_offset)
        search_date_str = target_date.strftime("%Y%m%d")
        display_date_str = target_date.strftime("%Y년 %m월 %d일")
        
        params = {
            "authkey": api_key,
            "searchdate": search_date_str,
            "data": "AP01",
        }
        
        try:
            response = requests.get(
                KOREAEXIM_API_URL,
                params=params,
                verify=False,
                timeout=5,
            )
            
            if response.status_code == 200:
                response.encoding = 'utf-8'
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    return data, display_date_str, False
        except Exception:
            continue
            
    return [], today.strftime("%Y년 %m월 %d일"), True


@login_required
def index(request):
    """
    실시간 환율 조회 및 외화/원화 스마트 환전 계산기 대시보드 뷰
    """
    load_dotenv(BASE_DIR / '.env', override=True)
    api_key = os.getenv("EXCHANGE_API_KEY") or os.getenv("API_KEY", "").strip()
    
    rates = []
    query_date = datetime.now().strftime("%Y년 %m월 %d일")
    is_sample = False
    error_message = None
    
    if not api_key:
        rates = FALLBACK_SAMPLE_DATA
        is_sample = True
        error_message = ".env 파일에 한국수출입은행 API_KEY가 설정되지 않아 샘플 데이터로 표시 중입니다."
    else:
        rates_data, found_date, is_empty = fetch_exchange_rates(api_key)
        query_date = found_date
        
        if is_empty or not rates_data:
            rates = FALLBACK_SAMPLE_DATA
            is_sample = True
            error_message = "최근 영업일의 환율 데이터를 불러올 수 없어 샘플 데이터를 표시합니다. API 키를 확인해 주세요."
        else:
            rates = rates_data
            is_sample = False
            error_message = None
            
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

    context = {
        "rates": cleaned_rates,
        "query_date": query_date,
        "is_sample": is_sample,
        "error_message": error_message,
        "has_data": len(cleaned_rates) > 0,
        "active_tab": "exchange",
    }
    
    return render(request, "exchange/index.html", context)
