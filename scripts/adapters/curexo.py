# -*- coding: utf-8 -*-
"""
큐렉소(career.curexo.com) 채용 수집기.

목록  GET https://career.curexo.com/{노션페이지ID}

수술로봇·재활로봇. 코스닥. 한국야쿠르트(hy) 계열입니다.

노션으로 만든 채용 페이지입니다
--------------------------------
oopy 라는 서비스가 노션 페이지를 웹사이트처럼 보여줍니다. 주소 끝의
긴 UUID 가 노션 페이지 번호입니다.

    https://career.curexo.com/a049e805-13d8-4ccc-97d2-a3fab412be13
                             └─ 이것이 노션 페이지 ID

companies.json 의 code 에 이 UUID 를 적습니다. 페이지를 다시 만들면
번호가 바뀌니, 0건이 계속되면 주소를 먼저 확인하세요.

데이터를 어디서 읽는가
----------------------
화면은 자바스크립트가 그리지만, 서버가 보내는 HTML 안에 노션 원본이
통째로 들어 있습니다. __NEXT_DATA__ 의 recordMap 입니다.
요청 한 번이면 끝나고 별도 API 도 없습니다.

    props.pageProps.recordMap.collection   데이터베이스 정의(칸 이름)
    props.pageProps.recordMap.block        각 행(공고)

칸 이름이 아니라 키로 찾아야 합니다
-----------------------------------
노션은 칸마다 짧은 키를 붙입니다. 사람이 읽을 수 없는 형태입니다.

    "VgC:"  → 모집 인원
    "a@>F"  → 채용 유형
    "title" → 이름
    "1057952d-171c-..."  → 근무지

그래서 collection 의 schema 에서 "이름 → 키" 표를 먼저 만들고, 그 키로
값을 꺼냅니다. 키를 코드에 박아두면 안 됩니다. 노션에서 칸을 지웠다
다시 만들면 키가 바뀝니다.

칸 구성 (2026-09-15 확인)
-------------------------
    이름         재활로봇 SW개발(미들웨어)
    모집 전형     경력
    채용 유형     정규직
    근무지        기술연구소 / 본사
    지원 마감일    채용 시까지
    모집 인원     1명
    학력 요건     석사 이상
    우대 요건     RTX 등 RTOS 경험자 外

마감일에 대하여
--------------
2026-09-15 기준 다섯 건 모두 "채용 시까지" 였습니다. 날짜가 아니므로
closesAt 을 비웁니다. 비우면 사이트가 상시채용으로 표시합니다.

공고마다 고유 주소가 없습니다
-----------------------------
노션 데이터베이스의 행이라 각 공고에 열 수 있는 주소가 없습니다.
모두 목록 페이지로 보냅니다. 없는 주소를 지어내지 않습니다.
"""
import html
import json
import re
import time
import urllib.error
import urllib.request

BASE = "https://career.curexo.com"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

NEXT_DATA = re.compile(
    r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S | re.I)

# 마감 표시가 이 말이면 날짜가 아닙니다.
ALWAYS = re.compile(r"채용\s*시|상시|수시", re.I)

# 모집 전형 → 사이트 career 표기.
CAREER = {"경력": "경력", "신입": "신입", "신입/경력": "신입/경력",
          "무관": "무관", "경력무관": "무관", "인턴": "무관"}


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


def _plain(v):
    """노션 값은 [["글자", ...], ...] 형태입니다. 글자만 이어 붙입니다."""
    if not isinstance(v, list):
        return ""
    out = []
    for part in v:
        if isinstance(part, list) and part and isinstance(part[0], str):
            out.append(part[0])
    return re.sub(r"\s+", " ", html.unescape("".join(out))).strip()


def _date(v):
    """'2026.09.30' → '2026-09-30'. "채용 시까지" 면 빈 문자열(상시채용)."""
    if ALWAYS.search(str(v or "")):
        return ""
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", str(v or ""))
    if not m:
        return ""
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def _career(v):
    t = str(v or "").strip()
    if not t:
        return "무관"
    has_new = "신입" in t
    has_exp = "경력" in t
    if has_new and has_exp:
        return "신입/경력"
    if has_exp:
        return "경력"
    if has_new:
        return "신입"
    return CAREER.get(t, "무관")


def list_open(code):
    """공고 목록. probe 용으로 밖에서도 씁니다."""
    page_id = (code or "").strip().strip("/")
    if not page_id:
        raise RuntimeError(
            "curexo: code 가 비어 있습니다. "
            "채용 페이지 주소 끝의 노션 페이지 ID 를 적으세요.")

    url = f"{BASE}/{page_id}"
    page = _get(url)

    m = NEXT_DATA.search(page)
    if not m:
        print(f"  ! 큐렉소: 노션 데이터를 찾지 못했습니다. ({url})")
        print(f"    받은 HTML {len(page)}자 · "
              f"'__NEXT_DATA__' {page.count('__NEXT_DATA__')}회")
        return []

    try:
        data = json.loads(m.group(1))
        pp = (data.get("props") or {}).get("pageProps") or {}
        record = pp.get("recordMap") or {}
        cols = record.get("collection") or {}
        blocks = record.get("block") or {}
    except Exception as e:
        print(f"  ! 큐렉소: 노션 데이터를 읽지 못했습니다: {e}")
        return []

    if not cols:
        print(f"  ! 큐렉소: 데이터베이스가 없습니다. 페이지 ID 를 확인하세요.")
        return []

    col = list(cols.values())[0].get("value") or {}
    col_id = col.get("id")
    schema = col.get("schema") or {}

    # 칸 이름 → 키. 키는 노션이 자동으로 붙이는 값이라 바뀔 수 있습니다.
    by_name = {}
    for key, spec in schema.items():
        name = str((spec or {}).get("name") or "").strip()
        if name:
            by_name[name] = key

    rows = []
    for b in blocks.values():
        v = b.get("value") if isinstance(b, dict) else None
        if not v or v.get("type") != "page":
            continue
        # 이 데이터베이스에 속한 행만 담습니다.
        if col_id and v.get("parent_id") != col_id:
            continue
        props = v.get("properties") or {}

        def get(name):
            key = by_name.get(name)
            return _plain(props.get(key)) if key else ""

        title = get("이름") or _plain(props.get("title"))
        if not title:
            continue

        rows.append({
            "id": str(v.get("id") or ""),
            "title": title,
            "career": get("모집 전형"),
            "employment": get("채용 유형"),
            "location": get("근무지"),
            "deadline": get("지원 마감일"),
        })

    if not rows:
        print(f"  ! 큐렉소: 공고를 찾지 못했습니다. "
              f"(블록 {len(blocks)}개, 칸 {list(by_name)[:6]})")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    code = company["code"]

    rows = list_open(code)
    url = f"{BASE}/{code.strip().strip('/')}"

    jobs = []
    for x in rows:
        # 정규직이 아니면 제목에 표시합니다.
        title = x["title"]
        emp = x["employment"]
        if emp and emp != "정규직" and emp not in title:
            title = f"{title} ({emp})"

        jobs.append({
            # 노션 블록 ID 는 UUID 라 깁니다. 앞부분만 씁니다.
            "id": f"curexo-{x['id'].replace('-', '')[:16]}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            "title": title,
            "location": x["location"],
            "career": _career(x["career"]),
            # 게시일을 주지 않습니다.
            "postedAt": "",
            # "채용 시까지" 면 빈 문자열이 됩니다(상시채용).
            "closesAt": _date(x["deadline"]),
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            # 공고마다 고유 주소가 없습니다. 목록으로 보냅니다.
            "sourceUrl": url,
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })

    return jobs
