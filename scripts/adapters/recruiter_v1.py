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
    JW중외제약    jwholdings  JW생명과학·JW케미타운 등 포함
    메디톡스      medytox

함정 1 — JSON 이 아니라 form 으로 보내야 합니다
-----------------------------------------------
경로가 .json 으로 끝나서 JSON 본문을 받을 것처럼 보이지만 아닙니다.
application/x-www-form-urlencoded 로 보내야 합니다.

JSON 으로 보내면 오류가 나지 않고 200 을 돌려주는데, 파라미터를 전부
무시하고 기본값(1쪽 5건)만 줍니다. 그래서 페이지를 넘겨도 같은 5건이
계속 오고, 그것을 쌓으면 같은 공고가 수십 번 담깁니다.

2026-09-11 수집에서 실제로 그랬습니다.

    JW중외제약  160건  (실제 4건 × 잘못된 반복)
    효성그룹    120건  (실제 3건)
    메디톡스     40건  (실제 1건)

페이지 반복 대신 pageSize 를 크게 주세요
----------------------------------------
form 으로 제대로 보내면 pageSize 가 먹습니다. 100 을 주면 한 번에 다 옵니다.
JW 기준 lastPage 가 1 이 되어 페이지를 넘길 일이 없어집니다.

함정 2 — jobnoticeStateCode 만으로는 부족합니다
-----------------------------------------------
10 을 주면 "진행중" 쪽만 추리지만 최근 마감된 것이 섞여 옵니다.
JW 기준 25건이 왔고 그중 접수중은 4건이었습니다.
receiptState 가 "접수중" 인 것만 담아 한 번 더 거릅니다.

함정 3 — 날짜가 자바 객체로 옵니다
----------------------------------
    "applyEndDate": {"year":126, "month":8, "date":20, "time":1789916399000, ...}

year 는 1900 을 더해야 하고(126 → 2026), month 는 0부터 셉니다(8 → 9월).
헷갈리기 쉬우니 time(밀리초)만 쓰고 나머지는 보지 않습니다.

숨은 경로를 어떻게 찾았는가
---------------------------
목록 화면의 HTML 에는 <div class="list-bbs"> 빈 껍데기뿐이고 공고는
자바스크립트가 채웁니다. XHR 후킹은 새로고침 때마다 풀려 초기 요청을
놓쳤는데, performance.getEntriesByType('resource') 로 이미 끝난 요청
기록을 뒤져 찾았습니다. 파라미터 이름과 형식도 같은 방법으로 확인했습니다.

응답 구조 (2026-09-11 실제 확인)
--------------------------------
{ "pageUtil": {"currentPage":1, "lastPage":1, "recordCount":25, ...},
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

PAGE_SIZE = 100   # form 으로 보내면 먹습니다. 대개 한 번에 다 옵니다.
MAX_PAGES = 10    # 그래도 넘칠 때를 위한 안전장치.

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


def _post(url, params):
    """form 인코딩으로 보냅니다. JSON 으로 보내면 파라미터가 무시됩니다."""
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        url, method="POST", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
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

    rows, seen, closed, total = [], set(), 0, None
    for p in range(1, MAX_PAGES + 1):
        j = _post(url, {
            "recruitClassSn": "", "recruitClassName": "",
            # 10 = 진행중. 최근 마감된 것이 섞여 오므로 아래에서 다시 거릅니다.
            "jobnoticeStateCode": "10",
            "pageSize": str(PAGE_SIZE),
            "searchByNameOnly": "true",
            "currentPage": str(p),
        })
        got = j.get("list") or []
        page_util = j.get("pageUtil") or {}
        if total is None:
            total = page_util.get("recordCount")
        if not got:
            break

        added = 0
        for x in got:
            sn = x.get("jobnoticeSn")
            # 같은 공고가 두 번 담기지 않게 합니다. 페이지가 안 넘어가는
            # 서버를 만나도 숫자가 부풀지 않습니다.
            if sn in seen:
                continue
            seen.add(sn)
            added += 1
            if str(x.get("receiptState") or "").strip() == "접수중":
                rows.append(x)
            else:
                closed += 1

        last_page = page_util.get("lastPage") or 1
        if added == 0 or p >= last_page:
            break
        time.sleep(0.3)

    if not rows:
        print(f"  ! recruiter_v1({code}): 접수중 공고가 없습니다. ({url})")
        print(f"    받은 {len(seen)}건 중 마감 {closed}건. 전체 {total}건.")
        print(f"    0건이 계속되면 신버전으로 옮겼는지 확인하고 "
              f"recruiter 어댑터로 바꾸세요.")
    else:
        print(f"  · recruiter_v1({code}): 접수중 {len(rows)}건 "
              f"(받은 {len(seen)}건 중 마감 {closed}건 제외)")
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
