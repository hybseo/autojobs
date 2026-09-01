# -*- coding: utf-8 -*-
"""
Breezy HR 수집기. 해외 ATS 로, 국내에서는 외국계·스타트업이 씁니다.

  목록·본문  GET https://{code}.breezy.hr/json?verbose=true

회사 채용 사이트가 그대로 내주는 공개 JSON 입니다. 인증이 필요 없습니다.
verbose=true 를 붙이면 본문까지 한 번에 옵니다. 요청 1회로 끝납니다.

주의: api.breezy.hr 쪽 v3 API 는 인증이 필요합니다. 여기서 쓰는 것은
채용 사이트가 공개로 내주는 경로이고, 로그인 없이 누구나 보는 데이터입니다.

code 는 무엇인가
----------------
채용 사이트 주소의 회사 부분입니다.

  https://bear-robotics.breezy.hr/  →  code = "bear-robotics"

한국 공고만 담습니다
--------------------
Breezy 를 쓰는 회사는 해외 공고를 함께 올립니다. 베어로보틱스만 해도
미국 본사 공고가 섞여 있습니다. 기본은 한국 근무지만 담고,
해외까지 원하면 companies.json 에 "overseas": true 를 넣으세요.

만들 때의 한계
--------------
응답 필드 이름을 실제로 확인하지 못한 채 작성했습니다. Breezy 문서와
알려진 구조를 따랐고, 필드를 못 찾으면 무엇을 받았는지 로그에 남깁니다.
첫 실행 로그를 확인하고 FIELD 표를 실제 이름으로 고치세요.
"""
import json
import re
import html
import urllib.parse
import urllib.request

API = "https://{}.breezy.hr/json?verbose=true"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

KOREA = re.compile(
    r"korea|대한민국|한국"
    r"|서울|seoul|부산|busan|대구|daegu|인천|incheon|광주|gwangju"
    r"|대전|daejeon|울산|ulsan|세종|sejong"
    r"|경기|gyeonggi|판교|pangyo|성남|seongnam|수원|suwon|용인|화성|평택|안산"
    r"|천안|cheonan|아산|청주|전주|포항|구미|창원|제주|jeju", re.I)

# 응답 필드 이름 후보. 실제 이름이 확인되면 맨 앞으로 옮기고 나머지는 지우세요.
FIELD = {
    "id":    ("id", "_id", "friendly_id"),
    "title": ("name", "title", "position_name"),
    "body":  ("description", "content", "job_description"),
    "url":   ("url", "absolute_url", "apply_url"),
    "date":  ("published_date", "creation_date", "updated_date", "published_at"),
}


def _pick(row, key):
    for name in FIELD[key]:
        v = row.get(name)
        if v not in (None, "", []):
            return v
    return ""


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


def _location(row):
    """근무지. 문자열일 수도 중첩 객체일 수도 있습니다."""
    loc = row.get("location")
    if isinstance(loc, str):
        return loc.strip()
    if isinstance(loc, dict):
        city = (loc.get("city") or "").strip()
        country = loc.get("country")
        if isinstance(country, dict):
            country = country.get("name") or country.get("id") or ""
        country = str(country or "").strip()
        return ", ".join(x for x in (city, country) if x)
    return ""


def _date(v):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(v or ""))
    return m.group(0) if m else ""


def list_open(code, overseas=False):
    """공개된 공고 목록. probe 용으로 밖에서도 씁니다."""
    data = _get(API.format(urllib.parse.quote(code)))
    # 최상위가 배열인 경우와 {"positions":[...]} 인 경우가 모두 보고됩니다.
    rows = data if isinstance(data, list) else (
        data.get("positions") or data.get("jobs") or [])
    if not rows:
        print(f"      ! breezy({code}): 공고를 찾지 못했습니다. "
              f"응답 앞부분: {str(data)[:200]}")
        return []
    if overseas:
        return rows
    kept = [x for x in rows if KOREA.search(_location(x))]
    if rows and not kept:
        seen = sorted({_location(x) or "?" for x in rows})[:8]
        print(f"      ! breezy({code}): 한국 근무지로 인식된 공고가 없습니다. "
              f"받은 근무지: {seen}")
    return kept


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    code = company["code"]

    rows = list_open(code, overseas=bool(company.get("overseas")))

    jobs = []
    for x in rows:
        jid = _pick(x, "id")
        if not jid:
            continue
        body = str(_pick(x, "body") or "")
        text = strip_html(body)
        image_only = len(text) < 50 and "<img" in body.lower()
        url = str(_pick(x, "url") or "")
        if not url:
            url = f"https://{code}.breezy.hr/p/{jid}"

        jobs.append({
            "id": f"breezy-{code}-{jid}",
            "unit": "공고",
            "company": name, "companySlug": slug,
            "title": str(_pick(x, "title") or ""),
            "location": _location(x),
            # Breezy 는 신입/경력을 구분해 주지 않습니다. 지어내지 않습니다.
            "career": "무관",
            "postedAt": _date(_pick(x, "date")),
            # 마감일이 없습니다. 상시채용으로 표시됩니다.
            "closesAt": "",
            "dday": None,
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": url,
            "description": body if not image_only else "",
        })
    return jobs
