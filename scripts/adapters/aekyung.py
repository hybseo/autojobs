# -*- coding: utf-8 -*-
"""
애경케미칼(aekyungchemical.applyin.co.kr) 채용 수집기.

목록  GET https://aekyungchemical.applyin.co.kr/jobs/
상세  https://aekyungchemical.applyin.co.kr/jobs/{번호}

가소제·바이오디젤·배터리 음극재를 만드는 회사입니다.

applyin 은 사람인이 파는 채용 홈페이지 솔루션입니다
-----------------------------------------------------
그리팅(두들린)·리크루터(마이다스)처럼 기업이 자사 채용 사이트를 만들 때
쓰는 제품이고, 공고의 주인은 회사입니다. 사람인 구인 서비스 본체
(saramin.co.kr)와는 다릅니다. 그쪽은 채용공고가 상품인 서비스라 담지
않습니다(KG스틸이 그 경우입니다).

요청 한 번이면 끝납니다
-----------------------
서버가 HTML 을 완성해 보냅니다(11만 자). 제목·기간·상태가 그 안에
있습니다.

공고 한 건의 생김새
-------------------
    <li>
      <div class="recruit_sort">일반</div>
      <a class="inner" href="/jobs/23238">[신입] 청양공장 '자재물류' 담당 모집</a>
      <div class="day_txt">2026.09.03 00:00 ~ 2026.09.13 </div>
      <span class="badge_announ">발표중</span>
    </li>

상태 배지로 거릅니다
--------------------
    badge_ing     접수중      → 담습니다
    badge_test    전형중      → 접수가 끝났습니다
    badge_announ  발표중      → 접수가 끝났습니다
    badge_end     종료        → 끝났습니다

2026-10-02 확인 11건이 모두 전형중·발표중·종료였습니다. 접수중이 생기면
자동으로 들어옵니다.

배지 이름이 아니라 글자를 봅니다. 회사가 배지를 새로 만들어도 "접수"
라는 말이 들어가면 담기도록 했습니다.
"""
import html
import re
import time
import urllib.error
import urllib.request

BASE = "https://aekyungchemical.applyin.co.kr"
LIST = BASE + "/jobs/"
VIEW = BASE + "/jobs/{}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

ITEM = re.compile(r"<li[^>]*>(.*?)</li>", re.S | re.I)
LINK = re.compile(r'href="[^"]*/jobs/(\d+)"[^>]*>(.*?)</a>', re.S | re.I)
CLS = re.compile(r'class="[^"]*\b{}\b[^"]*"[^>]*>(.*?)<', re.S | re.I)
BADGE = re.compile(r'class="[^"]*\b(badge_\w+|recruit_badge)\b[^"]*"[^>]*>(.*?)<', re.S | re.I)
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
    m = re.search(r'class="[^"]*\b' + re.escape(cls) + r'\b[^"]*"[^>]*>(.*?)</', chunk, re.S | re.I)
    return _text(m.group(1)) if m else ""


def _dates(v):
    got = DATE.findall(str(v or ""))
    out = [f"{y}-{int(m):02d}-{int(d):02d}" for y, m, d in got[:2]]
    while len(out) < 2:
        out.append("")
    return out[0], out[1]


def _career(title):
    t = title or ""
    has_new, has_exp = "신입" in t, "경력" in t
    if has_new and has_exp:
        return "신입/경력"
    if has_exp:
        return "경력"
    if has_new:
        return "신입"
    return "무관"


def list_open(code=""):
    """접수중인 공고만 돌려줍니다. probe 용으로 밖에서도 씁니다."""
    page = _get(LIST)

    rows, closed, seen = [], 0, set()
    for chunk in ITEM.findall(page):
        m = LINK.search(chunk)
        if not m:
            continue
        no, title_raw = m.group(1), m.group(2)
        title = _text(title_raw)
        if not no or not title or no in seen:
            continue

        # 상태 배지. 이름이 아니라 글자를 봅니다.
        states = [_text(t) for _, t in BADGE.findall(chunk)]
        state = " ".join(s for s in states if s)
        if state and "접수" not in state:
            closed += 1
            continue

        seen.add(no)
        start, end = _dates(_field(chunk, "day_txt"))
        rows.append({"id": no, "title": title, "start": start, "end": end})

    if not rows:
        print(f"  ! 애경케미칼: 접수중 공고가 없습니다. "
              f"(전형중·발표중·종료 {closed}건)")
    elif closed:
        print(f"  · 애경케미칼: 접수중 {len(rows)}건 (끝난 공고 {closed}건 제외)")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company.get("code"))

    jobs = []
    for x in rows:
        jobs.append({
            "id": f"aekyung-{x['id']}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            "title": x["title"],
            # 목록에 근무지가 없습니다. 제목에 공장 이름이 들어가기도 하지만
            # 근무지 칸으로 옮기지 않습니다. 지어내지 않습니다.
            "location": "",
            "career": _career(x["title"]),
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
