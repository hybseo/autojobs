# -*- coding: utf-8 -*-
"""
롯데그룹(recruit.lotte.co.kr) 채용 수집기.

목록  GET https://recruit.lotte.co.kr/apply/announcement
상세  https://recruit.lotte.co.kr/apply/announcement/detail/{공고번호}

계열사 40곳 안팎의 공고가 한곳에 모입니다. 우리에게 중요한 것은 화학·소재
계열입니다.

    롯데케미칼 · 롯데정밀화학 · 롯데이네오스화학 · 롯데엠시시
    롯데GS화학 · 롯데에너지머티리얼즈 · 롯데알미늄 · 롯데인프라셀

유통·식품·호텔 계열사도 함께 오므로 affiliates 로 거릅니다.

요청 한 번이면 끝납니다
-----------------------
서버가 HTML 을 완성해 보냅니다(17만 자). 계열사·제목·기간·D-day 가 모두
그 안에 있어 상세를 따로 읽지 않습니다. 쪽 나눔이 없고 진행 중인 공고만
나옵니다.

공고 한 건의 생김새
-------------------
    <li>
      <div class="job-card-group">
        <span class="ico-bage-anncmtype">경력</span>
        <div class="cmp-name">롯데케미칼</div>
        <div class="card-tit">
          <a class="line-clamp" href="/apply/announcement/detail/21987204">
            2026년 9월 롯데케미칼 화학군PSO 정보보호 경력사원 채용</a>
        </div>
        <p class="date">2026.09.22 ~ 2026.10.06</p>
        <p class="dday">D-4</p>

제목에 계열사 이름이 또 들어갑니다
----------------------------------
"2026년 9월 롯데케미칼 ... 채용" 처럼 제목 안에 회사명이 들어 있고,
cmp-name 칸에도 따로 옵니다. 회사명은 cmp-name 을 쓰고 제목은 그대로
둡니다. 제목에서 떼어내면 "2026년 9월 ... 채용" 만 남아 어느 회사인지
알 수 없게 됩니다.
"""
import html
import re
import time
import urllib.error
import urllib.request

BASE = "https://recruit.lotte.co.kr"
LIST = BASE + "/apply/announcement"
VIEW = BASE + "/apply/announcement/detail/{}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# 상세 링크를 기준점으로 삼습니다.
#
# 2026-10-02 에 계열사 이름 → 링크 순서를 가정한 정규식을 썼다가 0건이
# 났습니다(받은 HTML 17만 자). 화면에서 보이는 순서와 HTML 안의 순서가
# 달랐습니다. 그래서 링크를 먼저 찾고, 그 앞뒤 일정 범위에서 계열사·제목·
# 기간을 꺼내는 방식으로 바꿨습니다. 순서가 바뀌어도 걸립니다.
LINK = re.compile(r'href="[^"]*/apply/announcement/detail/(\d+)"', re.I)
KIND = re.compile(r'class="[^"]*\bico-bage-anncmtype\b[^"]*"[^>]*>(.*?)</span>', re.S | re.I)
DATE_P = re.compile(r'class="[^"]*\bdate\b[^"]*"[^>]*>(.*?)</p>', re.S | re.I)
DATE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")


def _get(url):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9",
    })
    last = None
    for i in range(2):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError:
            raise
        except Exception as e:
            last = e
            if i < 1:
                time.sleep(3)
    raise last


def _text(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def _field(chunk, cls):
    """class 이름 하나로 그 안의 글자를 꺼냅니다. 태그 종류는 가리지 않습니다."""
    m = re.search(r'class="[^"]*\b' + re.escape(cls) + r'\b[^"]*"[^>]*>(.*?)<', chunk, re.S | re.I)
    return _text(m.group(1)) if m else ""


def _dates(v):
    """'2026.09.22 ~ 2026.10.06' → 두 날짜."""
    got = DATE.findall(str(v or ""))
    out = [f"{y}-{int(m):02d}-{int(d):02d}" for y, m, d in got[:2]]
    while len(out) < 2:
        out.append("")
    return out[0], out[1]


def _career(kind, title):
    t = f"{kind} {title}"
    has_new = "신입" in t or "인턴" in t
    has_exp = "경력" in t
    if has_new and has_exp:
        return "신입/경력"
    if has_exp:
        return "경력"
    if has_new:
        return "신입"
    return "무관"


def _norm(s):
    return re.sub(r"[\s()（）㈜.,·-]|주식회사", "", str(s or "")).lower()


def list_open(code=""):
    """공고 목록. probe 용으로 밖에서도 씁니다."""
    page = _get(LIST)

    # 공고 하나의 범위를 링크와 링크 사이로 끊습니다.
    #
    # 앞뒤로 넉넉히 1500자씩 보던 때는 옆 공고의 회사명과 기간을 가져왔습니다
    # (2026-10-02, 네 건이 모두 "롯데케미칼" 로 찍혔습니다). 링크 위치를 모두
    # 모은 뒤, 앞 링크 다음부터 다음 링크 전까지만 한 공고로 봅니다.
    marks = [(m.start(), m.end(), m.group(1)) for m in LINK.finditer(page)]

    rows, seen = [], set()
    for idx, (st, en, no) in enumerate(marks):
        if no in seen:
            continue

        prev_end = marks[idx - 1][1] if idx > 0 else 0
        next_start = marks[idx + 1][0] if idx + 1 < len(marks) else len(page)
        # 회사명·배지는 링크 앞에, 제목·기간은 링크 뒤에 옵니다.
        lo = max(prev_end, st - 1200)
        hi = min(next_start, en + 1200)
        chunk = page[lo:hi]

        company = _field(chunk, "cmp-name")
        # 제목은 링크 바로 뒤 <a> 안에 있습니다.
        tm = re.search(r">\s*([^<>]{4,120}?)\s*</a>", page[en:min(next_start, en + 600)], re.S)
        title = _text(tm.group(1)) if tm else ""
        if not title:
            title = _field(chunk, "card-tit")
        if not company or not title:
            continue

        seen.add(no)
        # 배지는 링크 앞, 기간은 링크 뒤에 옵니다. 각자 제 쪽에서만 찾습니다.
        head = page[lo:st]
        tail = page[en:hi]
        kind = _field(head, "ico-bage-anncmtype")
        start, end = _dates(_field(tail, "date") or tail)

        rows.append({
            "id": no,
            "company": company,
            "title": title,
            "kind": kind,
            "start": start,
            "end": end,
        })

    if not rows:
        print(f"  ! 롯데그룹: 공고를 찾지 못했습니다. 받은 HTML {len(page)}자. "
              f"화면 구조가 바뀌었을 수 있습니다. {LIST}")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company.get("code"))

    # 유통·식품·호텔 계열사가 함께 오므로 적어 둔 곳만 담습니다.
    want = [_norm(a) for a in (company.get("affiliates") or []) if str(a).strip()]
    if want:
        before = len(rows)
        rows = [x for x in rows if any(w in _norm(x["company"]) for w in want)]
        if before != len(rows):
            print(f"      · {name}: 계열사 거르기 {before}건 → {len(rows)}건")

    jobs = []
    for x in rows:
        jobs.append({
            "id": f"lotte-{x['id']}",
            "unit": "공고",
            "company": x["company"] or name,
            "companySlug": slug,
            "title": x["title"],
            # 목록에 근무지가 없습니다. 지어내지 않습니다.
            "location": "",
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
