# -*- coding: utf-8 -*-
"""
네오위즈(neowiz.com) 채용 수집기.

목록  GET https://www.neowiz.com/kr/career/browse-job
상세  GET https://www.neowiz.com/kr/career/browse-job/{id}

공개 API 가 따로 없습니다. 서버가 HTML 을 완성해서 보냅니다.
개발자도구 Network 탭에 API 호출이 하나도 안 잡힙니다.

그래도 HTML 태그를 파싱하지는 않습니다
--------------------------------------
목록 페이지의 <script> 안에 이런 줄이 들어 있습니다.

    const serverData = [ {id, categories, text, tags}, ... ]

화면은 이 배열로 그려집니다. 태그 구조를 훑는 것보다 이 JSON 을 꺼내
쓰는 편이 훨씬 안전합니다. 디자인이 바뀌어도 데이터 모양은 잘 안 바뀝니다.
그리팅 어댑터가 __NEXT_DATA__ 를 꺼내 쓰는 것과 같은 발상입니다.

2026-09-09 확인 시점 21건이 들어 있었고, 화면 표시 건수와 일치했습니다.

항목 구조 (2026-09-09 실제 확인)
--------------------------------
    id          c3704f2e-...    UUID. 상세 주소에 그대로 들어갑니다
    text        공고 제목        "[ASTRA9 Studio] ... 클라이언트 프로그래머"
    categories  {
        commitment  "Regular(Full-time)"   고용형태
        department  "ASTRA9 Studio"        프로젝트/스튜디오
        location    "NEOWIZ"               회사 구분(근무지가 아닙니다)
        team        "Game Engineering"     직군
    }

주의 1 — location 은 근무지가 아닙니다
--------------------------------------
이름만 보면 근무지 같은데 값이 "NEOWIZ" 입니다. 회사 구분입니다.
그대로 location 에 넣으면 화면 근무지 칸에 "NEOWIZ" 가 찍힙니다.

실제 근무지는 본문에 "[근무장소] 네오위즈 본사 (판교)" 로 적혀 있습니다.
본문에서 뽑아낼 수는 있지만 표기가 제각각일 수 있어, 확실한 경우만
씁니다. 못 찾으면 비워둡니다. 지어내지 않습니다.

주의 2 — 마감일이 없습니다
--------------------------
본문에 "본 공고는 채용 시 마감되는 공고" 라고 적혀 있습니다. 마감일
필드도 없습니다. closesAt 을 비우면 사이트가 상시채용으로 표시합니다.

주의 3 — 신입/경력 구분이 없습니다
----------------------------------
categories 에 있는 것은 고용형태(정규직/계약직/프리랜서)뿐입니다.
신입인지 경력인지는 공고 본문을 읽어야 알 수 있고, 표기가 일정하지
않습니다. career 는 "무관" 으로 둡니다. 지어내지 않습니다.

주의 4 — 인재풀 공고가 섞여 있습니다
------------------------------------
"[네오위즈] 인재 Pool", "아트 프리랜서" 같은 상시 접수 창구가 있습니다.
실제 채용이 아니라 이력서를 받아두는 것이라 기본으로 제외합니다.
Ashby 어댑터와 같은 방침입니다. 담고 싶으면 companies.json 에
"includePool": true 를 넣으세요.
"""
import html
import json
import re
import time
import urllib.error
import urllib.request

BASE = "https://www.neowiz.com"
LIST_URL = BASE + "/kr/career/browse-job"
DETAIL = BASE + "/kr/career/browse-job/{}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# 이력서만 받아두는 창구. 실제 채용 공고가 아닙니다.
POOL = re.compile(r"인재\s*pool|talent\s*pool|인재\s*풀|프리랜서", re.I)

# 본문에서 근무지를 찾습니다. 확실한 경우만 씁니다.
PLACE = re.compile(r"\[?근무\s*(?:장소|지)\]?\s*[:\]]?\s*([^\n<]{2,40})")

# 상세 본문이 담긴 영역. 화면이 바뀌면 여기부터 확인하세요.
BODY = re.compile(
    r'<div[^>]+class="[^"]*jobDetail__content[^"]*"[^>]*>(.*?)</div>\s*</div>',
    re.S | re.I)


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


def _server_data(page):
    """<script> 안의 serverData 배열을 꺼냅니다.

    괄호 짝을 세어 배열 끝을 찾습니다. 정규식으로 [ ... ] 를 잡으면
    본문 안의 대괄호에 걸려 중간에서 잘립니다.
    """
    i = page.find("serverData")
    if i < 0:
        return None
    start = page.find("[", i)
    if start < 0:
        return None
    depth, end = 0, -1
    for k in range(start, len(page)):
        c = page[k]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                end = k
                break
    if end < 0:
        return None
    try:
        return json.loads(page[start:end + 1])
    except Exception:
        return None


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def _location(text):
    """본문에서 근무지를 찾습니다. 못 찾으면 빈 문자열."""
    m = PLACE.search(text or "")
    if not m:
        return ""
    v = m.group(1).strip().strip("-–—:").strip()
    # 문장이 통째로 걸리면 근무지가 아닙니다.
    if len(v) > 30 or not v:
        return ""
    return v


def list_open(include_pool=False):
    """공고 목록. probe 용으로 밖에서도 씁니다."""
    page = _get(LIST_URL)
    rows = _server_data(page)

    if rows is None:
        # 화면이 바뀌면 조용히 0건이 됩니다.
        # "구조가 바뀌었다" 는 말만으로는 무엇을 고칠지 알 수 없습니다.
        print("  ! 네오위즈: serverData 를 찾지 못했습니다.")
        print(f"    받은 HTML {len(page)}자 · "
              f"'serverData' {page.count('serverData')}회 · "
              f"'browse-job__job-posting' {page.count('browse-job__job-posting')}회")
        print(f"    {LIST_URL} 의 <script> 안에 const serverData 가 "
              f"아직 있는지 확인하세요.")
        return []

    if not include_pool:
        rows = [x for x in rows if not POOL.search(str(x.get("text") or ""))]
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]

    rows = list_open(include_pool=bool(company.get("includePool")))

    jobs = []
    for x in rows:
        jid = x.get("id")
        if not jid:
            continue

        cat = x.get("categories") or {}
        url = DETAIL.format(jid)

        raw = ""
        try:
            m = BODY.search(_get(url))
            raw = m.group(1) if m else ""
        except Exception:
            raw = ""
        time.sleep(0.3)

        text = strip_html(raw)
        # 본문이 이미지뿐이면 세부 직무를 읽을 수 없습니다. 원문으로 보냅니다.
        image_only = len(text) < 50 and "<img" in raw.lower()

        # 고용형태가 정규직이 아니면 제목에 덧붙입니다. Ashby 어댑터와 같은 방식입니다.
        title = str(x.get("text") or "").strip()
        emp = str(cat.get("commitment") or "").strip()
        if emp and "Regular" not in emp and emp not in title:
            title = f"{title} ({emp})"

        jobs.append({
            "id": f"neowiz-{jid}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            "title": title,
            # categories.location 은 회사 구분("NEOWIZ")이라 쓰지 않습니다.
            "location": _location(text),
            # 신입/경력을 구분해 주지 않습니다. 지어내지 않습니다.
            "career": "무관",
            # 게시일을 주지 않습니다.
            "postedAt": "",
            # 채용 시 마감이라 마감일이 없습니다. 상시채용으로 표시됩니다.
            "closesAt": "",
            "dday": None,
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": url,
            "description": raw if not image_only else "",
        })

    return jobs
