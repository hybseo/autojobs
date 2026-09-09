# -*- coding: utf-8 -*-
"""
NC Careers(careers.ncsoft.com) 수집기. 엔씨소프트 그룹 통합 채용입니다.

목록  POST https://careers.ncsoft.com/interface/apply/list
상세  https://careers.ncsoft.com/apply/view/{jopenId}?companyId={regOpId}

robots.txt 는 404 입니다. 규칙이 없으면 제한 없음이 표준 해석입니다.

함정 1 — CSRF 토큰이 없으면 403
-------------------------------
그냥 API 를 부르면 403 입니다. 목록 페이지(/apply/list)를 먼저 GET 하면
HTML 머리에 이런 게 들어 있습니다.

    <meta name="_csrf" content="138bac2c-...">
    <meta name="_csrf_header" content="X-CSRF-TOKEN">

이 값을 X-CSRF-TOKEN 헤더에 넣어야 200 이 옵니다. 토큰은 요청마다 새로
발급되므로 캐시하지 말고 매 실행마다 페이지를 읽어 꺼냅니다.
세션 쿠키도 함께 유지해야 합니다. 토큰만 있고 쿠키가 없으면 다시 403 입니다.

함정 2 — 접속이 느리거나 끊깁니다
---------------------------------
2026-09-09 깃허브 Actions 실행에서 이렇게 실패했습니다.

    ! NC: <urlopen error _ssl.c:993: The handshake operation timed out>

같은 시각 로컬에서는 TLS 핸드셰이크가 0.08초에 끝났고 인증서도 정상
(TLSv1.3, verify 0)이었습니다. 서버 설정 문제가 아니라, 클라우드에서
오는 접속에 응답을 늦추는 것으로 보입니다.

그래서 이 어댑터는 다른 곳보다 끈질기게 붙습니다.

  - 시간 제한을 60초로 넉넉히 둡니다(다른 어댑터는 25초).
  - 최대 4번 시도하고 간격을 3초씩 늘립니다(3, 6, 9초).
  - 마지막 시도에서는 인증서 검증과 TLS 버전을 완화합니다.
    그리팅 어댑터가 카카오게임즈·니어스랩에서 쓰는 것과 같은 방법입니다.
  - Connection: close 로 연결을 재사용하지 않습니다. 오래 붙들고 있는
    연결이 끊기는 쪽이 더 잘 실패했습니다.

그래도 실패하면 잡히지 않는 것이 맞습니다. 억지로 끌어오지 않습니다.

함정 3 — 화면의 4분할은 필터일 뿐입니다
--------------------------------------
첫 화면이 Development / Business / System & Information /
Management Supporting 로 나뉘고 각각 건수가 적혀 있습니다. 구직자가
골라 보는 필터이고, 공고가 그 수만큼 따로 있는 게 아닙니다.

job_group_cd 를 빈 문자열로 두면 네 영역이 한 번에 옵니다.
2026-09-09 확인 기준 76 + 14 + 3 + 0 = 93건이 그대로 나왔습니다.
직군별로 네 번 부르지 마세요.

본문에 대하여
------------
목록에는 본문이 없습니다. 상세 페이지는 자바스크립트로 그려지고,
본문을 불러오는 내부 경로(POST /template/html//apply/view)는 재현에
실패했습니다(404). 그래서 description 을 비우고 원문 링크로 보냅니다.

삼성·한화·SK 어댑터와 같은 방침입니다. 본문이 없으면 자체 상세 페이지와
JobPosting 스키마도 만들어지지 않습니다. 그게 구글 정책에 맞습니다.

계열사에 대하여
--------------
한 사이트에 여러 법인이 섞여 옵니다. 2026-09-09 확인 기준
NC / NC AI / 퍼스트스파크게임즈 / 77ST. Games 네 곳입니다.
companyNm 이 계열사를 정확히 주므로 그대로 회사명으로 씁니다.

응답 구조 (2026-09-09 실제 확인)
--------------------------------
result.State == "0" 이면 성공, result.data.record 가 공고 배열입니다.

    jopenId      101263        공고 번호. 상세 주소에 들어갑니다
    regOpId      NCH           법인 코드. 상세 주소의 companyId 입니다
    jopenNm                    공고 제목
    companyNm    NC AI         계열사명
    channelNm    경력          경력 구분(경력/신입/단기)
    startDt      2026.09.09    접수 시작. 점으로 구분됩니다
    endDt        2026.09.25    접수 마감
    dday         16            남은 일수. 숫자로 옵니다
"""
import http.cookiejar
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://careers.ncsoft.com"
LIST_PAGE = BASE + "/apply/list"
LIST_API = BASE + "/interface/apply/list"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# 접속이 느린 곳이라 다른 어댑터보다 넉넉히 둡니다.
TIMEOUT = 60
TRIES = 4

# channelNm 이 한글로 그대로 옵니다.
# "단기" 는 단기계약직이라 신입/경력 구분이 아닙니다. "무관" 으로 접습니다.
CAREER = {"경력": "경력", "신입": "신입", "신입/경력": "신입/경력",
          "무관": "무관", "단기": "무관", "인턴": "무관"}

CSRF = re.compile(r'name="_csrf"\s+content="([^"]+)"')
CSRF_ALT = re.compile(r'content="([^"]+)"\s+name="_csrf"')


def _loose_ctx():
    """마지막 시도용. 인증서 검증과 TLS 버전을 완화합니다.

    공개된 채용 공고를 읽을 뿐이고, 그러지 않으면 이 회사가 통째로
    빠지기 때문입니다. 그리팅 어댑터와 같은 판단입니다.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.minimum_version = ssl.TLSVersion.TLSv1
    try:
        ctx.set_ciphers("ALL:@SECLEVEL=0")
    except ssl.SSLError:
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
    return ctx


def _open(op, req, tries=TRIES):
    """끈질기게 시도합니다. 마지막에는 TLS 를 완화합니다.

    403 은 재시도해도 같으므로 바로 올립니다. 토큰이나 쿠키가 거부된
    것이라 기다린다고 달라지지 않습니다.
    """
    last = None
    for i in range(tries):
        try:
            ctx = _loose_ctx() if i == tries - 1 else None
            return op.open(req, timeout=TIMEOUT, context=ctx)
        except urllib.error.HTTPError as e:
            if e.code == 403:
                raise
            last = e
        except Exception as e:
            last = e
        if i < tries - 1:
            time.sleep(3 * (i + 1))
    raise last


def _opener():
    """쿠키를 유지하는 opener. 세션 쿠키가 없으면 토큰이 있어도 403 입니다."""
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def _token(op):
    """목록 페이지에서 CSRF 토큰을 꺼냅니다."""
    req = urllib.request.Request(LIST_PAGE, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        # 연결을 재사용하지 않습니다. 오래 붙들면 더 잘 끊깁니다.
        "Connection": "close",
        "Upgrade-Insecure-Requests": "1",
    })
    with _open(op, req) as r:
        page = r.read().decode("utf-8", "replace")

    m = CSRF.search(page) or CSRF_ALT.search(page)
    if not m:
        raise RuntimeError(
            "NC: CSRF 토큰을 찾지 못했습니다. "
            f"받은 HTML {len(page)}자 · '_csrf' {page.count('_csrf')}회. "
            "<meta name=\"_csrf\"> 가 사라졌는지 확인하세요.")
    return m.group(1)


def _date(v):
    """'2026.09.09' → '2026-09-09'. 값이 없으면 빈 문자열."""
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", str(v or ""))
    if not m:
        return ""
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def _dday(v):
    """남은 일수. 숫자로 오지만 'D-16' 형태에도 대비합니다."""
    t = str(v or "").strip()
    if not t:
        return None
    if re.search(r"오늘|D-?DAY", t, re.I):
        return 0
    m = re.search(r"\d+", t)
    return int(m.group(0)) if m else None


def list_open():
    """접수중 공고 목록. probe 용으로 밖에서도 씁니다.

    직군(job_group_cd)을 비워 네 영역을 한 번에 받습니다.
    """
    op = _opener()
    token = _token(op)
    time.sleep(0.5)

    body = urllib.parse.urlencode({
        "order_type": "ORDER_ETC", "order_direction": "desc",
        "page": "1", "pagesize": "500",
        "channelCds": "", "keywords": "", "job_group_cd": "",
        "search_text": "", "job_type_cd": "", "companyIds": "",
    }).encode()

    req = urllib.request.Request(LIST_API, method="POST", data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRF-TOKEN": token,
        "Origin": BASE,
        "Referer": LIST_PAGE,
        "Connection": "close",
        "User-Agent": UA,
    })

    try:
        with _open(op, req) as r:
            j = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise RuntimeError(
                "NC: 403 입니다. CSRF 토큰이나 세션 쿠키가 거부됐습니다. "
                "목록 페이지의 <meta name=\"_csrf\"> 를 확인하세요.") from None
        raise

    res = j.get("result") or {}
    if str(res.get("State")) != "0":
        print(f"  ! NC: 응답이 성공이 아닙니다. {res.get('StateMsg')}")
        return []

    rows = (res.get("data") or {}).get("record") or []
    if not rows:
        print(f"  ! NC: 공고 목록이 비어 있습니다. {LIST_API} 를 확인하세요.")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    slug = company["slug"]
    rows = list_open()

    jobs = []
    for x in rows:
        jid = x.get("jopenId")
        if not jid:
            continue
        # 상세 주소에 법인 코드가 필요합니다. 없으면 목록으로 보냅니다.
        corp = (x.get("regOpId") or "").strip()
        url = (f"{BASE}/apply/view/{jid}?companyId={corp}"
               if corp else LIST_PAGE)

        cls = (x.get("channelNm") or "").strip()
        jobs.append({
            "id": f"nc-{jid}",
            "unit": "공고",
            # 계열사명을 그대로 씁니다. "NC" 로 뭉치면 어느 회사인지 모릅니다.
            "company": (x.get("companyNm") or company["name"]).strip(),
            "companySlug": slug,
            "title": (x.get("jopenNm") or "").strip(),
            # 근무지를 주지 않습니다. 지어내지 않습니다.
            "location": "",
            "career": CAREER.get(cls, "무관"),
            "postedAt": _date(x.get("startDt")),
            "closesAt": _date(x.get("endDt")),
            "dday": _dday(x.get("dday")),
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": url,
            # 목록에 본문이 없고 상세는 자바스크립트로 그려집니다. 원문으로 보냅니다.
            "description": "",
        })

    return jobs
