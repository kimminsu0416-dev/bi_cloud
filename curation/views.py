"""
AI 뉴스 큐레이션 Views 및 실시간 API 사용량 모니터링
"""

import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import Keyword, ApiUsage
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
