# -*- coding: utf-8 -*-
"""
SK Careers 수집기. SK그룹 통합 채용 플랫폼입니다.

  목록  POST https://www.skcareers.com/Recruit/GetRecruitList
  상세  https://www.skcareers.com/Recruit/Detail/{공고번호}

robots.txt (2026-08-31 확인)
---------------------------
  Allow: /Recruit
  Disallow: /*?searchText=

/Recruit 경로가 명시적으로 허용돼 있습니다. 금지된 것은 검색어를 주소
뒤에 붙이는 요청뿐입니다. 그래서 searchText 는 항상 빈 값으로 두고
본문으로만 보냅니다. 주소에 검색어를 붙이지 마세요.

계열사를 골라 담습니다
----------------------
SK그룹은 반도체·통신·에너지·바이오까지 있습니다. 전부 받으면 사이트
성격이 흐려집니다. companies.json 의 "affiliates" 에 회사명을 적으면
그 계열사 공고만 담습니다.

  "affiliates": ["SK온", "SK아이이테크놀로지"]

비워두면 전부 받습니다. LG 어댑터에서 companyCodeList 로 하던 것과
같은 취지인데, SK 는 corpCode 값을 아직 몰라 회사명으로 거릅니다.
corpCode 를 알아내면 요청 단계에서 거르는 편이 더 깔끔합니다.

요청 형식
---------
개발자도구로 확인한 실제 요청은 폼 형식입니다.

  sort=2&searchText=&corpCode=&jobRole=0&recruitType=&workingType=&workingRegion=

만들 때의 한계
--------------
응답 필드 이름은 아직 확인하지 못했습니다. 그래서 FIELD 표에 후보를
여러 개 두고, 목록을 찾지 못하면 무엇을 받았는지 로그에 남깁니다.
첫 실행 로그를 확인하고, 찍힌 실제 이름을 FIELD 표 맨 앞으로 옮기세요.
"""
import json
import re
import html
import urllib.parse
import urllib.request

LIST_URL = "https://www.skcareers.com/Recruit/GetRecruitList"
DETAIL = "https://www.skcareers.com/Recruit/Detail/{}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# 개발자도구에서 확인한 파라미터 이름입니다. 값은 화면이 기본 상태일 때의 것.
# searchText 는 반드시 빈 값으로 둡니다. robots.txt 가 검색어 요청을 막습니다.
PARAMS = {
    "sort": "2",
    "searchText": "",
    "corpCode": "",
    "jobRole": "0",
    "recruitType": "",
    "workingType": "",
    "workingRegion": "",
}

# 응답 필드 이름을 몰라 후보를 여러 개 둡니다.
# 첫 실행 로그에 실제 이름이 찍히면 맨 앞으로 옮기고 나머지는 지우세요.
FIELD = {
    "id":      ("recruitNo", "recruitSeq", "recruitId", "seq", "id"),
    "title":   ("recruitTitle", "title", "subject", "recruitNm"),
    "company": ("corpName", "companyName", "corpNm", "company"),
    "close":   ("endDate", "recruitEndDate", "closeDate", "endDt"),
    "open":    ("startDate", "recruitStartDate", "openDate", "startDt"),
    "type":    ("recruitType", "recruitTypeName", "employmentType"),
}


def _pick(row, key):
    """FIELD 표의 후보 이름을 차례로 찾습니다."""
    for name in FIELD[key]:
        v = row.get(name)
        if v not in (None, ""):
            return v
    return ""


def _first_list(o, depth=0):
    """응답 어딘가에 있는 공고 배열을 찾습니다. 키 이름이 달라도 견딥니다."""
    if depth > 4:
        return None
    if isinstance(o, list):
        if o and isinstance(o[0], dict):
            return o
        return None
    if isinstance(o, dict):
        for v in o.values():
            got = _first_list(v, depth + 1)
            if got:
                return got
    return None


def _request(as_json):
    """JSON 과 폼 두 형식을 모두 시도하기 위해 분리했습니다."""
    if as_json:
        data = json.dumps(PARAMS).encode()
        ctype = "application/json"
    else:
        data = urllib.parse.urlencode(PARAMS).encode()
        ctype = "application/x-www-form-urlencoded; charset=UTF-8"
    req = urllib.request.Request(LIST_URL, method="POST", data=data, headers={
        "Content-Type": ctype,
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.skcareers.com/Recruit",
        "User-Agent": UA,
    })
    with urllib.request.urlopen(req, timeout=25) as r:
        raw = r.read().decode("utf-8", "replace")
    try:
        return json.loads(raw), raw
    except Exception:
        return None, raw


def list_open(affiliates=()):
    """접수중 공고 목록. probe 용으로 밖에서도 씁니다."""
    # 개발자도구에서 확인한 실제 요청은 폼 형식입니다.
    #   sort=2&searchText=&corpCode=&jobRole=0&recruitType=&workingType=&workingRegion=
    # 폼을 먼저 보내고, 혹시 바뀌었을 때를 대비해 JSON 도 시도합니다.
    rows, last_raw = None, ""
    for as_json in (False, True):
        try:
            parsed, raw = _request(as_json)
            last_raw = raw
        except Exception as e:
            last_raw = f"{type(e).__name__}: {e}"
            continue
        if parsed is None:
            continue
        rows = _first_list(parsed)
        if rows:
            break

    if not rows:
        # 여기서 조용히 빈 목록을 돌려주면 원인을 알 수 없습니다.
        print("      ! SK: 공고 목록을 찾지 못했습니다. 응답 앞부분:")
        print("        " + str(last_raw)[:300].replace("\n", " "))
        return []

    if affiliates:
        keep = []
        for x in rows:
            name = str(_pick(x, "company"))
            if any(a in name for a in affiliates):
                keep.append(x)
        if not keep:
            seen = sorted({str(_pick(x, "company")) for x in rows})[:12]
            print(f"      ! SK: 지정한 계열사 공고가 없습니다. "
                  f"받은 회사명: {seen}")
        rows = keep
    return rows


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def _date(v):
    m = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", str(v or ""))
    if not m:
        return ""
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    slug = company["slug"]
    affiliates = company.get("affiliates") or []
    rows = list_open(affiliates)

    jobs = []
    for x in rows:
        rid = _pick(x, "id")
        if not rid:
            continue
        title = str(_pick(x, "title"))
        name = str(_pick(x, "company")) or company["name"]
        jobs.append({
            "id": f"sk-{rid}",
            "unit": "공고",
            # 계열사명을 그대로 씁니다. "SK그룹" 으로 뭉치면 어느 회사인지 모릅니다.
            "company": name,
            "companySlug": slug,
            "title": title,
            "location": "",
            # SK 는 신입/경력 구분을 목록에서 확실히 주지 않습니다. 지어내지 않습니다.
            "career": "무관",
            "postedAt": _date(_pick(x, "open")),
            "closesAt": _date(_pick(x, "close")),
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": DETAIL.format(rid),
            # 목록만으로는 본문을 알 수 없습니다. 원문으로 보냅니다.
            "description": "",
        })
    return jobs
