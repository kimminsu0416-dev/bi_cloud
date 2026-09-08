"""
AI 뉴스 큐레이션 Views 및 실시간 API 사용량 모니터링
"""

import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import Keyword, ApiUsage, SavedArticle
from .services.curator import curate_news_feed


from django.contrib.auth.decorators import login_required


@login_required
def index(request):
    """
    메인 큐레이션 대시보드 뷰 (키워드 및 실시간 API 사용량 포함)
    """
    if Keyword.objects.count() == 0:
        Keyword.initialize_defaults()

    keywords = list(Keyword.objects.filter(is_active=True).order_by("order", "id").values_list("name", flat=True))
    has_naver_key = bool(settings.NAVER_CLIENT_ID and settings.NAVER_CLIENT_SECRET)
    has_gemini_key = bool(settings.GEMINI_API_KEY)
    usage_stats = ApiUsage.get_current_stats()

    context = {
        "keywords": keywords,
        "keywords_json": json.dumps(keywords, ensure_ascii=False),
        "has_naver_key": has_naver_key,
        "has_gemini_key": has_gemini_key,
        "usage_stats": usage_stats,
        "usage_stats_json": json.dumps(usage_stats, ensure_ascii=False),
        "active_tab": "news",
    }
    return render(request, "curation/index.html", context)



def api_usage_stats(request):
    """
    실시간 네이버 API 무료 한도 및 사용량 조회 API
    """
    stats = ApiUsage.get_current_stats()
    return JsonResponse({"success": True, "data": stats})


@csrf_exempt
def api_curate(request):
    """
    뉴스 큐레이션 비동기 API 엔드포인트
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST 요청만 지원합니다."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        data = {}

    mode = data.get("mode", "default")
    keywords = data.get("keywords", [])
    filter_prompt = data.get("filter_prompt", "").strip()
    count_per_keyword = int(data.get("count_per_keyword", 2))
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    if mode == "default" and not keywords:
        keywords = list(Keyword.objects.filter(is_active=True).order_by("order", "id").values_list("name", flat=True))

    if not keywords:
        return JsonResponse({"error": "검색할 키워드를 1개 이상 선택하거나 입력해주세요."}, status=400)

    try:
        feed_data = curate_news_feed(
            keywords=keywords,
            filter_prompt=filter_prompt,
            count_per_keyword=count_per_keyword,
            start_date=start_date,
            end_date=end_date
        )
        latest_usage = ApiUsage.get_current_stats()

        return JsonResponse({
            "success": True,
            "mode": mode,
            "filter_prompt": filter_prompt,
            "start_date": start_date,
            "end_date": end_date,
            "data": feed_data,
            "usage": latest_usage
        })
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": f"뉴스 수집 및 요약 중 오류가 발생했습니다: {str(e)}"
        }, status=500)



@csrf_exempt
def api_keywords(request):
    """
    키워드 목록 조회 및 신규 키워드 추가 API
    """
    if request.method == "GET":
        keywords = list(Keyword.objects.all().order_by("order", "id").values("id", "name", "order", "is_active", "created_at"))
        for kw in keywords:
            kw["created_at"] = kw["created_at"].strftime("%Y-%m-%d %H:%M")
        return JsonResponse({"success": True, "keywords": keywords})

    elif request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
        except Exception:
            data = {}
        
        name = data.get("name", "").strip()
        if not name:
            return JsonResponse({"success": False, "error": "키워드 이름을 입력해주세요."}, status=400)

        if Keyword.objects.filter(name=name).exists():
            return JsonResponse({"success": False, "error": "이미 등록되어 있는 키워드입니다."}, status=400)

        max_order = Keyword.objects.count() + 1
        kw = Keyword.objects.create(name=name, order=max_order)
        return JsonResponse({
            "success": True,
            "keyword": {
                "id": kw.id,
                "name": kw.name,
                "order": kw.order,
                "is_active": kw.is_active,
                "created_at": kw.created_at.strftime("%Y-%m-%d %H:%M")
            }
        })

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def api_keywords_reorder(request):
    """
    키워드 순서 일괄 업데이트 API
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            ordered_ids = data.get("ordered_ids", [])
        except Exception:
            ordered_ids = []

        if not ordered_ids:
            return JsonResponse({"success": False, "error": "순서 정보가 전달되지 않았습니다."}, status=400)

        for index, kw_id in enumerate(ordered_ids):
            Keyword.objects.filter(id=kw_id).update(order=index + 1)

        keywords = list(Keyword.objects.all().order_by("order", "id").values("id", "name", "order", "is_active", "created_at"))
        for kw in keywords:
            kw["created_at"] = kw["created_at"].strftime("%Y-%m-%d %H:%M")

        return JsonResponse({
            "success": True,
            "message": "키워드 우선순위가 성공적으로 저장되었습니다.",
            "keywords": keywords
        })

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def api_keyword_detail(request, keyword_id):
    """
    키워드 삭제 API
    """
    if request.method == "DELETE":
        kw = get_object_or_404(Keyword, id=keyword_id)
        kw_name = kw.name
        kw.delete()
        return JsonResponse({"success": True, "message": f"'{kw_name}' 키워드가 삭제되었습니다."})

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def api_keywords_reset(request):
    """
    기본 23개 키워드로 초기화 및 복원 API
    """
    if request.method == "POST":
        Keyword.objects.all().delete()
        Keyword.initialize_defaults()
        keywords = list(Keyword.objects.all().order_by("order", "id").values("id", "name", "order", "is_active", "created_at"))
        for kw in keywords:
            kw["created_at"] = kw["created_at"].strftime("%Y-%m-%d %H:%M")
        return JsonResponse({
            "success": True,
            "message": "기본 23개 키워드로 초기화되었습니다.",
            "keywords": keywords
        })

    return JsonResponse({"error": "Method not allowed"}, status=405)


def api_settings_status(request):
    """
    API 키 설정 상태 확인 API
    """
    has_naver_key = bool(settings.NAVER_CLIENT_ID and settings.NAVER_CLIENT_SECRET)
    has_gemini_key = bool(settings.GEMINI_API_KEY)
    return JsonResponse({
        "has_naver_key": has_naver_key,
        "has_gemini_key": has_gemini_key,
    })


@login_required
def archive_view(request):
    """
    저장된 기사 아카이브 대시보드 뷰
    """
    keywords = list(SavedArticle.objects.values_list("keyword", flat=True).distinct())
    articles = SavedArticle.objects.all().order_by("-created_at")
    total_count = articles.count()

    context = {
        "articles": articles,
        "keywords": sorted(keywords),
        "total_count": total_count,
        "active_tab": "archive",
    }
    return render(request, "curation/archive.html", context)


@csrf_exempt
@login_required
def api_save_article(request):
    """
    기사 아카이브 저장 API (토글 지원)
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"success": False, "error": "유효하지 않은 요청 데이터입니다."}, status=400)

        origin_url = data.get("origin_url", "").strip()
        title = data.get("title", "").strip()
        keyword = data.get("keyword", "").strip() or "기타"
        press = data.get("press", "").strip()
        published_at = data.get("published_at", "").strip()
        summary_points = data.get("summary_points", [])
        business_implication = data.get("business_implication", "").strip()
        raw_content = data.get("raw_content", "").strip()
        memo = data.get("memo", "").strip()

        if not origin_url or not title:
            return JsonResponse({"success": False, "error": "기사 제목과 원문 링크는 필수입니다."}, status=400)

        # 중복 체크: 이미 저장된 기사가 있는지 확인
        existing = SavedArticle.objects.filter(origin_url=origin_url).first()
        if existing:
            # action이 'toggle'이고 이미 있으면 삭제
            if data.get("action") == "toggle":
                existing.delete()
                return JsonResponse({
                    "success": True,
                    "saved": False,
                    "message": "기사 저장이 취소(삭제)되었습니다."
                })
            else:
                # 정보 업데이트
                existing.summary_points = summary_points or existing.summary_points
                existing.business_implication = business_implication or existing.business_implication
                if memo:
                    existing.memo = memo
                existing.save()
                return JsonResponse({
                    "success": True,
                    "saved": True,
                    "article_id": existing.id,
                    "message": "기존 저장된 기사 정보가 업데이트되었습니다."
                })

        # 신규 저장
        article = SavedArticle.objects.create(
            user=request.user if request.user.is_authenticated else None,
            keyword=keyword,
            title=title,
            origin_url=origin_url,
            press=press,
            published_at=published_at,
            summary_points=summary_points,
            business_implication=business_implication,
            raw_content=raw_content,
            memo=memo,
        )

        return JsonResponse({
            "success": True,
            "saved": True,
            "article_id": article.id,
            "message": f"'{title[:20]}...' 기사가 아카이브에 성공적으로 저장되었습니다."
        })

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
@login_required
def api_delete_article(request, article_id):
    """
    저장된 기사 삭제 API
    """
    if request.method in ["POST", "DELETE"]:
        article = get_object_or_404(SavedArticle, id=article_id)
        title = article.title
        article.delete()
        return JsonResponse({
            "success": True,
            "message": f"'{title[:20]}...' 기사가 아카이브에서 삭제되었습니다."
        })

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
@login_required
def api_update_article_memo(request, article_id):
    """
    저장된 기사의 메모 수정 API
    """
    if request.method == "POST":
        article = get_object_or_404(SavedArticle, id=article_id)
        try:
            data = json.loads(request.body.decode("utf-8"))
            memo = data.get("memo", "").strip()
        except Exception:
            memo = ""

        article.memo = memo
        article.save(update_fields=["memo"])
        return JsonResponse({
            "success": True,
            "message": "메모가 성공적으로 저장되었습니다.",
            "memo": article.memo
        })

    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required
def api_saved_articles_list(request):
    """
    저장된 기사 JSON 목록 (키워드/검색 필터 지원)
    """
    keyword_filter = request.GET.get("keyword", "").strip()
    query = request.GET.get("q", "").strip()

    qs = SavedArticle.objects.all()
    if keyword_filter:
        qs = qs.filter(keyword=keyword_filter)
    if query:
        qs = qs.filter(
            models.Q(title__icontains=query) |
            models.Q(business_implication__icontains=query) |
            models.Q(memo__icontains=query)
        )

    articles = []
    for a in qs.order_by("-created_at"):
        articles.append({
            "id": a.id,
            "keyword": a.keyword,
            "title": a.title,
            "origin_url": a.origin_url,
            "press": a.press,
            "published_at": a.published_at,
            "summary_points": a.summary_points,
            "business_implication": a.business_implication,
            "memo": a.memo,
            "created_at": a.created_at.strftime("%Y-%m-%d %H:%M"),
        })

    return JsonResponse({
        "success": True,
        "count": len(articles),
        "articles": articles
    })


@csrf_exempt
@login_required
def api_check_saved_urls(request):
    """
    여러 URL의 저장 여부를 일괄 확인하는 API
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            urls = data.get("urls", [])
        except Exception:
            urls = []

        saved_urls = list(SavedArticle.objects.filter(origin_url__in=urls).values_list("origin_url", flat=True))
        return JsonResponse({
            "success": True,
            "saved_urls": saved_urls
        })

    return JsonResponse({"error": "Method not allowed"}, status=405)

