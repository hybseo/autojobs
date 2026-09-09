# -*- coding: utf-8 -*-
"""
넷마블컴퍼니 채용 사이트 수집기.

목록  GET https://career.netmarble.com/api/v1/apply/announces?page=1&size=1000
상세  GET https://career.netmarble.com/api/v1/apply/announces/{carAnnoId}/view

인증 토큰은 필요 없습니다(마이페이지류 API 만 401). 대신 함정이 두 개
있으니 반드시 지킬 것.

함정 1 — 넷마블은 하나의 회사가 아닙니다
career.netmarble.com 은 넷마블 단독이 아니라 넷마블네오·넷마블몬스터·
넷마블에프앤씨 등 여러 계열사 공고를 한 사이트에서 같이 보여줍니다.
목록 API 응답의 companyNm 이 이미 계열사명까지 정확히 구분해 주므로
(다우기술 comNm 버그와 달리 이 값은 신뢰할 수 있습니다), company 필드에
companyNm 을 그대로 씁니다. companySlug 는 companies.json 에 등록한
넷마블 그룹 통합 슬러그 하나로 고정합니다(recruiter.py 의 HL그룹
splitByTitle 과 같은 발상 — 회사명만 계열사별로 쪼개고 페이지는 하나).

함정 2 — endDate 만으로 마감을 판단하면 안 됩니다
상시채용 공고는 endDate 가 "2999-12-31 23:59:59" 로 옵니다. 이 값을
그대로 closesAt 에 넣으면 화면에 엉뚱한 마감일이 찍힙니다.
isUnlimitedEndDate 가 true 면 마감일 없음(빈 문자열)으로 둡니다.
dday 필드는 API 가 주지 않으므로 계산해서 지어내지 않고 None 으로
둡니다(README 방침: 모르면 비워두고 지어내지 않는다).

career 매핑에 대하여
--------------------
reqTypeNm 값은 "신입"/"경력"/"공통" 세 가지를 확인했습니다. "공통"은
경력무관 채용이라는 뜻이라 "무관"으로 옮깁니다. entTypeNm("정규직"/
"계약직")은 고용형태이지 경력구분이 아니므로 career 에 쓰지 않습니다.

본문에 대하여
------------
상세 API 의 annoContents 는 회사에 따라 순수 HTML 텍스트인 경우와
이미지 카드 나열뿐인 경우가 섞여 있습니다(2026-09 확인 시 넷마블네오
쪽 공고 하나가 img 태그만으로 구성됨). recruiter.py 와 같은 기준으로
텍스트가 사실상 없으면 multiRole=True 로 표시하고 description 은
비웁니다.
"""

import html
import json
import re
import time
import urllib.error
import urllib.request

BASE = "https://career.netmarble.com"

# reqTypeNm → 사이트 career 필터 값. 모르는 값은 "무관"으로 접습니다.
CAREER = {"신입": "신입", "경력": "경력", "공통": "무관"}


def _get(path, params=None):
    """일시적 실패(타임아웃·연결오류)만 몇 초 쉬었다 재시도합니다.
    4xx/5xx 는 재시도하지 않습니다.
    """
    url = BASE + path
    if params:
        from urllib.parse import urlencode

        url += "?" + urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    last = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.load(resp)
        except urllib.error.HTTPError:
            raise
        except Exception as e:
            last = e
            time.sleep(2)
    raise last


def _career(req_type_nm):
    return CAREER.get((req_type_nm or "").strip(), "무관")


def strip_html(raw):
    text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    text = re.sub(r"</(p|div|li|tr|h\d)>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{2,}", "\n", html.unescape(text)).strip()


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    slug = company["slug"]

    data = _get("/api/v1/apply/announces", {"page": 1, "size": 1000})
    rows = data.get("content") or []

    jobs = []
    for row in rows:
        car_anno_id = row.get("carAnnoId")
        jid = f"netmarble-{car_anno_id}"

        posted_at = (row.get("staDate") or "")[:10]
        is_unlimited = bool(row.get("isUnlimitedEndDate"))
        closes_at = "" if is_unlimited else (row.get("endDate") or "")[:10]

        try:
            detail = _get(f"/api/v1/apply/announces/{car_anno_id}/view")
            raw = detail.get("annoContents") or ""
        except Exception:
            raw = ""

        text_only = strip_html(raw)
        # 본문이 이미지 카드뿐인 공고는 세부 직무를 읽을 수 없습니다.
        # 억지로 분해하지 않고 원문으로 보냅니다.
        image_only = len(text_only) < 30 and "<img" in raw.lower()

        jobs.append(
            {
                "id": jid,
                "unit": "공고",
                "company": row.get("companyNm") or company["name"],
                "companySlug": slug,
                "title": row.get("annoSubject") or "",
                "location": "",  # 이 API 는 근무지 필드를 주지 않습니다.
                "career": _career(row.get("reqTypeNm")),
                "postedAt": posted_at,
                "closesAt": closes_at,
                "dday": None,  # API 가 주지 않아 지어내지 않습니다.
                "multiRole": image_only,
                "sourceTitle": "",
                "sourceUrl": f"{BASE}/announce/view?anno_id={car_anno_id}",
                # 본문이 있으면 상세 페이지와 JobPosting 스키마가 생성됩니다.
                "description": raw if not image_only else "",
            }
        )
        time.sleep(0.2)

    return jobs
