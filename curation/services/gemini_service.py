"""
Google Gemini API 기반 뉴스 요약 및 큐레이션 서비스
"""

import json
from django.conf import settings
from google import genai
from google.genai import types


def summarize_news_with_gemini(news_item: dict, filter_prompt: str = "") -> dict:
    """
    뉴스 기사를 Gemini API를 통해 맞춤 요약하는 함수
    :param news_item: {'title': str, 'description': str, 'keyword': str, 'link': str, 'pub_date': str}
    :param filter_prompt: 사용자가 지정한 필터링/요약 관점 프롬프트 (예: "보안 이슈 위주", "경쟁사 동향 파악")
    :return: dict (summary_points: list[str], insight: str, is_ai_generated: bool)
    """
    api_key = settings.GEMINI_API_KEY

    # API 키가 설정되지 않은 경우 fallback 기본 요약 반환
    if not api_key:
        desc = news_item.get("description", "")
        # 마침표 기준으로 간이 분할
        sentences = [s.strip() for s in desc.split(".") if len(s.strip()) > 5]
        fallback_points = sentences[:3] if sentences else [desc]
        return {
            "summary_points": fallback_points,
            "insight": "💡 .env 파일에 GEMINI_API_KEY를 등록하시면 실시간 AI 심층 요약 및 시사점 분석이 제공됩니다.",
            "is_ai_generated": False
        }

    client = genai.Client(api_key=api_key.strip())

    title = news_item.get("title", "")
    description = news_item.get("description", "")
    keyword = news_item.get("keyword", "")

    # 프롬프트 구성
    filter_instruction = ""
    if filter_prompt and filter_prompt.strip():
        filter_instruction = f"""
[사용자 특별 필터링 & 분석 지침]:
"{filter_prompt.strip()}"
위 사용자 지침/관점을 철저히 반영하여, 해당 관점에서 중요한 내용 위주로 요약하고 시사점을 도출하십시오.
"""

    prompt = f"""
당신은 IT 엔터프라이즈 및 클라우드/보안 분야의 최고 전략 요약 전문가입니다.
아래 제공된 뉴스 기사를 분석하여 핵심 사실과 주요 내용을 정확하고 명확한 3줄 요약 문장으로 정리해주세요.

[기사 정보]
- 관련 키워드: {keyword}
- 기사 제목: {title}
- 기사 내용 요약: {description}
{filter_instruction}

[작성 규칙]
1. summary_points: 기사의 핵심 사실을 3개의 한국어 문장(개조식/명사형 종결 또는 깔끔한 문장)으로 요약.
2. 반드시 아래 JSON 포맷으로만 응답할 것:

{{
  "summary_points": [
    "첫 번째 핵심 사실 요약",
    "두 번째 핵심 사실 요약",
    "세 번째 핵심 사실 요약"
  ]
}}
"""

    candidate_models = ["gemini-2.5-flash", "gemini-1.5-flash"]
    
    for model_name in candidate_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                )
            )
            
            response_text = response.text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
                
            data = json.loads(response_text.strip())
            
            return {
                "summary_points": data.get("summary_points", [description]),
                "is_ai_generated": True
            }
        except Exception:
            continue

    return {
        "summary_points": [news_item.get("description", "")],
        "is_ai_generated": False
    }

