# -*- coding: utf-8 -*-
"""
다우기술 채용 사이트 수집기.

목록  GET https://recruit.daou.co.kr/api/recruitment/list
상세  GET https://recruit.daou.co.kr/api/recruitment/detail?reNo={reNo}&annSeqNo={annSeqNo}
원문  https://recruit.daou.co.kr/detail/{reNo}/{annSeqNo}

인증 토큰은 필요 없습니다.

함정 1 — 응답은 JSON 입니다. XML 이 아닙니다
--------------------------------------------
브라우저 주소창으로 열면 XML 트리처럼 보입니다. 크롬이 그렇게 그려줄
뿐이고, 실제 Content-Type 은 application/json 입니다.

처음에 이걸 XML 로 착각해 ElementTree 로 파싱했다가

    not well-formed (invalid token): line 1, column 0

이 났습니다. 응답 첫 글자가 '{' 라 XML 파서가 바로 실패한 것입니다.
NHN 도 주소창에서는 XML 로 보이지만 Accept 헤더에 따라 JSON 이 옵니다.
주소창에 보이는 모습이 아니라 Content-Type 을 보세요.

함정 2 — comNm 을 믿지 마세요
-----------------------------
목록 응답의 comNm(회사명)이 "LS전선" 으로 잘못 내려옵니다. 사이트 자체는
다우기술 공식 채용 페이지가 맞고 LS전선과는 무관합니다. 다우기술이
여러 회사의 채용 시스템을 같은 틀로 만들면서 남은 설정으로 보입니다.

회사명은 이 값을 쓰지 말고 companies.json 의 name 을 그대로 씁니다.

함정 3 — 접수중 판별
--------------------
status 가 "접수중" 인 것만 접수중입니다. 목록 API 에 상태 필터가 없어
전체가 내려오므로 응답에서 걸러야 합니다.

본문에 대하여
------------
2026-09-09 확인 기준 상세의 annTxt 는 전부 이미지(<img>)였습니다.
HTML 태그를 걷어내면 글자가 0자입니다. 다우기술 블로그 카드 이미지를
본문 대신 넣는 방식입니다.

글자를 읽을 수 없으므로 description 을 비우고 원문으로 보냅니다.
나중에 텍스트 본문이 오는 공고가 생기면 아래 판정이 자동으로 처리합니다.

응답 구조 (2026-09-09 실제 확인)
--------------------------------
{ "result": "SUCCESS",
  "resultData": { "recruitmentList": [ ... ] },
  "resultMessage": "..." }

    reNo         912                     공고 번호
    annSeqNo     1                       공고 회차
    annTitle                             공고 제목
    enterTypeNm  경력 / 신입              경력 구분
    locationNms  ["판교본사"]             근무지. 배열입니다
    gigan        2026.08.31~2026.09.10   접수 기간 한 문자열
    dday         D-1                     남은 일수
    status       접수중                   접수 상태
"""
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://recruit.daou.co.kr"
LIST_API = BASE + "/api/recruitment/list"
DETAIL_API = BASE + "/api/recruitment/detail"
DETAIL = BASE + "/detail/{}/{}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# enterTypeNm 이 한글로 그대로 옵니다. 표에 없으면 "무관" 으로 접습니다.
CAREER = {"경력": "경력", "신입": "신입", "신입/경력": "신입/경력",
          "무관": "무관", "인턴": "무관"}


def _get(url):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다."""
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": BASE + "/recruit",
        "User-Agent": UA,
    })
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


def _parse_gigan(gigan):
    """'2026.08.31~2026.09.10' → ('2026-08-31', '2026-09-10')."""
    s = str(gigan or "")
    if "~" not in s:
        return "", ""
    a, b = s.split("~", 1)

    def one(v):
        m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", v)
        if not m:
            return ""
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    return one(a), one(b)


def _dday(v):
    """'D-1' → 1. 부호를 그대로 읽으면 음수가 되어 마감으로 취급됩니다."""
    t = str(v or "").strip()
    if not t:
        return None
    if re.search(r"오늘|D-?DAY", t, re.I):
        return 0
    m = re.search(r"\d+", t)
    return int(m.group(0)) if m else None


def _location(v):
    """locationNms 는 배열입니다. 여러 곳이면 대표 한 곳만 적고 수를 붙입니다."""
    if isinstance(v, list):
        names = [str(x).strip() for x in v if str(x).strip()]
    elif v:
        names = [str(v).strip()]
    else:
        names = []
    if not names:
        return ""
    return names[0] if len(names) == 1 else f"{names[0]} 외 {len(names) - 1}곳"


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def list_open():
    """접수중 공고 목록. probe 용으로 밖에서도 씁니다."""
    j = _get(LIST_API)
    rows = ((j.get("resultData") or {}).get("recruitmentList")) or []
    if not rows:
        print(f"  ! 다우기술: 공고 목록이 비어 있습니다. {LIST_API} 를 확인하세요.")
        return []
    return [x for x in rows if str(x.get("status") or "").strip() == "접수중"]


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]

    rows = list_open()

    jobs = []
    for x in rows:
        re_no = str(x.get("reNo") or "").strip()
        seq = str(x.get("annSeqNo") or "1").strip()
        if not re_no:
            continue

        raw = ""
        try:
            q = urllib.parse.urlencode({"reNo": re_no, "annSeqNo": seq})
            d = _get(f"{DETAIL_API}?{q}")
            raw = (d.get("resultData") or {}).get("annTxt") or ""
        except Exception:
            raw = ""
        time.sleep(0.2)

        text = strip_html(raw)
        # 본문이 이미지뿐인 공고는 세부 직무를 읽을 수 없습니다.
        # 억지로 분해하지 않고 원문으로 보냅니다.
        image_only = len(text) < 50 and "<img" in raw.lower()

        posted_at, closes_at = _parse_gigan(x.get("gigan"))

        jobs.append({
            "id": f"daou-{re_no}-{seq}",
            "unit": "공고",
            # comNm 이 "LS전선" 으로 잘못 오므로 등록한 이름을 씁니다.
            "company": name,
            "companySlug": slug,
            "title": (x.get("annTitle") or "").strip(),
            "location": _location(x.get("locationNms")),
            "career": CAREER.get((x.get("enterTypeNm") or "").strip(), "무관"),
            "postedAt": posted_at,
            "closesAt": closes_at,
            "dday": _dday(x.get("dday")),
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": DETAIL.format(re_no, seq),
            "description": raw if not image_only else "",
        })

    return jobs
