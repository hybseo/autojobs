# -*- coding: utf-8 -*-
"""
NC Careers(careers.ncsoft.com) 수집기. 엔씨소프트 그룹 통합 채용입니다.

목록  POST https://careers.ncsoft.com/interface/apply/list
상세  https://careers.ncsoft.com/apply/view/{jopenId}?companyId={regOpId}

함정 1 — CSRF 토큰이 없으면 403
------------------------------
그냥 API 를 부르면 403 이 떨어집니다. 지금까지 붙인 어댑터 중 처음 나온
방식이라 적어둡니다.

목록 페이지(/apply/list)를 먼저 GET 하면 HTML 머리에 이런 게 들어 있습니다.

    <meta name="_csrf" content="138bac2c-...">
    <meta name="_csrf_header" content="X-CSRF-TOKEN">

이 값을 X-CSRF-TOKEN 헤더에 넣어야 200 이 옵니다. 토큰은 요청마다 새로
발급되므로 캐시하지 말고 매 실행마다 페이지를 한 번 읽어 꺼내세요.

세션 쿠키도 함께 받아 두어야 합니다. 토큰만 있고 쿠키가 없으면 다시
403 이 납니다. 아래에서 http.cookiejar 를 쓰는 이유입니다.

함정 2 — 화면의 4분할은 필터일 뿐입니다
--------------------------------------
사이트 첫 화면이 Development / Business / System & Information /
Management Supporting 로 나뉘어 있고 각각 건수가 적혀 있습니다.
그건 구직자가 골라 보는 필터이고, 공고가 그 수만큼 따로 있는 게 아닙니다.

job_group_cd 를 빈 문자열로 두면 네 영역이 전부 한 번에 옵니다.
2026-09-09 확인 기준 76 + 14 + 3 + 0 = 93건이 그대로 나왔습니다.
직군별로 네 번 부르지 마세요. 같은 것을 네 번 나눠 받을 뿐입니다.

본문에 대하여
------------
목록에는 본문이 없습니다. 상세 페이지는 자바스크립트로 그려지고,
본문을 불러오는 내부 경로(POST /template/html//apply/view)는 재현에
실패했습니다(404). 그래서 description 을 비우고 원문 링크로 보냅니다.

삼성·한화·SK 어댑터와 같은 방침입니다. 잘못된 본문을 지어내느니
원문으로 보내는 편이 낫고, 본문이 없으면 자체 상세 페이지와 JobPosting
스키마도 만들어지지 않습니다. 그게 구글 구조화 데이터 정책에 맞습니다.

나중에 본문 경로를 찾으면 description 만 채우면 됩니다.

계열사에 대하여
--------------
한 사이트에 여러 법인이 섞여 옵니다. 2026-09-09 확인 기준
NC / NC AI / 퍼스트스파크게임즈 / 77ST. Games 네 곳입니다.
companyNm 이 계열사를 정확히 주므로 그대로 회사명으로 씁니다.
"NC" 로 뭉치면 어느 회사 공고인지 알 수 없습니다.

응답 구조 (2026-09-09 실제 확인)
--------------------------------
result.State == "0" 이면 성공, result.data.record 가 공고 배열입니다.

    jopenId      101263        공고 번호. 상세 주소에 그대로 들어갑니다
    regOpId      NCH           법인 코드. 상세 주소의 companyId 입니다
    jopenNm                    공고 제목
    companyNm    NC AI         계열사명
    channelNm    경력          경력 구분(경력/신입/단기)
    startDt      2026.09.09    접수 시작. 점으로 구분됩니다
    endDt        2026.09.25    접수 마감
    dday         16            남은 일수. 숫자로 옵니다
    jobGroupName Business      직군
"""
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar

BASE = "https://careers.ncsoft.com"
LIST_PAGE = BASE + "/apply/list"
LIST_API = BASE + "/interface/apply/list"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# channelNm 이 한글로 그대로 옵니다.
# "단기" 는 단기계약직이라 신입/경력 구분이 아닙니다. "무관" 으로 접습니다.
CAREER = {"경력": "경력", "신입": "신입", "신입/경력": "신입/경력",
          "무관": "무관", "단기": "무관", "인턴": "무관"}

CSRF = re.compile(r'name="_csrf"\s+content="([^"]+)"')
CSRF_ALT = re.compile(r'content="([^"]+)"\s+name="_csrf"')


def _opener():
    """쿠키를 유지하는 opener. 세션 쿠키가 없으면 토큰이 있어도 403 입니다."""
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def _token(op):
    """목록 페이지에서 CSRF 토큰을 꺼냅니다. 못 찾으면 RuntimeError."""
    req = urllib.request.Request(LIST_PAGE, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9",
    })
    with op.open(req, timeout=25) as r:
        page = r.read().decode("utf-8", "replace")
    m = CSRF.search(page) or CSRF_ALT.search(page)
    if not m:
        raise RuntimeError(
            "NC: CSRF 토큰을 찾지 못했습니다. "
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
    time.sleep(0.3)

    body = urllib.parse.urlencode({
        "order_type": "ORDER_ETC", "order_direction": "desc",
        "page": "1", "pagesize": "500",
        "channelCds": "", "keywords": "", "job_group_cd": "",
        "search_text": "", "job_type_cd": "", "companyIds": "",
    }).encode()

    req = urllib.request.Request(LIST_API, method="POST", data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRF-TOKEN": token,
        "Referer": LIST_PAGE,
        "User-Agent": UA,
    })

    last = None
    for i in range(3):
        try:
            with op.open(req, timeout=25) as r:
                j = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code == 403:
                raise RuntimeError(
                    "NC: 403 입니다. CSRF 토큰이나 세션 쿠키가 거부됐습니다. "
                    "목록 페이지의 <meta name=\"_csrf\"> 를 확인하세요.") from None
            raise
        except Exception as e:
            last = e
            if i < 2:
                time.sleep(2 + i * 2)
    else:
        raise last

    res = j.get("result") or {}
    if str(res.get("State")) != "0":
        print(f"  ! NC: 응답이 성공이 아닙니다. {res.get('StateMsg')}")
        return []

    rows = (res.get("data") or {}).get("record") or []
    if not rows:
        print("  ! NC: 공고 목록이 비어 있습니다. "
              f"{LIST_API} 를 확인하세요.")
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
