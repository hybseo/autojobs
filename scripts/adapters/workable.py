# -*- coding: utf-8 -*-
"""
Workable ATS 수집기. 해외 ATS 로, 국내에서는 스타트업·의료AI 쪽이 씁니다.
루닛이 이걸 씁니다.

목록  POST https://apply.workable.com/api/v3/accounts/{code}/jobs
상세  GET  https://apply.workable.com/api/v1/accounts/{code}/jobs/{shortcode}
원문  https://apply.workable.com/{code}/j/{shortcode}/

채용 사이트가 화면을 그릴 때 쓰는 것과 같은 경로입니다. 인증은 필요 없습니다.

Workday 와 헷갈리지 마세요
--------------------------
이름이 비슷하지만 전혀 다른 시스템입니다. 이 저장소에는 workday.py 가
따로 있습니다.

    Workable  apply.workable.com      스타트업이 많이 씁니다
    Workday   *.myworkdayjobs.com     외국계 대기업이 씁니다

code 는 무엇인가
----------------
Workable 채용 사이트 주소의 회사 부분입니다.

    https://apply.workable.com/lunit/  →  code = "lunit"

함정 1 — 페이징이 토큰 방식입니다
---------------------------------
한 번에 10건씩 옵니다. page 번호가 아니라 응답의 nextPage 를 다음 요청
본문에 token 으로 넣어야 다음 쪽이 옵니다. 이걸 안 하면 10건만 받고
끝나서, 18건짜리 회사가 10건으로 보입니다.

nextPage 가 없으면 마지막 쪽입니다.

함정 2 — 목록에 본문이 없습니다
-------------------------------
목록은 제목·근무지·부서까지만 줍니다. 본문은 상세를 따로 읽어야 합니다.
게다가 한 덩어리가 아니라 셋으로 나뉘어 옵니다.

    description   직무 소개
    requirements  자격 요건
    benefits      복리후생

아래 _body() 가 이 셋을 순서대로 이어 붙입니다. 셋 다 HTML 입니다.

한국 공고만 담습니다
--------------------
location.countryCode 로 나라를 정확히 알 수 있습니다. 문자열을 뒤져
지명을 찾을 필요가 없어 Workday·Greenhouse 어댑터보다 깔끔합니다.

2026-09-09 루닛 기준 18건 중 1건이 일본(JP) 이었습니다.
해외까지 원하면 companies.json 에 "overseas": true 를 넣으세요.

인재풀을 제외합니다
-------------------
"Talent Pool (인재풀 등록)" 같은 상시 접수 창구가 섞여 있습니다.
실제 자리가 아니라 이력서를 받아두는 것이라 기본으로 제외합니다.
Ashby 어댑터와 같은 방침입니다. 담고 싶으면 "includePool": true 를 넣으세요.

응답 구조 (2026-09-09 실제 확인)
--------------------------------
{ "total": 18, "results": [ ... ], "nextPage": "토큰" }

    shortcode   9A3D9AA456     공고 번호. 원문 주소에 들어갑니다
    title                      공고 제목
    department  Research       부서
    location    {country, countryCode, city, region}
    state       published      게시 상태
    published   2026-09-03T00:00:00.000Z
    type        full           고용형태
    workplace   on_site        근무 형태
"""
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://apply.workable.com/api/v3/accounts/{}/jobs"
DETAIL_API = "https://apply.workable.com/api/v1/accounts/{}/jobs/{}"
SITE = "https://apply.workable.com/{}/j/{}/"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

MAX_PAGES = 30  # 안전장치. 300건이면 충분합니다.

# 이력서만 받아두는 창구. 실제 채용 공고가 아닙니다.
POOL = re.compile(r"talent\s*pool|인재\s*풀|인재\s*pool|인재\s*등록", re.I)

# 고용형태 → 화면 표기. Workable 은 신입/경력을 구분해 주지 않습니다.
EMPLOYMENT = {"full": "정규직", "part": "파트타임", "contract": "계약직",
              "temporary": "임시직", "internship": "인턴"}


def _post(code, body):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다."""
    req = urllib.request.Request(
        API.format(urllib.parse.quote(code)), method="POST",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json",
                 "User-Agent": UA})
    last = None
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError:
            raise
        except Exception as e:
            last = e
            if i < 2:
                time.sleep(2 + i * 2)
    raise last


def _get(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def _body(d):
    """description + requirements + benefits 를 한 덩어리로 잇습니다."""
    out = []
    for key, label in (("description", ""),
                       ("requirements", "자격 요건"),
                       ("benefits", "복리후생")):
        v = (d.get(key) or "").strip()
        if not v:
            continue
        if label:
            out.append(f"<h3>{label}</h3>")
        out.append(v)
    return "\n".join(out)


def _is_korea(row):
    loc = row.get("location") or {}
    cc = (loc.get("countryCode") or "").upper()
    if cc:
        return cc == "KR"
    # 나라 코드가 없으면 나라 이름으로 봅니다.
    return "korea" in (loc.get("country") or "").lower()


def _location(row):
    loc = row.get("location") or {}
    city = (loc.get("city") or "").strip()
    region = (loc.get("region") or "").strip()
    if city and region and city != region:
        return f"{city}, {region}"
    return city or region or ""


def _date(v):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(v or ""))
    return m.group(0) if m else ""


def list_open(code, overseas=False, include_pool=False):
    """공개된 공고 목록. probe 용으로 밖에서도 씁니다.

    nextPage 토큰을 따라가며 전부 받습니다.
    """
    rows, token = [], None
    for _ in range(MAX_PAGES):
        body = {"query": "", "location": [], "department": [],
                "worktype": [], "remote": []}
        if token:
            body["token"] = token
        j = _post(code, body)
        got = j.get("results") or []
        rows += got
        token = j.get("nextPage")
        if not token or not got:
            break
        time.sleep(0.3)

    if not rows:
        print(f"  ! workable({code}): 공고를 찾지 못했습니다. "
              f"code 값이 맞는지 확인하세요.")
        return []

    # 게시중인 것만.
    rows = [x for x in rows
            if (x.get("state") or "published") == "published"
            and not x.get("isInternal")]

    if not include_pool:
        rows = [x for x in rows
                if not POOL.search(f"{x.get('title','')} {x.get('department','')}")]

    if overseas:
        return rows

    kept = [x for x in rows if _is_korea(x)]
    if rows and not kept:
        seen = sorted({(x.get("location") or {}).get("country") or "?"
                       for x in rows})
        print(f"  ! workable({code}): 한국 근무지로 인식된 공고가 없습니다. "
              f"받은 나라: {seen[:8]}")
    return kept


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    code = company["code"]

    rows = list_open(code,
                     overseas=bool(company.get("overseas")),
                     include_pool=bool(company.get("includePool")))

    jobs = []
    for x in rows:
        sc = x.get("shortcode")
        if not sc:
            continue

        raw = ""
        try:
            d = _get(DETAIL_API.format(urllib.parse.quote(code), sc))
            raw = _body(d)
        except Exception:
            raw = ""
        time.sleep(0.3)

        text = strip_html(raw)
        # 본문이 이미지뿐이면 세부 직무를 읽을 수 없습니다. 원문으로 보냅니다.
        image_only = len(text) < 50 and "<img" in raw.lower()

        # 정규직이 아니면 제목에 표시합니다.
        title = (x.get("title") or "").strip()
        emp = EMPLOYMENT.get((x.get("type") or "").lower(), "")
        if emp and emp != "정규직" and emp not in title:
            title = f"{title} ({emp})"

        jobs.append({
            "id": f"workable-{code}-{sc}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            "title": title,
            "location": _location(x),
            # Workable 은 신입/경력을 구분해 주지 않습니다. 지어내지 않습니다.
            "career": "무관",
            "postedAt": _date(x.get("published")),
            # 마감일을 주지 않습니다. 상시채용으로 표시됩니다.
            "closesAt": "",
            "dday": None,
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": SITE.format(urllib.parse.quote(code), sc),
            "description": raw if not image_only else "",
        })

    return jobs
