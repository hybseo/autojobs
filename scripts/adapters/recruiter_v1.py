# -*- coding: utf-8 -*-
"""
리크루터(recruiter.co.kr) 구버전 수집기.

목록  POST https://{code}.recruiter.co.kr/app/jobnotice/list.json
원문  https://{code}.recruiter.co.kr/app/jobnotice/view?systemKindCode={종류}&jobnoticeSn={번호}

recruiter.py 와 무엇이 다른가
------------------------------
같은 회사(인크루트 리크루터)의 서비스인데 화면이 두 세대입니다.

    신버전  /career/home         api-recruiter.recruiter.co.kr 의 JSON API
    구버전  /app/jobnotice/list  이 파일

신버전용 어댑터로 구버전 회사를 부르면 400 이 떨어집니다. 회사가 신버전으로
옮기면 이 어댑터가 0건이 되니 그때는 recruiter.py 로 바꾸고 code 만 옮기세요.

2026-09-11 확인 기준 구버전을 쓰는 곳
    효성그룹     hyosung     계열사 여럿
    JW중외제약    jwholdings  JW생명과학 등 포함
    메디톡스      medytox
    차바이오텍     chamc

화면 HTML 을 긁으면 안 됩니다 — 실제로 그래서 0건이 났습니다
------------------------------------------------------------
처음에는 목록 화면의 <li> 를 파싱하도록 짰습니다. 개발자도구로 보면
data-jobnoticesn 속성이 분명히 10개 있었습니다.

그런데 2026-09-11 수집에서 네 곳 모두 0건이 나왔습니다. 서버가 주는 HTML 을
그대로 받아 보니 <div class="list-bbs"> 빈 껍데기뿐이고 그 안에 <ul> 조차
없었습니다. 공고는 자바스크립트가 나중에 채워 넣는 것이었습니다.

개발자도구에 보이는 것은 자바스크립트가 다 돌고 난 뒤의 모습입니다.
수집기는 그 전 상태를 받습니다. 서버 응답을 직접 확인하고 짜세요.

숨은 JSON 경로를 어떻게 찾았는가
--------------------------------
XHR 후킹은 새로고침 때마다 풀려서 초기 요청을 놓쳤습니다. 대신
performance.getEntriesByType('resource') 로 이미 끝난 요청 기록을 뒤져
찾았습니다. 비슷한 상황에서 쓸 만한 방법입니다.

함정 1 — GET 은 받지 않습니다
-----------------------------
POST 로만 응답합니다. GET 으로 부르면 이렇게 돌려줍니다.

    {"code":"HttpRequestMethodNotSupportedException", ...}

함정 2 — 한 쪽에 5건씩 고정입니다
---------------------------------
maxRows·pageSize·limit·rows 를 다 넣어 봤지만 전부 무시하고 5건만 줍니다.
currentPage 를 올려 가며 여러 번 받아야 합니다.

JW중외제약은 전체 509건(102쪽)이었습니다. 다만 접수중은 앞쪽에 몰려 있어
끝까지 갈 필요는 없습니다. 아래에서 접수중이 한 건도 없는 쪽이 두 번
연달아 나오면 멈춥니다.

함정 3 — 마감된 공고가 함께 옵니다
----------------------------------
receiptState 가 "접수중" 인 것만 담습니다. 신버전의 submissionStatus 와
같은 역할입니다. 2026-09-11 JW 기준 20건 중 4건이 접수마감이었습니다.

함정 4 — 날짜가 자바 객체로 옵니다
----------------------------------
    "applyEndDate": {"year":126, "month":8, "date":20, "time":1789916399000, ...}

year 는 1900 을 더해야 하고(126 → 2026), month 는 0부터 셉니다(8 → 9월).
헷갈리기 쉬우니 time(밀리초)만 쓰고 나머지는 보지 않습니다.

응답 구조 (2026-09-11 실제 확인)
--------------------------------
{ "pageUtil": {"currentPage":1, "lastPage":102, "recordCount":509, ...},
  "list": [ ... ] }

    jobnoticeSn      266223       공고 번호
    jobnoticeName                 공고 제목
    receiptState     접수중        접수 상태
    systemKindCode   MRS2         상세 주소에 필요합니다
    recruitClassName 수시          채용 구분
    applyStartDate   {time: ...}  접수 시작
    applyEndDate     {time: ...}  접수 마감
    deadlineCount    9            남은 일수

본문에 대하여
------------
상세 페이지도 자바스크립트로 그려집니다. 본문을 가져올 수 없어 원문 링크로
보냅니다. 삼성·한화·NC 어댑터와 같은 방침입니다.

계열사에 대하여
--------------
효성·JW 처럼 그룹 통합이면 계열사 공고가 섞여 옵니다. 회사 구분 필드가 없고
제목 앞 대괄호로만 표시되므로([JW생명과학] ...) 회사명은 name 을 그대로 씁니다.
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

KST = timezone(timedelta(hours=9))

MAX_PAGES = 40      # 한 쪽 5건이니 200건까지 봅니다.
EMPTY_STOP = 2      # 접수중이 없는 쪽이 이만큼 연달아 나오면 멈춥니다.

# recruitClassName → 사이트 career 표기.
CAREER = {"신입": "신입", "경력": "경력", "신입/경력": "신입/경력",
          "경력무관": "무관", "무관": "무관", "수시": "무관",
          "공채": "신입/경력", "상시": "무관", "인턴": "무관"}


def _base(code):
    c = (code or "").strip().rstrip("/")
    if not c:
        raise RuntimeError(
            "recruiter_v1: code 가 비어 있습니다. "
            "채용 사이트 앞자리를 적으세요. 예: hyosung")
    if c.startswith("http"):
        return c
    if "." in c:
        return "https://" + c
    return f"https://{c}.recruiter.co.kr"


def _post(url, body):
    """POST 로만 응답합니다. GET 은 받지 않습니다."""
    req = urllib.request.Request(
        url, method="POST", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json",
                 "X-Requested-With": "XMLHttpRequest",
                 "Accept-Language": "ko-KR,ko;q=0.9",
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


def _date(v):
    """자바 날짜 객체에서 날짜만. time(밀리초)만 쓰고 year·month 는 보지 않습니다."""
    if not isinstance(v, dict):
        return ""
    ms = v.get("time")
    if not isinstance(ms, (int, float)):
        return ""
    try:
        d = datetime.fromtimestamp(ms / 1000, KST)
    except (ValueError, OSError, OverflowError):
        return ""
    if d.year >= 2100:   # 먼 미래는 상시채용을 뜻하는 가짜 값입니다.
        return ""
    return d.strftime("%Y-%m-%d")


def _dday(v):
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if n >= 0 else None


def list_open(code):
    """접수중 공고만 골라 돌려줍니다. probe 용으로 밖에서도 씁니다."""
    base = _base(code)
    url = base + "/app/jobnotice/list.json"

    rows, closed, empty_run, total = [], 0, 0, None
    for p in range(1, MAX_PAGES + 1):
        j = _post(url, {"currentPage": p})
        got = (j.get("list") or [])
        if total is None:
            total = (j.get("pageUtil") or {}).get("recordCount")
        if not got:
            break

        live = [x for x in got if str(x.get("receiptState") or "").strip() == "접수중"]
        closed += len(got) - len(live)
        rows += live

        # 접수중은 앞쪽에 몰려 있습니다. 빈 쪽이 이어지면 멈춥니다.
        empty_run = empty_run + 1 if not live else 0
        if empty_run >= EMPTY_STOP:
            break

        last_page = (j.get("pageUtil") or {}).get("lastPage") or 0
        if p >= last_page:
            break
        time.sleep(0.3)

    if not rows:
        print(f"  ! recruiter_v1({code}): 접수중 공고가 없습니다. ({url})")
        print(f"    전체 {total}건 중 마감으로 걸러진 것 {closed}건.")
        print(f"    0건이 계속되면 신버전으로 옮겼는지 확인하고 "
              f"recruiter 어댑터로 바꾸세요.")
    elif closed:
        print(f"  · recruiter_v1({code}): 접수중 {len(rows)}건 "
              f"(마감 {closed}건 제외, 전체 {total}건)")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    code = company["code"]
    base = _base(code)

    rows = list_open(code)

    jobs = []
    for x in rows:
        sn = x.get("jobnoticeSn")
        if not sn:
            continue
        kind = str(x.get("systemKindCode") or "").strip()

        jobs.append({
            "id": f"recruiterv1-{slug}-{sn}",
            "unit": "공고",
            # 계열사 구분 필드가 없습니다. 등록한 이름을 씁니다.
            "company": name,
            "companySlug": slug,
            "title": str(x.get("jobnoticeName") or "").strip(),
            # 근무지를 주지 않습니다. 지어내지 않습니다.
            "location": "",
            "career": CAREER.get(str(x.get("recruitClassName") or "").strip(), "무관"),
            "postedAt": _date(x.get("applyStartDate")),
            "closesAt": _date(x.get("applyEndDate")),
            "dday": _dday(x.get("deadlineCount")),
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": (f"{base}/app/jobnotice/view"
                          f"?systemKindCode={urllib.parse.quote(kind)}"
                          f"&jobnoticeSn={sn}"),
            # 상세도 자바스크립트로 그려집니다. 원문으로 보냅니다.
            "description": "",
        })

    return jobs
