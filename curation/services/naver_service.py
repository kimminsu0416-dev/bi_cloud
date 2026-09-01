"""
네이버 뉴스 검색 API 연동, 엄격한 100% 키워드 일치 필터링 및 사용량 자동 계측 서비스
"""

import html
import re
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup
from django.conf import settings
from ..models import ApiUsage


def clean_html(text: str) -> str:
    """HTML 특수문자 및 태그 제거"""
    if not text:
        return ""
    unescaped = html.unescape(text)
    soup = BeautifulSoup(unescaped, "html.parser")
    cleaned = soup.get_text()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def parse_pub_date(pub_date_str: str):
    """RFC 822 날짜 포맷을 datetime 객체로 파싱"""
    if not pub_date_str:
        return None
    try:
        return datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
    except Exception:
        return None


def format_pub_date(dt: datetime, fallback_str: str = "") -> str:
    """datetime 객체를 YYYY-MM-DD HH:MM 문자열로 변환"""
    if dt:
        return dt.strftime("%Y-%m-%d %H:%M")
    return fallback_str


def sanitize_key(val: str) -> str:
    """API 키의 따옴표 및 공백 안전 제거"""
    if not val:
        return ""
    val = val.strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        val = val[1:-1].strip()
    return val


def get_keyword_variants(keyword: str) -> list[str]:
    """키워드 일치 검사를 위한 핵심 단어 목록 추출"""
    kw = keyword.strip()
    variants = [kw.lower()]

    match = re.match(r"^(.*?)\s*\((.*?)\)$", kw)
    if match:
        part1 = match.group(1).strip().lower()
        part2 = match.group(2).strip().lower()
        if part1:
            variants.append(part1)
        if part2:
            variants.append(part2)

    if "소프트" in kw and " " not in kw:
        variants.append(kw.replace("소프트", " 소프트").lower())
    if "브로드밴드" in kw and " " not in kw:
        variants.append(kw.replace("브로드밴드", " 브로드밴드").lower())
    if "시큐리티" in kw and " " not in kw:
        variants.append(kw.replace("시큐리티", " 시큐리티").lower())

    return list(set(variants))


def is_keyword_strictly_matched(title: str, description: str, keyword: str) -> bool:
    """기사 제목 또는 내용에 키워드가 100% 엄격하게 포함되어 있는지 검증"""
    full_text = (title + " " + description).lower()
    clean_target = re.sub(r"[^\w\s]", " ", full_text)
    clean_target_nospace = clean_target.replace(" ", "")

    variants = get_keyword_variants(keyword)
    for var in variants:
        var_lower = var.lower()
        var_nospace = var_lower.replace(" ", "")
        
        if var_lower in full_text:
            return True
        if len(var_nospace) >= 2 and var_nospace in clean_target_nospace:
            return True

    return False


def search_naver_news(
    keyword: str,
    display_count: int = 2,
    sort: str = "date",
    start_date: str = None,
    end_date: str = None
):
    """
    네이버 뉴스 검색 API 호출, 무료 한도 체크, 날짜 필터링 및 100% 키워드 일치 선별
    """
    client_id = sanitize_key(settings.NAVER_CLIENT_ID)
    client_secret = sanitize_key(settings.NAVER_CLIENT_SECRET)

    if not client_id or not client_secret:
        return {
            "success": False,
            "error": "NAVER_API_KEY_MISSING",
            "message": ".env 파일에 NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET을 설정해주세요.",
            "items": []
        }

    # 과금 방지 안전 장치: 일일 25,000회 초과 여부 확인
    stats = ApiUsage.get_current_stats()
    if stats["daily_count"] >= stats["daily_limit"]:
        return {
            "success": False,
            "error": "DAILY_LIMIT_EXCEEDED",
            "message": "과금 방지를 위해 오늘의 무료 한도(25,000회)에서 검색이 안전하게 중단되었습니다.",
            "items": []
        }

    raw_kw = keyword.strip()
    search_query = f'"{raw_kw}"' if " " in raw_kw else raw_kw
    
    if "(" in raw_kw and ")" in raw_kw:
        search_query = re.sub(r"\(.*?\)", "", raw_kw).strip()

    fetch_count = 100

    kst = timezone(timedelta(hours=9))
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0, tzinfo=kst)
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=kst)
        except ValueError:
            pass

    api_configs = [
        {
            "url": "https://naverapihub.apigw.ntruss.com/search/v1/news",
            "headers": {
                "X-NCP-APIGW-API-KEY-ID": client_id,
                "X-NCP-APIGW-API-KEY": client_secret,
            }
        },
        {
            "url": "https://openapi.naver.com/v1/search/news.json",
            "headers": {
                "X-Naver-Client-Id": client_id,
                "X-Naver-Client-Secret": client_secret,
            }
        }
    ]

    params = {
        "query": search_query,
        "display": fetch_count,
        "start": 1,
        "sort": sort,
    }

    last_error = ""

    for cfg in api_configs:
        try:
            response = requests.get(cfg["url"], headers=cfg["headers"], params=params, timeout=10)
            
            # API 호출 성공 시 사용량 카운트 1 증가
            ApiUsage.increment_call(1)

            if response.status_code == 200:
                data = response.json()
                raw_items = data.get("items", [])
                items = []
                
                for item in raw_items:
                    title = clean_html(item.get("title", ""))
                    description = clean_html(item.get("description", ""))
                    link = item.get("originallink") or item.get("link", "")
                    
                    if not link or not (link.startswith("http://") or link.startswith("https://")):
                        continue

                    if not is_keyword_strictly_matched(title, description, keyword):
                        continue

                    pub_raw = item.get("pubDate", "")
                    dt = parse_pub_date(pub_raw)
                    if dt:
                        if start_dt and dt < start_dt:
                            continue
                        if end_dt and dt > end_dt:
                            continue

                    pub_date_formatted = format_pub_date(dt, fallback_str=pub_raw)
                    
                    items.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "pub_date": pub_date_formatted,
                        "keyword": keyword,
                    })

                    if len(items) >= display_count:
                        break
                    
                return {
                    "success": True,
                    "items": items,
                    "error": None
                }
            else:
                last_error = f"HTTP {response.status_code}"
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            continue

    return {
        "success": False,
        "error": "NAVER_API_ERROR",
        "message": f"네이버 API 호출 실패: {last_error}",
        "items": []
    }
