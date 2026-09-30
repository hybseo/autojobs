# -*- coding: utf-8 -*-
"""
코아시아그룹(coasiacareers.com) 채용 수집기.

목록  POST https://www.coasiacareers.com/recruit_list_ajax.php   본문 pg={쪽}
상세  https://www.coasiacareers.com/recruit_view.php?idx={번호}

반도체 설계(코아시아세미)·카메라모듈 등을 하는 그룹입니다. 계열사 공고가
한곳에 모여 옵니다. 2026-09-30 확인 17건이었습니다.

쪽 번호는 pg 입니다
-------------------
화면 스크립트에는 page 로 적혀 있는데, 실제 서버는 pg 만 봅니다.
page 로 보내면 몇 쪽을 요청하든 첫 여덟 건만 돌려줍니다(8건에서 멈춤).
pg 로 보내야 2쪽·3쪽이 옵니다.

    pg=1  8건
    pg=2  8건
    pg=3  1건
    pg=4  0건   → 여기서 멈춥니다

응답은 목록 조각(HTML)입니다. 빈 쪽은 300자 미만으로 옵니다.

공고 한 건의 생김새
-------------------
    <li><a href="/recruit_view.php?idx=33">
      <div class="company">CoAsia SEMI</div>
      <div class="tit">Design Efficiency팀 IT Infra EDA Support Engineer 모집</div>
      <div class="work">IT/정보전략</div>
      <div class="type">8년 이상</div>
      <div class="period">2026.09.16 ~ 2026.10.15</div>
      <div class="location">동탄</div>
      <div class="dday">D-15</div>
    </a></li>

계열사 거르기
-------------
CoAsia SEMI·NEXELL·CM 등으로 나뉩니다. 전부 반도체·전자 계열이라 기본은
모두 담습니다. companies.json 의 affiliates 를 적으면 그곳만 담습니다.
"""
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://www.coasiacareers.com"
LIST_API = BASE + "/recruit_list_ajax.php"
LIST_PAGE = BASE + "/recruit.php"
VIEW = BASE + "/recruit_view.php?idx={}"

MAX_PAGE = 10

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

ITEM = re.compile(r'<a[^>]+href="[^"]*idx=(\d+)[^"]*"[^>]*>(.*?)</a>', re.S | re.I)
DIV = re.compile(r'<div[^>]*class="\\?"?([a-z_]+)\\?"?[^>]*>(.*?)</div>', re.S | re.I)
DATE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")


def _post(page):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다."""
    data = urllib.parse.urlencode({"pg": str(page)}).encode()
    req = urllib.request.Request(
        LIST_API, method="POST", data=data,
        headers={
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "text/html, */*; q=0.01",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": LIST_PAGE,
        })
    last = None
    for i in range(2):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError:
            raise
        except Exception as e:
            last = e
            if i < 1:
                time.sleep(3)
    raise last


def _unwrap(body):
    """응답에서 목록 HTML 만 꺼냅니다.

    이 서버는 HTML 을 JSON 에 담아 보냅니다.

        {"success":true,"listHtml":"<li><a href=\\"/recruit_view.php?idx=33\\">..."}

    그래서 따옴표가 \\" 로 감싸여 있고, 그대로 정규식을 걸면 href=" 가
    하나도 맞지 않습니다. 2026-09-30 첫 수집에서 0건이 난 까닭입니다.
    JSON 으로 풀어 listHtml 을 꺼내고, 실패하면 역슬래시만 걷어냅니다.
    """
    body = body or ""
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            for key in ("listHtml", "html", "list", "data"):
                v = data.get(key)
                if isinstance(v, str) and v.strip():
                    return v
    except Exception:
        pass
    # JSON 이 아니면 감싼 따옴표만 풀어 줍니다.
    return body.replace('\\"', '"').replace("\\/", "/")


def _text(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s).replace("\\/", "/").replace("\\\"", '"')
    s = s.replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def _field(chunk, cls):
    """응답이 따옴표를 역슬래시로 감싸 보내기도 해서 느슨하게 찾습니다."""
    m = re.search(r'class=\\?"?[^"\\>]*\b' + re.escape(cls) + r'\b[^"\\>]*\\?"?[^>]*>(.*?)</div>',
                  chunk, re.S | re.I)
    return _text(m.group(1)) if m else ""


def _dates(v):
    """'2026.09.16 ~ 2026.10.15' → 두 날짜. 하나뿐이면 마감일은 빕니다."""
    got = DATE.findall(str(v or ""))
    out = [f"{y}-{int(m):02d}-{int(d):02d}" for y, m, d in got[:2]]
    while len(out) < 2:
        out.append("")
    return out[0], out[1]


def _career(kind, title):
    """'8년 이상' 같은 값이 옵니다. 숫자가 있으면 경력입니다."""
    t = f"{kind} {title}"
    has_new = "신입" in t
    has_exp = "경력" in t or re.search(r"\d+\s*년", t)
    if has_new and has_exp:
        return "신입/경력"
    if has_exp:
        return "경력"
    if has_new:
        return "신입"
    return "무관"


def _norm(s):
    return re.sub(r"[\s()（）㈜.,·-]", "", str(s or "")).lower()


def list_open(code=""):
    """공고 목록. probe 용으로 밖에서도 씁니다."""
    rows, seen = [], set()
    for page in range(1, MAX_PAGE + 1):
        chunk_html = _unwrap(_post(page))
        # 빈 쪽은 목록이 비어 옵니다.
        if len(chunk_html) < 60:
            break

        got = 0
        for no, block in ITEM.findall(chunk_html):
            if no in seen:
                continue
            title = _field(block, "tit")
            if not title:
                continue
            seen.add(no)
            got += 1
            start, end = _dates(_field(block, "period"))
            rows.append({
                "id": no,
                "title": title,
                "company": _field(block, "company"),
                "work": _field(block, "work"),
                "kind": _field(block, "type"),
                "location": _field(block, "location"),
                "start": start,
                "end": end,
            })
        if got == 0:
            break
        time.sleep(0.2)

    if not rows:
        print(f"  ! 코아시아: 공고를 찾지 못했습니다. 쪽 번호는 page 가 아니라 pg 입니다. "
              f"{LIST_API}")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company.get("code"))

    want = [_norm(a) for a in (company.get("affiliates") or []) if str(a).strip()]
    if want:
        before = len(rows)
        rows = [x for x in rows if any(w in _norm(x["company"]) for w in want)]
        if before != len(rows):
            print(f"      · {name}: 계열사 거르기 {before}건 → {len(rows)}건")

    jobs = []
    for x in rows:
        title = x["title"]
        # 직무가 제목에 없으면 뒤에 붙입니다. 어떤 자리인지 보이게 합니다.
        if x["work"] and x["work"] not in title:
            title = f"{title} · {x['work']}"

        jobs.append({
            "id": f"coasia-{x['id']}",
            "unit": "공고",
            "company": x["company"] or name,
            "companySlug": slug,
            "title": title,
            "location": x["location"],
            "career": _career(x["kind"], x["title"]),
            "postedAt": x["start"],
            "closesAt": x["end"],
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": VIEW.format(x["id"]),
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })
    return jobs
