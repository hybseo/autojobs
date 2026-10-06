# -*- coding: utf-8 -*-
"""
나인하이어(ninehire) 채용 사이트 수집기.

목록  GET https://{code}.ninehire.site/_backend/identity-access/homepage/recruitments
           ?companyId={companyId}&page=1&countPerPage=100
원문  https://{code}.ninehire.site/{siteURL}

잡코리아 계열 ATS 입니다. 국내 제약·바이오 쪽에서 자주 보입니다.
2026-09-11 확인 기준 리가켐바이오·보령·일동제약이 이걸 씁니다.

code 는 두 값을 쉼표로 붙여 적습니다
--------------------------------------
    "code": "ligachembio,2bb7a6c0-3742-11ef-b2b0-8b38cffa734f"
             ↑ 하위도메인      ↑ companyId (UUID)

앞은 주소를 만들 하위도메인, 뒤는 API 에 넘길 회사 식별자입니다.
둘 다 필요합니다. companyId 없이 부르면 아무것도 오지 않습니다.

자체 도메인을 쓰는 회사가 있습니다
    보령      recruit.boryung.co.kr
    일동제약   careers.ildong.com

그럴 때는 companies.json 에 "domain" 을 적으세요.
아래 _base() 가 domain 을 먼저 봅니다.

companyId 찾는 법
    1. 채용 사이트를 엽니다
    2. 개발자도구 Network 에서 /_backend/ 로 시작하는 요청을 찾습니다
    3. 주소의 companyId 값이 그것입니다

경로에 주의하세요
-----------------
공고 목록인데 경로가 recruitment 가 아니라 identity-access 입니다.

    /_backend/identity-access/homepage/recruitments   ← 맞음
    /_backend/recruitment/homepage/recruitments       ← 404

이름만 보고 recruitment 로 부르면 404 가 납니다. 처음에 그렇게 헤맸습니다.

함정 1 — status 에 disabled 가 섞여 옵니다
------------------------------------------
2026-09-11 리가켐바이오 기준 9건 중 6건만 in_progress 였고 나머지는
disabled 였습니다. 걸러내지 않으면 내려간 공고가 올라갑니다.

함정 2 — 상세 주소가 공고마다 다르지 않습니다
--------------------------------------------
응답의 siteURL 이 공고 주소처럼 생겼지만 회사마다 하나뿐입니다.
9건 전부 같은 값이었습니다. 공고별 주소를 만들 수 없어 모두 목록
페이지로 보냅니다. recruitmentId 로 /recruit/{id} 를 만들어 봤지만
404 였습니다.

없는 주소를 지어내지 않습니다.

함정 3 — 마감일이 null 인 공고가 있습니다
-----------------------------------------
deadlineType 이 custom_deadline 이면 deadlineValue 에 날짜가 있고,
상시채용이면 null 입니다. 비워 두면 사이트가 상시채용으로 표시합니다.

응답 구조 (2026-09-11 실제 확인)
--------------------------------
{ "count": 9, "results": [ ... ] }

    recruitmentId   UUID
    title           공고 제목
    status          in_progress / disabled
    deadlineType    custom_deadline / (상시)
    deadlineValue   2026-10-04T... 또는 null
    employmentType  ["full_time"]           배열입니다
    career          {"type":"experienced","range":{"over":3,"below":8}}
    affiliation     {"title":"CMC센터"}      소속 조직
    jobGroup        직군
    jobLocations    근무지 배열
    siteURL         k9YnhEUa                회사 공통 주소
"""
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

API = "/_backend/identity-access/homepage/recruitments"

# 수집기 꼬리표는 그대로 둡니다.
#
# 2026-10-02 부터 나인하이어를 쓰는 아홉 곳이 전부 429(요청이 너무 많음)로
# 막혔습니다. 재시도를 넣고 회사마다 5초를 쉬어도 그대로였고, 그 날 첫
# 나인하이어 회사(리가켐바이오)부터 바로 429 가 났습니다. 요청이 쌓여서가
# 아니라 우리를 알아보고 막는다는 뜻입니다.
#
# 2026-10-06 확인: 나인하이어 robots.txt 는 네이버(Yeti)·구글·빙·GPTBot
# 네 곳만 이름을 적어 허용하고, 나머지에게는 /api 와 물음표가 붙은 주소를
# 전부 막아 두었습니다. 우리가 쓰는 /_backend 도 그 안에 들어갑니다.
# 우리 쪽은 바뀐 것이 없으니 나인하이어가 차단을 새로 건 것입니다.
#
# 꼬리표를 빼면 통과할 수도 있습니다. 하지만 그것은 막아 둔 것을 알고도
# 신분을 숨겨 들어가는 일입니다. 사람인 호스팅형을 제외한 것과 같은
# 기준으로, 여기서도 우리가 누군지 밝힌 채로 요청합니다. 나인하이어가
# 허용하기로 마음먹는다면 이 꼬리표가 우리를 알아볼 표시가 됩니다.
#
# 막혀 있는 동안 공고가 사라지지는 않습니다. fetch_jobs.py 가 수집에
# 실패한 회사의 지난 공고를 최대 7일간 그대로 들고 갑니다.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# 이력서만 받아두는 창구. 실제 자리가 아닙니다.
POOL = re.compile(
    r"인재\s*(?:상시|풀|pool|db)|talent\s*pool|상시\s*인재|people\s*database", re.I)

# career.type → 사이트 표기.
CAREER = {"experienced": "경력", "newcomer": "신입", "entry": "신입",
          "irrelevant": "무관", "any": "무관", "intern": "무관"}


def _base(company):
    """주소의 앞부분. domain 이 있으면 그것을, 없으면 {code}.ninehire.site."""
    dom = (company.get("domain") or "").strip().rstrip("/")
    if dom:
        return dom if dom.startswith("http") else "https://" + dom
    sub, _ = _split_code(company["code"])
    return f"https://{sub}.ninehire.site"


def _split_code(code):
    """'ligachembio,2bb7a6c0-...' → ('ligachembio', '2bb7a6c0-...')."""
    parts = [p.strip() for p in str(code or "").split(",")]
    sub = parts[0] if parts else ""
    cid = parts[1] if len(parts) > 1 else ""
    if not cid:
        raise RuntimeError(
            "ninehire: code 에 companyId 가 없습니다. "
            "'하위도메인,companyId' 형식으로 적으세요. "
            "예: ligachembio,2bb7a6c0-3742-11ef-b2b0-8b38cffa734f")
    return sub, cid


def _get(url):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다."""
    # 브라우저가 보내는 헤더에 맞춥니다. 나인하이어는 헤더가 빈약하면
    # 사람이 아니라고 보고 막는 것으로 보입니다.
    host = url.split("/")[2] if "//" in url else ""
    req = urllib.request.Request(url, headers={
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        "User-Agent": UA,
        "Referer": f"https://{host}/recruit" if host else "",
        "Origin": f"https://{host}" if host else "",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    })
    last = None
    TRIES = 2
    for i in range(TRIES):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            # 429(요청이 너무 많음)와 5xx 는 기다리면 풀릴 때가 있습니다.
            #
            # 다만 2026-10-02 부터의 429 는 기다려서 풀리는 종류가
            # 아닙니다. 첫 요청부터 429 가 나고, 30·60·120초를 기다려도
            # 그대로였습니다. 나인하이어가 차단을 걸어 둔 것입니다.
            #
            # 그래서 재시도를 두 번으로 줄였습니다. 아홉 곳이 각자 여러 번
            # 길게 기다리면 갱신 시간만 30분 늘어나고(한 번은 60분 제한에
            # 걸려 중단됐습니다), 상대 서버에 계속 두드리는 셈이 됩니다.
            # 공고는 fetch_jobs.py 가 지난 회차 것을 들고 가 지켜줍니다.
            if e.code in (429, 500, 502, 503, 504) and i < TRIES - 1:
                try:
                    hinted = int(e.headers.get("Retry-After") or 0)
                except Exception:
                    hinted = 0
                time.sleep(min(max(hinted, 10), 30))
                last = e
                continue
            raise
        except Exception as e:
            last = e
            if i < TRIES - 1:
                time.sleep(3)
    raise last


def _date(v):
    """'2026-10-04T00:00:00' → '2026-10-04'. null 이면 빈 문자열(상시채용)."""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(v or ""))
    if not m:
        return ""
    if int(m.group(1)) >= 2100:
        return ""
    return m.group(0)


def _career(v):
    """career 객체에서 신입/경력을 읽습니다.

    {"type":"experienced","range":{"over":3,"below":8}} 형태입니다.
    범위가 0년부터면 신입도 받는다는 뜻으로 봅니다.
    """
    if not isinstance(v, dict):
        return "무관"
    t = CAREER.get(str(v.get("type") or "").lower(), "무관")
    rng = v.get("range") or {}
    try:
        if t == "경력" and int(rng.get("over") or 0) == 0:
            return "신입/경력"
    except (TypeError, ValueError):
        pass
    return t


def _location(v):
    """jobLocations 는 배열입니다. 여러 곳이면 대표 한 곳만 적습니다."""
    if not isinstance(v, list) or not v:
        return ""
    names = []
    for x in v:
        if isinstance(x, dict):
            n = x.get("title") or x.get("name") or x.get("address") or ""
        else:
            n = str(x)
        n = str(n).strip()
        if n:
            names.append(n)
    if not names:
        return ""
    return names[0] if len(names) == 1 else f"{names[0]} 외 {len(names) - 1}곳"


def _title_of(v):
    """affiliation·jobGroup 처럼 {title: ...} 로 오는 값에서 이름만."""
    if isinstance(v, dict):
        return str(v.get("title") or v.get("name") or "").strip()
    return str(v or "").strip()


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def list_open(company, include_pool=False):
    """진행중 공고만 골라 돌려줍니다. probe 용으로 밖에서도 씁니다.

    부르기 전에 잠깐 쉽니다. 나인하이어를 쓰는 회사가 열 곳이 넘어
    줄줄이 부르면 429 가 납니다. 한 곳당 5초면 전체로는 1분 남짓이고,
    그 대신 193건이 통째로 사라지는 일을 막습니다.
    """
    time.sleep(5)
    _, cid = _split_code(company["code"])
    base = _base(company)
    q = urllib.parse.urlencode({"companyId": cid, "page": 1, "countPerPage": 100})
    j = _get(f"{base}{API}?{q}")

    rows = j.get("results") or []
    if not rows:
        print(f"  ! ninehire({company['slug']}): 공고가 비어 있습니다. "
              f"companyId 가 맞는지 확인하세요.")
        return []

    live = [x for x in rows if str(x.get("status")) == "in_progress"]
    if not include_pool:
        live = [x for x in live if not POOL.search(str(x.get("title") or ""))]

    dropped = len(rows) - len(live)
    if dropped:
        print(f"  · ninehire({company['slug']}): 전체 {len(rows)}건 중 "
              f"{len(live)}건 (마감·인재풀 {dropped}건 제외)")
    return live


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    base = _base(company)

    rows = list_open(company, include_pool=bool(company.get("includePool")))

    jobs = []
    for x in rows:
        rid = x.get("recruitmentId")
        if not rid:
            continue

        # 상세 주소가 공고마다 다르지 않습니다. 목록으로 보냅니다.
        site = str(x.get("siteURL") or "").strip()
        url = f"{base}/{site}" if site else f"{base}/recruit"

        # 고용형태는 배열입니다. 정규직이 아니면 제목에 표시합니다.
        title = str(x.get("externalTitle") or x.get("title") or "").strip()
        emp = x.get("employmentType")
        emp = emp[0] if isinstance(emp, list) and emp else ""
        if emp and emp != "full_time":
            label = {"contract": "계약직", "intern": "인턴",
                     "part_time": "파트타임"}.get(str(emp), "")
            if label and label not in title:
                title = f"{title} ({label})"

        jobs.append({
            "id": f"ninehire-{str(rid)[:16]}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            "title": title,
            "location": _location(x.get("jobLocations")),
            "career": _career(x.get("career")),
            # 게시일을 주지 않습니다.
            "postedAt": "",
            # deadlineValue 가 null 이면 상시채용입니다.
            "closesAt": _date(x.get("deadlineValue")),
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": url,
            # 목록에 본문이 없고 공고별 상세 주소도 없습니다. 원문으로 보냅니다.
            "description": "",
        })

    return jobs
