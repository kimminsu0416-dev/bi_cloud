from django.test import TestCase, Client
from django.urls import reverse
import json
from curation.models import Keyword


class NewsCurationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        Keyword.initialize_defaults()

    def test_index_page(self):
        """메인 대시보드 페이지 로드 테스트"""
        response = self.client.get(reverse('curation:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI News")
        self.assertContains(response, "Desktop 가상화")

    def test_api_keywords_crud_and_reorder(self):
        """키워드 조회, 순서 변경, 추가, 삭제, 리셋 API 테스트"""
        # 1. 목록 조회
        get_res = self.client.get(reverse('curation:api_keywords'))
        self.assertEqual(get_res.status_code, 200)
        keywords = get_res.json()["keywords"]
        self.assertEqual(len(keywords), 23)

        # 2. 순서 변경 (Reorder) 테스트: 맨 뒤의 키워드를 맨 앞으로 이동
        first_id = keywords[0]["id"]
        last_id = keywords[-1]["id"]
        reordered_ids = [last_id] + [k["id"] for k in keywords[:-1]]
        
        reorder_res = self.client.post(
            reverse('curation:api_keywords_reorder'),
            data=json.dumps({"ordered_ids": reordered_ids}),
            content_type="application/json"
        )
        self.assertEqual(reorder_res.status_code, 200)
        new_ordered_kws = reorder_res.json()["keywords"]
        self.assertEqual(new_ordered_kws[0]["id"], last_id)

        # 3. 신규 키워드 추가
        add_res = self.client.post(
            reverse('curation:api_keywords'),
            data=json.dumps({"name": "양자암호보안"}),
            content_type="application/json"
        )
        self.assertEqual(add_res.status_code, 200)
        new_kw = add_res.json()["keyword"]
        self.assertEqual(new_kw["name"], "양자암호보안")

        # 4. 키워드 삭제
        del_res = self.client.delete(reverse('curation:api_keyword_detail', args=[new_kw["id"]]))
        self.assertEqual(del_res.status_code, 200)
        self.assertFalse(Keyword.objects.filter(name="양자암호보안").exists())

        # 5. 키워드 초기화
        reset_res = self.client.post(reverse('curation:api_keywords_reset'))
        self.assertEqual(reset_res.status_code, 200)
        self.assertEqual(len(reset_res.json()["keywords"]), 23)

    def test_api_curate_with_date_range(self):
        """날짜 범위 필터링이 포함된 큐레이션 API 테스트"""
        payload = {
            "mode": "default",
            "keywords": ["VDI", "DaaS"],
            "filter_prompt": "보안 규제 중심 요약",
            "count_per_keyword": 2,
            "start_date": "2026-08-01",
            "end_date": "2026-09-01"
        }
        response = self.client.post(
            reverse('curation:api_curate'),
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("start_date"), "2026-08-01")
        self.assertEqual(data.get("end_date"), "2026-09-01")
        self.assertEqual(len(data["data"]["results"]), 2)
