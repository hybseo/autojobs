# -*- coding: utf-8 -*-
"""
Ashby ATS 수집기. 국내외 기술 기업이 많이 씁니다. 42dot 이 이걸 씁니다.

  목록·상세  GET https://api.ashbyhq.com/posting-api/job-board/{code}

Ashby 가 공식으로 제공하는 공개 API 입니다. 인증이 필요 없고, 문서에
"자체 채용페이지를 만들 때 이 데이터를 쓰라"고 적혀 있습니다.
  https://developers.ashbyhq.com/docs/public-job-posting-api

지금까지 붙인 경로 중 가장 깔끔합니다. 한 번 요청하면 목록과 본문이 함께 옵니다.
상세 페이지를 따로 읽을 필요가 없어 요청 수가 공고 수와 무관하게 1회입니다.

robots.txt 에 대하여
--------------------
jobs.ashbyhq.com/robots.txt 는 /api/ 를 막습니다. 그건 채용 사이트 도메인의
내부 경로이고, 여기서 쓰는 것은 api.ashbyhq.com 의 공개 API 입니다.
Ashby 가 별도로 문서화해 제공하는 경로라 그 금지 대상이 아닙니다.

code 는 무엇인가
----------------
Ashby 채용 사이트 주소의 회사 부분입니다.
  https://jobs.ashbyhq.com/42dot/...  →  code = "42dot"

주의
----
- 해외 근무지 공고가 섞여 옵니다. 42dot 만 해도 폴란드·미국·베트남이 있습니다.
  국내 구직자용 사이트이므로 기본은 한국 근무지만 담습니다.
  해외까지 원하면 companies.json 에 "overseas": true 를 넣으세요.
- "인재풀 등록" 같은 상시 접수 창구가 섞여 있습니다. 실제 채용이 아니라
  이력서를 받아두는 것이라 기본으로 제외합니다.
- Ashby 는 마감일을 주지 않습니다. 전부 상시채용으로 처리됩니다.
"""
import json
import re
import html
import urllib.parse
import urllib.request

API = "https://api.ashbyhq.com/posting-api/job-board/{}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# Ashby 고용형태 → 화면 표기. 경력 구분이 아니라 고용형태입니다.
# Ashby 는 신입/경력을 구분해 주지 않으므로 career 는 "무관" 으로 둡니다.
EMPLOYMENT = {"FullTime": "정규직", "PartTime": "파트타임",
              "Intern": "인턴", "Contract": "계약직", "Temporary": "임시직"}

# 이력서만 받아두는 창구. 실제 채용 공고가 아닙니다.
POOL = re.compile(r"인재\s*풀|talent\s*pool|인재\s*등록", re.I)


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def _is_korea(job):
    addr = ((job.get("address") or {}).get("postalAddress") or {})
    country = (addr.get("addressCountry") or "").lower()
    if country:
        return "korea" in country and "north" not in country
    # 주소가 없으면 location 문자열로 판단합니다.
    return "korea" in (job.get("location") or "").lower()


def _location(job):
    """근무지. addressLocality 가 있으면 그것을, 없으면 location 앞부분을 씁니다."""
    addr = ((job.get("address") or {}).get("postalAddress") or {})
    loc = addr.get("addressLocality")
    if loc:
        return loc
    raw = job.get("location") or ""
    return raw.split(",")[0].strip()


def list_open(code, overseas=False, include_pool=False):
    """접수중 공고 목록. probe 용으로 밖에서도 씁니다."""
    j = _get(API.format(urllib.parse.quote(code)))
    rows = j.get("jobs") or []
    out = []
    for x in rows:
        if x.get("isListed") is False:
            continue
        if not overseas and not _is_korea(x):
            continue
        if not include_pool and POOL.search(x.get("title") or ""):
            continue
        out.append(x)
    return out


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
        jid = x.get("id")
        if not jid:
            continue
        body = x.get("descriptionHtml") or ""
        text = strip_html(body) or (x.get("descriptionPlain") or "")
        # 본문이 이미지뿐이면 원문으로 보냅니다.
        image_only = len(text) < 50 and "<img" in body.lower()

        emp = EMPLOYMENT.get(x.get("employmentType"))
        title = x.get("title") or ""
        if emp and emp not in title and emp != "정규직":
            title = f"{title} ({emp})"

        jobs.append({
            "id": f"ashby-{code}-{jid}",
            "unit": "공고",
            "company": name, "companySlug": slug,
            "title": title,
            "location": _location(x),
            # Ashby 는 신입/경력을 구분해 주지 않습니다. 지어내지 않습니다.
            "career": "무관",
            "postedAt": (x.get("publishedAt") or "")[:10],
            # Ashby 는 마감일이 없습니다. 전부 상시채용으로 표시됩니다.
            "closesAt": "",
            "dday": None,
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": x.get("jobUrl") or x.get("applyUrl") or "",
            "description": body if not image_only else "",
        })

    return jobs
