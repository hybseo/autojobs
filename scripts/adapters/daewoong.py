# -*- coding: utf-8 -*-
"""
대웅그룹(career.daewoong.co.kr) 채용 수집기.

목록  GET https://career.daewoong.co.kr/apply/posting
      GET https://career.daewoong.co.kr/apply/posting?daae99d2_page={n}
상세  GET https://career.daewoong.co.kr/job-posting/{id}

daewoong.recruiter.co.kr 은 옛 사이트입니다
--------------------------------------------
대웅도 예전에는 리크루터를 썼고 그 주소가 아직 살아 있습니다. 하지만
2026-09-11 확인 시점에 거기 있는 13건은 전부 마감된 공고였고, 실제
채용은 자체 사이트에서 하고 있었습니다.

리크루터 주소가 응답한다고 "이 회사는 리크루터를 쓴다" 고 단정하면
안 됩니다. 회사 홈페이지의 채용 링크를 따라가 지금 운영 중인 곳이
어디인지 먼저 확인하세요. 실제로 그렇게 판단했다가 대웅을 0건으로
잘못 등록할 뻔했습니다.

Webflow CMS 입니다
------------------
공개 API 가 없습니다. 서버가 HTML 을 완성해 보내고, 한 쪽에 10건씩
담아 페이지를 나눕니다. 페이지 파라미터 이름이 특이합니다.

    /apply/posting                    1쪽
    /apply/posting?daae99d2_page=2    2쪽

daae99d2 는 Webflow 가 컬렉션마다 붙이는 식별자입니다. 사이트를
다시 만들면 바뀔 수 있으니, 2쪽이 비어 보이면 이것부터 확인하세요.

첫 쪽만 보고 판단하지 마세요
----------------------------
2026-09-11 기준 6쪽에 걸쳐 57건이 있었습니다. 첫 쪽 10건만 세고
"10건" 이라고 잘못 보고한 적이 있습니다. 끝까지 넘기세요.

목록 구조 (2026-09-11 확인)
---------------------------
    <a href="/job-posting/40affda1...">
      <div class="apply-item-header">
        <div class="d-day-label">D-14</div>
        <div class="close-day-label w-condition-invisible">마감</div>
        <h2 class="apply-list-heading">공고 제목</h2>
        <div id="start-date" class="job-date">2026-09-04</div>
        <div id="close-date" class="close-date">2026-09-25</div>
        <div fs-cmsfilter-field="type">경력</div>
        <div fs-cmsfilter-field="company">대웅제약</div>
        <div fs-cmsfilter-field="part">영업</div>
        <div fs-cmsfilter-field="region">서울</div>

값은 fs-cmsfilter-field 속성으로 찾습니다. 순서에 기대지 않으므로
항목이 늘거나 줄어도 견딥니다.

마감 판정 — 뒤집혀 있으니 주의
------------------------------
마감 라벨에 w-condition-invisible 이 "붙어 있으면" 진행중입니다.
Webflow 가 조건부 표시를 이렇게 처리합니다. 없으면 마감입니다.
읽는 방향을 반대로 잡으면 진행중인 공고를 전부 버립니다.

2026-09-11 기준 57건 전부 진행중이었습니다.

계열사에 대하여
--------------
한 사이트에 여러 계열사가 섞여 옵니다. 그중 담을 곳만 companies.json
의 affiliates 에 적습니다. 삼성·SK 어댑터와 같은 방식입니다.

2026-09-11 진행중 분포
    대웅제약 40 · 대웅(지주) 12 · 대웅바이오 3 · 한올바이오파마 1 · 대웅이엔지 1

필터에 있는 계열사(공고가 없는 곳 포함)
    대웅, 대웅제약, 대웅바이오, DMD대웅경영개발원, idsTrust, 대웅이엔지,
    대웅개발, 대웅테라퓨틱스, 대웅펫, 한올바이오파마, 선마을,
    아피셀테라퓨틱스, 아이엔테라퓨틱스, 다나아데이터

회사명은 응답 값을 그대로 씁니다. 한 회사로 뭉치면 한올바이오파마
공고를 대웅제약이 뽑는 것으로 잘못 보이게 됩니다.
"""
import html
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://career.daewoong.co.kr"
LIST_URL = BASE + "/apply/posting"
# Webflow 컬렉션 식별자. 사이트를 다시 만들면 바뀝니다.
PAGE_PARAM = "daae99d2_page"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

MAX_PAGES = 30  # 안전장치. 한 쪽 10건이니 300건까지 봅니다.

# 공고 링크. 블록보다 앞에 나옵니다.
HREF = re.compile(r'href="(/job-posting/[^"]+)"', re.I)
TITLE = re.compile(r'<h2[^>]*>(.*?)</h2>', re.S | re.I)
START = re.compile(r'id="start-date"[^>]*>([^<]*)<', re.I)
CLOSE = re.compile(r'id="close-date"[^>]*>([^<]*)<', re.I)
# 마감 라벨. class 안에 w-condition-invisible 이 있으면 진행중입니다.
CLOSED = re.compile(r'class="([^"]*close-day-label[^"]*)"', re.I)
# 상세 본문.
BODY = re.compile(r'<div[^>]+class="[^"]*w-richtext[^"]*"[^>]*>(.*?)</div>\s*</div>',
                  re.S | re.I)

# 채용유형 → 사이트 career 값.
CAREER = {"경력": "경력", "신입": "신입", "신입/주니어경력": "신입/경력",
          "신입/경력": "신입/경력", "계약직/인턴": "무관", "무관": "무관"}


def _get(url):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9",
    })
    last = None
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError:
            raise
        except Exception as e:
            last = e
            if i < 2:
                time.sleep(2 + i * 2)
    raise last


def _text(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def _field(chunk, name):
    """fs-cmsfilter-field 값을 꺼냅니다. 순서에 기대지 않습니다."""
    m = re.search(r'fs-cmsfilter-field="%s"[^>]*>([^<]{0,40})<' % name, chunk, re.I)
    return _text(m.group(1)) if m else ""


def _date(v):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(v or ""))
    return m.group(0) if m else ""


def list_open():
    """진행중 공고만 골라 돌려줍니다. probe 용으로 밖에서도 씁니다."""
    rows, seen, closed = [], set(), 0

    for p in range(1, MAX_PAGES + 1):
        url = LIST_URL if p == 1 else f"{LIST_URL}?{PAGE_PARAM}={p}"
        page = _get(url)

        # 링크와 블록을 짝지어야 합니다. 링크가 블록보다 앞에 나옵니다.
        parts = page.split('apply-item-header')
        if len(parts) < 2:
            if p == 1:
                print(f"  ! 대웅: 공고 블록을 찾지 못했습니다. ({url})")
                print(f"    받은 HTML {len(page)}자 · "
                      f"'apply-item-header' {page.count('apply-item-header')}회 · "
                      f"'/job-posting/' {page.count('/job-posting/')}회")
            break

        added = 0
        for i in range(1, len(parts)):
            chunk = parts[i][:3000]
            # 이 블록의 링크는 바로 앞 조각 끝에 있습니다.
            hrefs = HREF.findall(parts[i - 1][-600:])
            if not hrefs:
                continue
            href = hrefs[-1]
            jid = href.rstrip("/").split("/")[-1]
            if jid in seen:
                continue
            seen.add(jid)

            # 마감 라벨에 w-condition-invisible 이 붙어 있으면 진행중입니다.
            cm = CLOSED.search(chunk)
            if cm and "w-condition-invisible" not in cm.group(1):
                closed += 1
                continue

            t = TITLE.search(chunk)
            if not t:
                continue

            rows.append({
                "id": jid,
                "url": urllib.parse.urljoin(BASE, href),
                "title": _text(t.group(1)),
                "type": _field(chunk, "type"),
                "company": _field(chunk, "company"),
                "part": _field(chunk, "part"),
                "region": _field(chunk, "region"),
                "start": _date(START.search(chunk).group(1)) if START.search(chunk) else "",
                "close": _date(CLOSE.search(chunk).group(1)) if CLOSE.search(chunk) else "",
            })
            added += 1

        if added == 0 and closed == 0:
            break
        time.sleep(0.3)

    if rows:
        print(f"  · 대웅: 진행중 {len(rows)}건" +
              (f" (마감 {closed}건 제외)" if closed else ""))
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    affiliates = company.get("affiliates") or []

    rows = list_open()

    # 담을 계열사만 고릅니다. 비워두면 전부 담습니다.
    if affiliates:
        def norm(v):
            return re.sub(r"\s+", "", str(v or "")).lower()
        wanted = [norm(a) for a in affiliates]
        kept = [x for x in rows if any(w and w == norm(x["company"]) for w in wanted)]
        if rows and not kept:
            seen = sorted({x["company"] for x in rows if x["company"]})
            print(f"  ! 대웅: affiliates 와 맞는 공고가 없습니다. "
                  f"받은 회사: {seen[:10]}")
        rows = kept

    jobs = []
    for x in rows:
        raw = ""
        try:
            m = BODY.search(_get(x["url"]))
            raw = m.group(1) if m else ""
        except Exception:
            raw = ""
        time.sleep(0.3)

        text = strip_html(raw)
        # 본문이 이미지뿐이면 세부 직무를 읽을 수 없습니다. 원문으로 보냅니다.
        image_only = len(text) < 50 and "<img" in raw.lower()

        jobs.append({
            "id": f"daewoong-{x['id'][:16]}",
            "unit": "공고",
            # 계열사명을 그대로 씁니다. 한 회사로 뭉치면 어디 공고인지 모릅니다.
            "company": x["company"] or name,
            "companySlug": slug,
            "title": x["title"],
            "location": x["region"],
            "career": CAREER.get(x["type"], "무관"),
            "postedAt": x["start"],
            "closesAt": x["close"],
            "dday": None,
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": x["url"],
            "description": raw if not image_only else "",
        })

    return jobs
