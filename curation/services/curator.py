"""
뉴스 검색 및 AI 큐레이션 종합 오케스트레이터
- 100% 실제 기사만 처리 (허위/데모 기사 생성 절대 금지)
- 기사가 없는 키워드는 '해당 기간중 기사가 없습니다.' 상태로 명확히 반환
"""

from concurrent.futures import ThreadPoolExecutor
from .naver_service import search_naver_news
from .gemini_service import summarize_news_with_gemini
from django.conf import settings


def process_single_keyword(
    keyword: str,
    filter_prompt: str = "",
    count_per_keyword: int = 2,
    start_date: str = None,
    end_date: str = None
) -> dict:
    """
    단일 키워드에 대해 실제 네이버 뉴스 검색 및 Gemini AI 요약 수행
    - 기사가 없는 경우 '해당 기간중 기사가 없습니다.' 메시지 반환
    """
    cleaned_keyword = keyword.strip()
    if not cleaned_keyword:
        return {"keyword": keyword, "articles": [], "status": "empty", "message": "키워드가 비어있습니다."}

    search_result = search_naver_news(
        cleaned_keyword,
        display_count=count_per_keyword,
        start_date=start_date,
        end_date=end_date
    )

    # 기사가 없거나 검색 실패한 경우
    if not search_result["success"] or not search_result["items"]:
        return {
            "keyword": cleaned_keyword,
            "articles": [],
            "status": "no_articles",
            "message": "해당 기간중 기사가 없습니다."
        }

    raw_articles = search_result["items"]

    # 각 실존 기사별 Gemini 맞춤 요약 수행
    curated_articles = []
    for item in raw_articles:
        ai_summary = summarize_news_with_gemini(item, filter_prompt=filter_prompt)
        curated_articles.append({
            "title": item["title"],
            "description": item["description"],
            "link": item["link"],
            "pub_date": item["pub_date"],
            "keyword": cleaned_keyword,
            "summary_points": ai_summary["summary_points"],
            "is_ai_generated": ai_summary["is_ai_generated"],
            "is_mock": False,
        })


    return {
        "keyword": cleaned_keyword,
        "articles": curated_articles,
        "status": "success",
        "is_mock": False
    }


def curate_news_feed(
    keywords: list[str],
    filter_prompt: str = "",
    count_per_keyword: int = 2,
    start_date: str = None,
    end_date: str = None
) -> dict:
    """
    여러 키워드에 대한 뉴스 병렬 큐레이션 수집 및 요약
    - 기사가 없는 키워드도 '해당 기간중 기사가 없습니다' 상태로 포함하여 투명하게 전달
    """
    results = []
    # 입력 순서 유지를 위한 dict
    keyword_order = [kw.strip() for kw in keywords if kw.strip()]
    results_map = {}

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_kw = {
            executor.submit(process_single_keyword, kw, filter_prompt, count_per_keyword, start_date, end_date): kw
            for kw in keyword_order
        }
        for future in future_to_kw:
            kw = future_to_kw[future]
            try:
                res = future.result()
                results_map[kw] = res
            except Exception as e:
                results_map[kw] = {
                    "keyword": kw,
                    "articles": [],
                    "status": "no_articles",
                    "message": "해당 기간중 기사가 없습니다."
                }

    for kw in keyword_order:
        if kw in results_map:
            results.append(results_map[kw])

    has_naver_key = bool(settings.NAVER_CLIENT_ID and settings.NAVER_CLIENT_SECRET)
    has_gemini_key = bool(settings.GEMINI_API_KEY)

    total_articles = sum(len(r.get("articles", [])) for r in results)
    active_keywords_count = sum(1 for r in results if r.get("articles"))

    return {
        "results": results,
        "total_keywords": len(results),
        "active_keywords_count": active_keywords_count,
        "total_articles": total_articles,
        "api_status": {
            "has_naver_key": has_naver_key,
            "has_gemini_key": has_gemini_key
        }
    }
