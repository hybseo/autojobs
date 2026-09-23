# -*- coding: utf-8 -*-
"""
Select IN(select-in.co.kr) 채용 수집기.

목록  GET https://{code}.select-in.co.kr/recruit/apply/recruitMain

Select IN 은 국내 채용 관리 서비스입니다. 회사마다 앞자리(subdomain)가
다릅니다. 해성그룹이 haesunggroup 입니다.

    companies.json
      "ats": "select_in", "code": "haesunggroup"

화면이 두 칸으로 나뉩니다
------------------------
    <section class="sec03">   진행중인 채용공고   ← 이것만 담습니다
    <section class="sec04">   발표/마감 공고

마감된 공고까지 담으면 지원할 수 없는 자리가 목록에 섞입니다.
2026-09-22 기준 해성그룹은 진행중 2건, 마감 18건이었습니다.

공고 하나의 생김새
------------------
    <li class="swiper-slide">
      <p class="basic_info">해성그룹 | 경력 | 정규직</p>
      <p class="tit f24">[해성디에스] BGA Panel(표면처리/적층/설계) 경력사원 수시 채용</p>
      <button onclick="go_post(...)">지원하기</button>
      <p class="date">2026.09.18 13:00 ~ 2026.09.27 23:59</p>
      <div class="tag_cont"><div class="tag"><span>#경력</span>...</div></div>
    </li>

회사명은 제목 앞 대괄호에 있습니다
----------------------------------
basic_info 의 첫 칸은 "해성그룹" 처럼 그룹 이름이라 계열사를 알 수 없습니다.
계열사는 제목 앞 대괄호로만 표시됩니다.

    [해성디에스] BGA Panel ...   →  해성디에스

대괄호가 없으면 등록한 이름(그룹명)을 씁니다.

계열사 거르기
-------------
그룹 채용 사이트라 사이트가 다루지 않는 분야(제지 등)도 함께 옵니다.
companies.json 의 affiliates 에 적은 계열사만 담습니다. 비워 두면 전부
담습니다. SK·대웅·HD현대와 같은 방식입니다.

상세 주소가 없습니다
--------------------
"지원하기" 가 <a href> 가 아니라 go_post() 라는 폼 전송입니다. 주소로
열 수 있는 개별 공고 페이지가 없어서 모두 목록으로 보냅니다. 없는 주소를
지어내지 않습니다.

서버가 요청 방식에 따라 다른 답을 줍니다
----------------------------------------
브라우저 자바스크립트로 같은 주소를 부르면 1킬로바이트짜리 껍데기만
돌려주고, 주소창으로 들어가면 5만 자짜리 전체 화면을 돌려줍니다.
수집기는 브라우저가 페이지를 여는 것과 같은 모양으로 요청하므로 전체를
받습니다. 혹시 껍데기를 받으면 아래에서 그 사실을 로그에 적습니다.
"""
import hashlib
import html
import http.cookiejar
import re
import time
import urllib.error
import urllib.request

# 첫 요청에서 받은 쿠키(세션)를 다음 요청에 실어 보냅니다.
# 서버가 세션을 만든 뒤에야 전체 화면을 주는 경우가 있습니다.
_OPENER = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

BASE = "https://{}.select-in.co.kr"
PATH = "/recruit/apply/recruitMain"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# 진행중 칸만 잘라냅니다. 다음 section 이 나오면 거기서 끊습니다.
LIVE_SEC = re.compile(
    r'<section[^>]*class="[^"]*\bsec03\b[^"]*"[^>]*>(.*?)(?=<section|</body>)',
    re.S | re.I)
CARD = re.compile(r'<li[^>]*class="[^"]*\bswiper-slide\b[^"]*"[^>]*>(.*?)</li>',
                  re.S | re.I)
AFFIL = re.compile(r"^\s*[\[【]\s*([^\]】]{2,20})\s*[\]】]")
DATE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")


def _get(url):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다.

    이 서버는 요청 모양을 보고 다른 답을 줍니다.
    주소창으로 들어가면 5만 자짜리 전체 화면을, 자바스크립트가 부르면
    1킬로바이트짜리 껍데기를 돌려줍니다. 2026-09-22 수집에서 껍데기를
    받아 0건이 났습니다.

    브라우저가 페이지를 열 때 함께 보내는 표시(Sec-Fetch-*)를 붙여
    같은 모양으로 요청합니다. 쿠키도 받아 두 번째 요청에 실어 보냅니다.
    """
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    })
    last = None
    for i in range(3):
        try:
            with _OPENER.open(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError:
            raise
        except Exception as e:
            last = e
            if i < 2:
                time.sleep(2 + i * 2)
    raise last


def _text(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _field(chunk, cls):
    """카드 안에서 class 가 cls 인 <p> 의 글자를 꺼냅니다.

    class 에 다른 이름이 같이 붙기도 합니다(예: "tit f24").
    """
    m = re.search(r'<p[^>]*class="[^"]*\b' + re.escape(cls) + r'\b[^"]*"[^>]*>(.*?)</p>',
                  chunk, re.S | re.I)
    return _text(m.group(1)) if m else ""


def _career(basic, title):
    """basic_info 는 '해성그룹 | 경력 | 정규직' 모양입니다."""
    t = f"{basic} {title}"
    has_new = "신입" in t
    has_exp = "경력" in t
    if has_new and has_exp:
        return "신입/경력"
    if has_exp:
        return "경력"
    if has_new:
        return "신입"
    return "무관"


def _dates(v):
    """'2026.09.18 13:00 ~ 2026.09.27 23:59' → 두 날짜. '수시' 면 빈 값."""
    got = DATE.findall(str(v or ""))
    out = [f"{y}-{int(m):02d}-{int(d):02d}" for y, m, d in got[:2]]
    while len(out) < 2:
        out.append("")
    return out[0], out[1]


def _norm(s):
    return re.sub(r"[\s()·\-]", "", str(s or "")).lower()


def list_open(code):
    """진행중 공고 목록. probe 용으로 밖에서도 씁니다."""
    sub = str(code or "").strip().strip("/")
    if not sub:
        raise RuntimeError("select_in: code 가 비어 있습니다. "
                           "주소의 앞자리(예: haesunggroup)를 적으세요.")
    url = BASE.format(sub) + PATH
    page = _get(url)

    # 껍데기를 받으면 쿠키가 생긴 뒤 한 번 더 두드립니다.
    if len(page) < 3000:
        time.sleep(1)
        page = _get(url)

    if len(page) < 3000:
        # 껍데기만 받은 경우입니다. 파싱해봐야 0건이라 원인을 남깁니다.
        print(f"  ! Select IN({sub}): 화면 내용이 없는 응답을 받았습니다 "
              f"({len(page)}자). 주소나 차단 여부를 확인하세요. {url}")
        return []

    sec = LIVE_SEC.search(page)
    if not sec:
        print(f"  ! Select IN({sub}): '진행중' 칸(sec03)을 찾지 못했습니다. "
              f"화면 구조가 바뀌었을 수 있습니다. 받은 HTML {len(page)}자")
        return []

    rows = []
    for chunk in CARD.findall(sec.group(1)):
        title = _field(chunk, "tit")
        if not title:
            continue
        basic = _field(chunk, "basic_info")
        start, end = _dates(_field(chunk, "date"))
        m = AFFIL.match(title)
        rows.append({
            "title": title,
            "company": m.group(1).strip() if m else "",
            "career": _career(basic, title),
            "start": start,
            "end": end,
            "url": url,
        })

    if not rows:
        print(f"  ! Select IN({sub}): 진행중 공고가 없습니다. "
              f"(카드 {len(CARD.findall(sec.group(1)))}개)")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company["code"])

    # affiliates 에 적은 계열사만 담습니다. 비어 있으면 전부 담습니다.
    want = [_norm(a) for a in (company.get("affiliates") or []) if str(a).strip()]
    if want:
        before = len(rows)
        rows = [x for x in rows
                if x["company"] and any(w in _norm(x["company"]) for w in want)]
        if before != len(rows):
            print(f"      · {name}: 계열사 거르기 {before}건 → {len(rows)}건")

    jobs, seen = [], {}
    for x in rows:
        # 공고 번호가 없습니다(상세가 폼 전송이라 주소에 번호가 없습니다).
        # 제목으로 번호를 만듭니다. 제목이 바뀌면 새 공고로 보입니다.
        #
        # id 는 우리 사이트 주소(/job/{id}/)가 되므로 영문·숫자만 씁니다.
        # 한글 제목이 대부분이라 md5 로 줄입니다. hash() 는 파이썬을 새로
        # 띄울 때마다 값이 달라져 같은 공고가 매번 새 공고로 보입니다.
        jid = hashlib.md5(x["title"].encode("utf-8")).hexdigest()[:10]
        seen[jid] = seen.get(jid, 0) + 1
        if seen[jid] > 1:
            jid = f"{jid}{seen[jid]}"

        jobs.append({
            "id": f"selectin-{slug}-{jid}",
            "unit": "공고",
            "company": x["company"] or name,
            "companySlug": slug,
            "title": x["title"],
            # 근무지를 목록에 주지 않습니다. 지어내지 않습니다.
            "location": "",
            "career": x["career"],
            "postedAt": x["start"],
            "closesAt": x["end"],
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            # 개별 공고 주소가 없어 목록으로 보냅니다.
            "sourceUrl": x["url"],
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })
    return jobs
