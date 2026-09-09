# -*- coding: utf-8 -*-
"""
NEXON COMPANY Careers 수집기. 넥슨 그룹 통합 채용입니다.

목록  POST https://career-gateway.nexon.com/career/v1/open/job-posts
계열사 GET  https://career-gateway.nexon.com/career/v1/open/corps
원문  https://careers.nexon.com/recruit/{jobPostNo}

인증 토큰은 필요 없습니다. 경로에 open 이 들어간 공개 API 입니다.

지금까지 붙인 것 중 가장 가벼운 축입니다
----------------------------------------
목록 응답에 본문(contents)이 통째로 들어 있습니다. 상세를 따로 읽을
필요가 없어 요청이 공고 수와 무관하게 몇 회로 끝납니다.
Ashby·Greenhouse 와 같은 구조이고, 상대 서버 부담이 가장 적습니다.

넥슨게임즈를 찾다가 여기까지 왔습니다
------------------------------------
www.nexongames.co.kr 의 "채용공고 보기" 를 누르면 이 사이트로 넘어갑니다.
넥슨게임즈가 자체 채용 시스템을 쓰는 게 아니라 그룹 통합 사이트를
corpCodes=AG 로 걸러 쓰는 것입니다. 그래서 계열사 어댑터가 아니라
그룹 어댑터로 만들었습니다. LG·삼성·한화와 같은 방식입니다.

계열사 코드 (2026-09-09 확인)
    NX 넥슨코리아      NO 네오플          AG 넥슨게임즈
    HQ 넥슨에이치큐    DV 데브캣          MR 민트로켓
    UV 넥슨유니버스    SD 넥슨네트웍스    NU 넥슨커뮤니케이션즈
    MD 엔미디어플랫폼  DQ 딜로퀘스트      SE 넥슨스페이스
    XC 엔엑스씨

companies.json 의 "code" 에 쉼표로 적으면 그 계열사만 담습니다.

    "code": "AG"            넥슨게임즈만
    "code": "NX,NO,AG"      셋만

code 를 빈 문자열로 두면 이 어댑터는 그룹 전체를 받지만,
fetch_jobs.py 가 파일을 읽는 단계에서 먼저 막힙니다.

    companies.json 143번째 항목에 ['code'] 이(가) 없습니다.

필수항목 검사가 `not company.get(k)` 라서 빈 문자열도 없는 값으로 봅니다.
그래서 companies.json 에는 계열사 코드를 모두 적어 두었습니다.
계열사가 늘면 /career/v1/open/corps 로 확인해 추가하세요.

LG 어댑터의 companyCodeList 와 같은 취지입니다.

함정 1 — 페이지가 1부터 시작합니다
----------------------------------
page=0 을 보내면 빈 응답이 옵니다. NHN(page=0 시작)과 반대라 헷갈립니다.

함정 2 — 마감일 필드가 없습니다
-------------------------------
startDate 는 있는데 마감일에 해당하는 필드가 없습니다. dday 도 대부분
빈 값이고, 2026-09-09 기준 142건 중 1건에만 "D-4" 가 들어 있었습니다.
넥슨은 사실상 전부 상시채용입니다.

closesAt 을 비우면 사이트가 상시채용으로 표시합니다. 없는 마감일을
지어내지 않습니다.

함정 3 — 중첩 객체입니다
------------------------
careerType 과 employmentType 이 문자열이 아니라 {code, description}
객체로 옵니다. 그대로 쓰면 화면에 "[object Object]" 가 찍힙니다.
아래에서 description 만 꺼내 씁니다.

    careerType     {"code":"30","description":"경력무관"}
    employmentType {"code":"20","description":"계약직"}

응답 구조 (2026-09-09 실제 확인)
--------------------------------
{ "list": [ ... ], "pagination": {"page":1,"size":15,"total":142} }

    jobPostNo   10276          공고 번호. 원문 주소에 그대로 들어갑니다
    corpName    넥슨게임즈      계열사명
    title                      공고 제목
    contents                   본문 HTML. 중앙값 8,800자
    startDate   2026.09.04     게시일. 점으로 구분됩니다
    workingArea 판교           근무지
    careerType / employmentType  위 참고
"""
import html
import json
import re
import time
import urllib.error
import urllib.request

API = "https://career-gateway.nexon.com/career/v1/open/job-posts"
CORPS = "https://career-gateway.nexon.com/career/v1/open/corps"
SITE = "https://careers.nexon.com/recruit/{}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

PAGE = 100
MAX_PAGES = 20  # 안전장치. 2,000건이면 충분합니다.

# careerType.description 이 한글로 그대로 옵니다.
# "경력무관" 은 사이트 표기가 "무관" 이므로 옮깁니다.
CAREER = {"경력": "경력", "신입": "신입", "경력무관": "무관",
          "무관": "무관", "신입/경력": "신입/경력"}


def _post(body):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다."""
    req = urllib.request.Request(
        API, method="POST", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json",
                 "Origin": "https://careers.nexon.com",
                 "Referer": "https://careers.nexon.com/",
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


def _desc(v):
    """{code, description} 객체에서 표시용 문자열만 꺼냅니다."""
    if isinstance(v, dict):
        return (v.get("description") or "").strip()
    return str(v or "").strip()


def _date(v):
    """'2026.09.04' → '2026-09-04'. 값이 없으면 빈 문자열."""
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", str(v or ""))
    if not m:
        return ""
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def _dday(v):
    """'D-4' → 4. 부호를 그대로 읽으면 음수가 되어 마감으로 취급됩니다."""
    t = str(v or "").strip()
    if not t:
        return None
    if re.search(r"오늘|D-?DAY", t, re.I):
        return 0
    m = re.search(r"\d+", t)
    return int(m.group(0)) if m else None


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def list_open(codes=""):
    """공고 목록. codes 가 비면 그룹 전체입니다. probe 용으로 밖에서도 씁니다."""
    corp_codes = [c.strip() for c in (codes or "").split(",") if c.strip()]

    rows, page = [], 1
    while page <= MAX_PAGES:
        j = _post({
            "corpCodes": corp_codes, "jobCategories": [],
            "careerTypes": [], "employmentTypes": [], "workingAreas": [],
            "query": None, "page": page, "size": PAGE,
        })
        got = j.get("list") or []
        rows += got
        total = (j.get("pagination") or {}).get("total") or 0
        if not got or len(rows) >= total:
            break
        page += 1
        time.sleep(0.3)

    if not rows:
        print("  ! 넥슨: 공고 목록이 비어 있습니다. "
              f"code 값({codes!r})이 맞는지, {CORPS} 로 계열사 코드를 확인하세요.")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    slug = company["slug"]
    rows = list_open(company.get("code", ""))

    jobs = []
    for x in rows:
        no = x.get("jobPostNo")
        if not no:
            continue

        raw = x.get("contents") or ""
        text = strip_html(raw)
        # 본문이 이미지뿐인 공고가 있습니다(2026-09-09 기준 142건 중 12건).
        # 억지로 분해하지 않고 원문으로 보냅니다.
        image_only = len(text) < 50 and "<img" in raw.lower()

        jobs.append({
            "id": f"nexon-{no}",
            "unit": "공고",
            # 계열사명을 그대로 씁니다. "넥슨" 으로 뭉치면 어느 회사인지 모릅니다.
            "company": (x.get("corpName") or company["name"]).strip(),
            "companySlug": slug,
            "title": (x.get("title") or "").strip(),
            "location": (x.get("workingArea") or "").strip(),
            "career": CAREER.get(_desc(x.get("careerType")), "무관"),
            "postedAt": _date(x.get("startDate")),
            # 마감일 필드가 없습니다. 비우면 상시채용으로 표시됩니다.
            "closesAt": "",
            "dday": _dday(x.get("dday")),
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": SITE.format(no),
            # 본문이 목록에 함께 옵니다. 상세를 따로 읽지 않습니다.
            "description": raw if not image_only else "",
        })

    return jobs
