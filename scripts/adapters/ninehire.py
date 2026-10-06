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

companyId 를 추측해서 넣지 마세요
---------------------------------
위 3단계로 실제 요청에서 확인한 값만 적습니다. 다른 회사 값의 모양을
보고 만들어 넣으면 안 됩니다. 2026-10-02 에 고영테크놀러지 값을
추측으로 넣었다가 한참 엉뚱한 곳을 뒤졌습니다.

확인이 안 되면 추측값을 적는 대신 이렇게 두세요.
    "enabled": false,
    "note": "companyId 확인 못 함"
공고 0건으로 조용히 넘어가는 것보다 낫습니다. 이 규칙은 companyId 만이
아니라 다른 어댑터의 식별자·설정값에도 똑같이 적용됩니다.

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

# 왜 429 가 나는가 — 2026-10-06 확정
#
# 2026-10-02 부터 나인하이어를 쓰는 아홉 곳이 전부 429 로 막혔습니다.
# 그날 첫 나인하이어 회사부터 바로 429 였습니다.
#
# 원인은 나인하이어 앱이 아니라 호스팅 플랫폼입니다. 429 응답을 찍어보니
#   Server=Vercel
#   본문이 JSON 이 아니라 HTML (Vercel Security Checkpoint 페이지)
# 였고, 같은 회차에서 꼬리표 UA 와 평범한 크롬 UA 를 반씩 나눠 보낸
# 결과가 양쪽 똑같이 429 였습니다. UA 는 원인이 아닙니다.
#
# 나인하이어는 Vercel 에 올라가 있고 Vercel Firewall 의 Attack Mode
# (공격 차단 모드)가 켜져 있습니다. Vercel 문서 그대로입니다.
#   "브라우저가 일으킨 트래픽은 API 호출까지 지원됩니다. 다만 독립 API,
#    다른 백엔드 프레임워크, 인식되지 않은 자동화 서비스는 챌린지를
#    통과하지 못해 차단될 수 있습니다."
# 통과하는 것은 Vercel 이 인정한 봇(구글·빙·네이버 Yeti 등)뿐입니다.
# robots.txt 에 하필 그 넷만 Allow 로 적혀 있던 이유도 같은 설정입니다.
#
# 그래서 이것들은 전부 원인이 아니었습니다. 다시 손대지 마세요.
#   요청 간격·재시도    회사당 요청은 원래 1회뿐입니다(전체 9회/회차)
#   User-Agent 문자열   양쪽 묶음이 똑같이 막혔습니다
#   Origin·Sec-Fetch-*  근거 없는 추측이었고 되돌렸습니다
#   companyId 오타      시점이 겹친 우연이었습니다
#
# 챌린지는 자바스크립트를 실행해야 풀립니다. 헤드리스 브라우저를 쓰면
# 기술적으로는 통과하지만, 상대가 켜 둔 보안 장치를 일부러 뚫는 일이라
# 하지 않습니다. 정상 경로는 나인하이어(support@ninehire.com)나 고객사를
# 통해 Vercel Firewall Custom Rule 에 우리 UA 를 Allow 로 넣는 것입니다.
#
# 그때까지는 '차단 중' 으로 둡니다. 비활성(enabled:false)이 아닙니다.
# 매 회차 계속 시도하되 실패로 세지 않고 로그도 한 줄만 남깁니다.
# 방화벽이 풀리거나 예외가 들어가는 순간 아무 작업 없이 저절로
# 공고가 다시 들어옵니다. 손댈 파일이 없습니다.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# fetch_jobs.py 와 약속한 표시.
#
# 이 글자로 시작하는 오류를 내면 fetch_jobs.py 가 '실패' 가 아니라
# '차단 중' 으로 처리합니다. 양쪽 파일에 같은 글자가 적혀 있어야 합니다.
BLOCKED = "[차단] "

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


def _why_blocked(e):
    """429 가 나면 누가 막았는지 한 줄로 찍습니다.

    왜 이걸 찍나
    ------------
    이 어댑터는 회사당 요청을 딱 한 번 합니다. 아홉 곳을 5초 간격으로
    부르니 전체 9회입니다. 그 정도를 "요청이 너무 많다" 고 막을 서버는
    없습니다. 즉 429 는 속도 제한이 아니라 차단 응답으로 쓰인 것입니다.

    누가 막았는지는 응답에 적혀 있습니다. 지금까지 우리는 그 응답을
    버리고 "HTTP Error 429" 한 줄만 봤기 때문에 추측만 했습니다.
      Server / cf-ray      클라우드플레어 등 앞단 방화벽이면 여기 표시됩니다
      X-RateLimit-*        앱이 세는 한도면 남은 횟수가 적혀 있습니다
      Retry-After          몇 초 뒤 풀리는지. 없으면 시간 문제가 아닙니다
      본문                 "bot detected" 류인지, 한도 초과 안내인지
    이 한 줄을 보고 나서 다음 손을 정합니다. 추측으로 헤더를 이리저리
    바꾸는 일을 그만하기 위한 장치입니다.
    """
    try:
        h = e.headers or {}
        bits = []
        for k in ("Server", "Retry-After", "cf-ray", "cf-mitigated",
                  "x-amzn-waf-action", "X-RateLimit-Limit",
                  "X-RateLimit-Remaining", "X-RateLimit-Reset"):
            v = h.get(k)
            if v:
                bits.append(f"{k}={v}")
        body = ""
        try:
            body = (e.read() or b"")[:200].decode("utf-8", "replace")
            body = " ".join(body.split())
        except Exception:
            pass
        print(f"      · 429 응답: {' · '.join(bits) or '알려주는 헤더 없음'}")
        if body:
            print(f"      · 429 본문: {body}")
    except Exception:
        pass


def _is_vercel_challenge(e):
    """Vercel Attack Mode 가 막은 것인지 봅니다.

    판단 기준은 429 와 Server 헤더 두 가지입니다. 본문까지 보지 않는
    이유는, 본문을 읽어버리면 혹시 재시도할 때 쓸 수 없기 때문입니다.
    """
    try:
        server = str((e.headers or {}).get("Server") or "")
    except Exception:
        server = ""
    return e.code == 429 and server.strip().lower().startswith("vercel")


def _get(url):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다."""
    # 헤더는 평범하게 둡니다.
    #
    # 한때 Origin 과 Sec-Fetch-* 를 넣어 브라우저처럼 보이게 했습니다.
    # 근거가 없는 추측이었고, GET 에 Origin 이 붙는 것은 오히려 흔치
    # 않아 방화벽이 더 수상하게 볼 수 있습니다. 그래서 되돌렸습니다.
    # Referer 도 /recruit 로 박아뒀는데 그 주소는 회사마다 달라서
    # 메가존에서는 404 입니다. 대문 주소로 바꿉니다.
    host = url.split("/")[2] if "//" in url else ""
    req = urllib.request.Request(url, headers={
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        "User-Agent": UA,
        "Referer": f"https://{host}/" if host else "",
    })
    last = None
    TRIES = 2
    for i in range(TRIES):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            # Vercel Attack Mode 는 기다려도 재시도해도 풀리지 않습니다.
            # 자바스크립트 챌린지라 파이썬으로는 통과할 수 없습니다.
            # 그래서 즉시 '차단 중' 으로 알리고 끝냅니다. 두드리지 않습니다.
            if _is_vercel_challenge(e):
                raise RuntimeError(
                    BLOCKED + "Vercel Attack Mode 에 막혔습니다. "
                    "나인하이어가 방화벽 예외를 넣으면 저절로 다시 들어옵니다."
                ) from None

            # 그 밖의 429 는 정체를 모르니 응답에 적힌 단서를 찍습니다.
            if e.code == 429:
                _why_blocked(e)
            # 5xx 와 429 는 기다리면 풀릴 때가 있습니다. 다만 재시도는
            # 두 번까지입니다. 아홉 곳이 각자 길게 기다리면 갱신 시간만
            # 30분 늘어나고(한 번은 60분 제한에 걸려 중단됐습니다),
            # 상대 서버를 계속 두드리는 셈이 됩니다.
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

    부르기 전에 잠깐 쉽니다. 요청 자체는 회사당 1회뿐이라 속도가 문제는
    아니지만(위 설명 참고), 한 플랫폼을 연달아 부르지 않는 쪽이 예의라
    5초는 그대로 둡니다. 아홉 곳이면 45초로 전체 갱신에서 무시할 수준입니다.
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
