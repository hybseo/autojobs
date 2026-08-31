# -*- coding: utf-8 -*-
"""
Workday 수집기. 외국계 기업 한국법인이 많이 씁니다.

  목록  POST https://{회사}.{서버}.myworkdayjobs.com/wday/cxs/{회사}/{사이트}/jobs
  상세  GET  https://{회사}.{서버}.myworkdayjobs.com/wday/cxs/{회사}/{사이트}/job/{경로}

채용 사이트가 화면을 그릴 때 쓰는 것과 같은 경로입니다. 인증은 필요 없습니다.

code 는 무엇인가
----------------
채용 사이트 주소에서 도메인과 사이트 이름을 그대로 적습니다.

  https://valeo.wd3.myworkdayjobs.com/Valeo_Careers
  → "code": "valeo.wd3.myworkdayjobs.com/Valeo_Careers"

앞의 valeo 가 회사, wd3 이 서버, 뒤가 사이트 이름입니다. 셋 다 있어야
API 주소를 만들 수 있어 통째로 받습니다.

한국 공고만 담습니다
--------------------
Workday 는 전 세계 공고를 한 사이트에 올립니다. 그대로 받으면 수백 건이
쏟아지고 대부분 해외입니다. 국내 구직자용 사이트이므로 한국 근무지만
남깁니다. 해외까지 원하면 companies.json 에 "overseas": true 를 넣으세요.

만들 때의 한계
--------------
이 어댑터는 Workday 공개 문서와 알려진 응답 구조에 맞춰 작성했습니다.
실제 응답으로 검증하지 못한 상태로 처음 올라갑니다. 그래서 필드 이름이
다를 경우 조용히 0건이 되지 않도록, 무엇을 못 찾았는지 화면에 남깁니다.
첫 실행 로그를 반드시 확인하세요.
"""
import json
import re
import html
import time
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

PAGE = 20          # Workday 는 한 번에 20건씩 줍니다
MAX_PAGES = 25     # 안전장치. 500건이면 충분합니다

KOREA = re.compile(r"korea|한국|서울|seoul|경기|인천|부산|대구|울산|대전|광주"
                   r"|pangyo|판교|수원|화성|천안|아산|창원", re.I)


def _parts(code):
    """code 를 (호스트, 테넌트, 사이트) 로 나눕니다."""
    c = (code or "").strip().replace("https://", "").replace("http://", "").strip("/")
    if "/" not in c:
        raise ValueError(
            f"code 형식이 잘못됐습니다: {code!r}\n"
            "  '회사.wd3.myworkdayjobs.com/사이트이름' 형태여야 합니다.")
    host, site = c.split("/", 1)
    tenant = host.split(".")[0]
    return host, tenant, site.split("/")[0]


def _post(url, body):
    req = urllib.request.Request(
        url, method="POST", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def _get(url):
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def _date(s):
    """'2026-08-31T...' 또는 'Posted Today' 등이 옵니다. 날짜만 뽑습니다."""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(s or ""))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def list_open(code, overseas=False):
    """접수중 공고 목록. probe 용으로 밖에서도 씁니다."""
    host, tenant, site = _parts(code)
    base = f"https://{host}/wday/cxs/{tenant}/{site}"

    out, offset = [], 0
    for _ in range(MAX_PAGES):
        j = _post(f"{base}/jobs", {
            "appliedFacets": {}, "limit": PAGE,
            "offset": offset, "searchText": ""})
        posts = j.get("jobPostings") or []
        if not posts:
            break
        out += posts
        offset += PAGE
        if offset >= (j.get("total") or 0):
            break
        time.sleep(0.4)

    if not overseas:
        out = [x for x in out if KOREA.search(
            f"{x.get('locationsText','')} {x.get('title','')}")]
    return out


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    code = company["code"]
    host, tenant, site = _parts(code)
    base = f"https://{host}/wday/cxs/{tenant}/{site}"

    rows = list_open(code, overseas=bool(company.get("overseas")))

    # 구조가 다르면 조용히 0건이 됩니다. 그러면 원인을 알 수 없습니다.
    if not rows:
        print(f"      ! {name}: 공고 0건. 응답 구조가 바뀌었을 수 있습니다. "
              f"{base}/jobs 를 확인하세요.")
        return []

    jobs = []
    for x in rows:
        path = x.get("externalPath") or ""
        if not path:
            continue
        jid = path.rstrip("/").split("/")[-1]

        body = ""
        try:
            d = _get(base + "/job" + path)
            info = d.get("jobPostingInfo") or {}
            body = info.get("jobDescription") or ""
        except Exception:
            body = ""
        time.sleep(0.3)

        text = strip_html(body)
        image_only = len(text) < 50 and "<img" in body.lower()

        jobs.append({
            "id": f"workday-{tenant}-{jid}",
            "unit": "공고",
            "company": name, "companySlug": slug,
            "title": x.get("title") or "",
            "location": x.get("locationsText") or "",
            # Workday 는 신입/경력을 구분해 주지 않습니다. 지어내지 않습니다.
            "career": "무관",
            "postedAt": _date(x.get("postedOn") or x.get("startDate")),
            # 마감일을 주지 않습니다. 상시채용으로 표시됩니다.
            "closesAt": "",
            "dday": None,
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": f"https://{host}/{site}{path}",
            "description": body if not image_only else "",
        })

    return jobs
