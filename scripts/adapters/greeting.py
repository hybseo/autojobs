# -*- coding: utf-8 -*-
"""
두들린 '그리팅(greetinghr.com)' ATS 수집기.
리크루터를 안 쓰는 중견기업이 많이 씁니다.

  목록  GET https://{code}.career.greetinghr.com/ko
  상세  GET https://{code}.career.greetinghr.com/ko/o/{openingId}

공고 목록 페이지의 이름은 회사마다 다릅니다. guide, apply, intro, home 등
제각각입니다. 그런데 루트 /ko 로 들어가면 어느 페이지로 넘어가든 공고 목록이
함께 실려 옵니다. 그래서 경로를 추측하지 않고 루트만 씁니다.

자체 도메인을 붙인 회사도 있습니다. 현대오토에버가 career.hyundai-autoever.com
을 쓰는데 속은 그리팅입니다. 이런 곳은 companies.json 에 "domain" 을 적어주면
그 주소를 씁니다. 자체 도메인은 robots.txt 도 따로 있으니 추가 전에 확인하세요.

공개 API 가 따로 없어서 페이지 HTML 을 받아옵니다. 다만 HTML 태그를 파싱하는
것이 아니라, Next.js 가 심어두는 <script id="__NEXT_DATA__"> 안의 JSON 을
꺼내 씁니다. 화면 디자인이 바뀌어도 이 JSON 구조는 잘 안 바뀝니다.

robots.txt (2026-08-25 확인)
---------------------------
  User-agent: *
  Allow: /
  Disallow: /o/*/apply, /ko/o/*/apply, /m/*, /a/*
  Content-Signal: search=yes

공고 목록과 상세는 허용, 지원서 경로만 금지입니다. 이 수집기는 /ko/guide 와
/ko/o/{id} 만 읽습니다. 지원 경로(/apply)는 절대 요청하지 마세요.

주의
----
- status 가 "OPEN" 인 것만 접수중입니다.
- dueDate 가 null 인 상시채용 공고가 많습니다. 마감일 없이 그대로 둡니다.
- 한 공고에 여러 직무(openingJobPositions)가 붙을 수 있습니다.
  경력 조건이 서로 다르면 "분야별상이" 로 표시합니다.
"""
import json
import re
import time
import html
import urllib.request

UA = "Mozilla/5.0 (compatible; searchjob.co.kr job aggregator)"

# 그리팅 careerType → 사이트 표기
CAREER = {"EXPERIENCED": "경력", "NEW_COMER": "신입", "NOT_MATTER": "무관"}

NEXT_DATA = re.compile(
    r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def _html(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def _next_data(url):
    m = NEXT_DATA.search(_html(url))
    if not m:
        raise RuntimeError(f"__NEXT_DATA__ 를 찾지 못했습니다: {url}")
    return json.loads(m.group(1))


def _queries(data):
    return (data.get("props", {}).get("pageProps", {})
                .get("dehydratedState", {}).get("queries", []) or [])


def _pick(queries, first_key=None, second_key=None):
    for q in queries:
        k = q.get("queryKey") or []
        if first_key and k and k[0] == first_key:
            return (q.get("state") or {}).get("data")
        if second_key and len(k) > 1 and k[1] == second_key:
            return (q.get("state") or {}).get("data")
    return None


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def _career_label(positions):
    """직무별 경력 조건을 모아 사이트 표기 한 개로 정리합니다."""
    types = set()
    for p in positions or []:
        c = (p or {}).get("jobPositionCareer") or {}
        if c.get("careerType"):
            types.add(c["careerType"])
    if not types:
        return ""
    if types == {"EXPERIENCED", "NEW_COMER"}:
        return "신입/경력"
    if len(types) == 1:
        return CAREER.get(next(iter(types)), "")
    return "분야별상이"


def _location(positions):
    places = []
    for p in positions or []:
        wp = (p or {}).get("workspacePlace") or {}
        loc = wp.get("location") or wp.get("place")
        if loc and loc not in places:
            places.append(loc)
    if not places:
        return ""
    return places[0] if len(places) == 1 else f"{places[0]} 외 {len(places) - 1}곳"


def base_url(company):
    """회사의 채용 사이트 주소. 자체 도메인이 있으면 그것을 씁니다."""
    dom = (company.get("domain") or "").strip()
    if dom:
        return "https://" + dom.split("://")[-1].rstrip("/")
    return f"https://{company['code']}.career.greetinghr.com"


def list_open(company, path=""):
    """접수중 공고 요약 목록. probe 용으로 밖에서도 씁니다.

    path 를 넘기면 그 페이지를 읽습니다. 보통은 비워두고 루트를 씁니다.
    """
    url = base_url(company) + "/ko"
    if path:
        url += "/" + path.lstrip("/")
    data = _next_data(url)
    raw = _pick(_queries(data), first_key="openings")
    if raw is None:
        return []
    # 배열이 아니라 {"0":{...},"1":{...}} 형태로 실려 옵니다.
    rows = list(raw.values()) if isinstance(raw, dict) else list(raw)
    return [r for r in rows if r.get("deploy") is not False]


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    code = company["code"]
    base = base_url(company)

    rows = list_open(company, company.get("path", ""))

    jobs = []
    for r in rows:
        oid = r.get("openingId")
        if not oid:
            continue
        positions = ((r.get("openingJobPosition") or {})
                     .get("openingJobPositions") or [])

        raw = ""
        try:
            d = _next_data(f"{base}/ko/o/{oid}")
            info = ((_pick(_queries(d), second_key="getOpeningById") or {})
                    .get("data") or {}).get("openingsInfo") or {}
            # status 가 OPEN 이 아니면 마감된 공고입니다.
            if info.get("status") and info["status"] != "OPEN":
                continue
            raw = info.get("detail") or ""
        except Exception:
            raw = ""

        text = strip_html(raw)
        # 본문이 이미지뿐이면 세부 직무를 읽을 수 없습니다. 원문으로 보냅니다.
        image_only = len(text) < 50 and "<img" in raw.lower()

        jobs.append({
            "id": f"greeting-{code}-{oid}",
            "unit": "공고",
            "company": name, "companySlug": slug,
            "title": r.get("title") or "",
            "location": _location(positions),
            "career": _career_label(positions),
            "postedAt": (r.get("openDate") or "")[:10],
            "closesAt": (r.get("dueDate") or "")[:10],
            "dday": r.get("deadlineDDay"),
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": f"{base}/ko/o/{oid}",
            "description": raw if not image_only else "",
        })
        time.sleep(0.3)

    return jobs
