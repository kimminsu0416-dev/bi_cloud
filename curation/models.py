"""
키워드 및 네이버 API 사용량 추적을 위한 Django 모델
"""

from django.db import models
from django.utils import timezone
from .constants import DEFAULT_KEYWORDS


class Keyword(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="키워드명")
    order = models.IntegerField(default=0, verbose_name="표시 순서")
    is_active = models.BooleanField(default=True, verbose_name="활성화 여부")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="등록일")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "검색 키워드"
        verbose_name_plural = "검색 키워드 목록"

    def __str__(self):
        return f"[{self.order}] {self.name}"

    @classmethod
    def initialize_defaults(cls):
        """기본 23개 키워드가 없을 경우 순서대로 자동 초기화"""
        for idx, kw in enumerate(DEFAULT_KEYWORDS):
            kw_obj, created = cls.objects.get_or_create(name=kw)
            if created or kw_obj.order == 0:
                kw_obj.order = idx + 1
                kw_obj.save()


class ApiUsage(models.Model):
    """
    네이버 클라우드 API 일별/월별 무료 한도 모니터링 및 과금 방지 모델
    - 일별 무료 한도: 25,000 회/일
    - 월별 무료 한도: 775,000 회/월
    """
    DAILY_LIMIT = 25000
    MONTHLY_LIMIT = 775000

    date = models.DateField(default=timezone.now, unique=True, verbose_name="날짜")
    call_count = models.IntegerField(default=0, verbose_name="당일 호출 횟수")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "API 사용량"
        verbose_name_plural = "API 사용량 기록"

    @classmethod
    def increment_call(cls, count: int = 1):
        """API 호출 시 카운트 증가"""
        today = timezone.localdate()
        usage, _ = cls.objects.get_or_create(date=today)
        usage.call_count += count
        usage.save()
        return usage

    @classmethod
    def get_current_stats(cls):
        """현재 당일 및 당월 사용량 통계 계산"""
        today = timezone.localdate()
        today_usage = cls.objects.filter(date=today).first()
        daily_count = today_usage.call_count if today_usage else 0

        # 당월 전체 합산
        current_year = today.year
        current_month = today.month
        monthly_usages = cls.objects.filter(date__year=current_year, date__month=current_month)
        monthly_count = sum(u.call_count for u in monthly_usages)

        daily_percent = round((daily_count / cls.DAILY_LIMIT) * 100, 2)
        monthly_percent = round((monthly_count / cls.MONTHLY_LIMIT) * 100, 2)

        # 안전 등급: safe (<70%), warning (70~90%), danger (>90%)
        status = "safe"
        if daily_percent >= 90 or monthly_percent >= 90:
            status = "danger"
        elif daily_percent >= 70 or monthly_percent >= 70:
            status = "warning"

        return {
            "daily_count": daily_count,
            "daily_limit": cls.DAILY_LIMIT,
            "daily_remaining": max(0, cls.DAILY_LIMIT - daily_count),
            "daily_percent": daily_percent,
            "monthly_count": monthly_count,
            "monthly_limit": cls.MONTHLY_LIMIT,
            "monthly_remaining": max(0, cls.MONTHLY_LIMIT - monthly_count),
            "monthly_percent": monthly_percent,
            "status": status,
            "today_str": today.strftime("%Y-%m-%d"),
            "month_str": today.strftime("%Y년 %m월"),
        }
