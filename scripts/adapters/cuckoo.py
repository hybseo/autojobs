# -*- coding: utf-8 -*-
"""
쿠쿠(recruit.cuckoo.co.kr) 채용 수집기.

목록  GET https://recruit.cuckoo.co.kr/recruit/BASE/RecruitPost/list.do?hmCode=HM010&page=1
상세  GET https://recruit.cuckoo.co.kr/recruit/BASE/RecruitPost/view.do?hmCode=HM010&seq={번호}

밥솥·정수기로 알려진 쿠쿠입니다. 쿠쿠전자(제조)와 쿠쿠홈시스(렌털)가
한 채용 사이트를 씁니다. 계열사 구분 칸이 없고 제목에만 섞여 나옵니다.

    2026년 3분기 쿠쿠전자 생산직 사원 채용

요청 한 번이면 끝납니다
-----------------------
서버가 HTML 을 완성해서 보냅니다. 제목·경력구분·접수기간이 모두 그 안에
있어 상세를 따로 읽지 않습니다.

목록 구조 (2026-09-22 확인)
---------------------------
    <div class="info_box">
      <a href="...view.do?hmCode=HM010&seq=1234">
        <div class="info_list">
          <span class="list">경력</span>
          <span class="title"><span class="list_title">2026년 3분기 경력사원 수시 채용</span></span>
          <span class="list_date">2026.08.26 00:00(수) ~ 2026.09.10 00:00(목)</span>
        </div>
      </a>

접수 상태 칸이 없습니다
-----------------------
마감된 공고도 목록에 그대로 남고, "접수중" 같은 표시가 없습니다.
그래서 접수기간의 끝 날짜로 거릅니다. 오늘이 마감일이면 아직 접수중으로
봅니다.

2026-09-22 기준 열 건이 모두 마감(가장 늦은 마감이 9월 10일)이라 0건이
나옵니다. 사이트에 공고가 없는 것이 아니라 전부 지난 것입니다.

쪽 넘김
-------
한 쪽에 열 건입니다. page 번호로 넘깁니다. 마감된 공고는 담지 않으므로
보통 첫 쪽이면 충분하지만, 접수중 공고가 첫 쪽을 가득 채우면 다음 쪽도
봅니다(최대 MAX_PAGE 쪽).
"""
import html
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://recruit.cuckoo.co.kr"
LIST = BASE + "/recruit/BASE/RecruitPost/list.do?hmCode={}&page={}"
VIEW = BASE + "/recruit/BASE/RecruitPost/view.do?hmCode={}&seq={}"

# 화면 메뉴 번호입니다. 채용공고 목록이 HM010 입니다.
DEFAULT_MENU = "HM010"
MAX_PAGE = 5

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

CARD = re.compile(r'<div[^>]*class="[^"]*\binfo_list\b[^"]*"[^>]*>(.*?)</div>',
                  re.S | re.I)
# 카드를 감싼 <a> 에서 공고 번호를 꺼냅니다.
BLOCK = re.compile(r'<a[^>]+href="([^"]*view\.do[^"]*)"[^>]*>(.*?)</a>', re.S | re.I)
SEQ = re.compile(r"seq=(\d+)")
SPAN = re.compile(r'<span[^>]*class="[^"]*\b{}\b[^"]*"[^>]*>(.*?)</span>', re.S | re.I)
DATE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")


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


def _text(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _span(chunk, cls):
    m = re.search(r'<span[^>]*class="[^"]*\b' + re.escape(cls) + r'\b[^"]*"[^>]*>(.*?)</span>',
                  chunk, re.S | re.I)
    return _text(m.group(1)) if m else ""


def _dates(v):
    """'2026.08.26 00:00(수) ~ 2026.09.10 00:00(목)' → 두 날짜."""
    got = DATE.findall(str(v or ""))
    out = [f"{y}-{int(m):02d}-{int(d):02d}" for y, m, d in got[:2]]
    while len(out) < 2:
        out.append("")
    return out[0], out[1]


def _career(v, title):
    t = f"{v} {title}"
    has_new = "신입" in t
    has_exp = "경력" in t
    if has_new and has_exp:
        return "신입/경력"
    if has_exp:
        return "경력"
    if has_new:
        return "신입"
    return "무관"


def _today():
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")


def list_open(code=""):
    """접수중인 공고만 돌려줍니다. probe 용으로 밖에서도 씁니다."""
    menu = (str(code or "").strip() or DEFAULT_MENU)
    today = _today()

    rows, closed, seen_pages = [], 0, 0
    for page in range(1, MAX_PAGE + 1):
        url = LIST.format(menu, page)
        html_text = _get(url)
        seen_pages += 1

        cards = 0
        got_this_page = 0
        for href, block in BLOCK.findall(html_text):
            m = CARD.search(block)
            if not m:
                continue
            chunk = m.group(1)
            title = _span(chunk, "list_title")
            if not title:
                continue
            cards += 1

            start, end = _dates(_span(chunk, "list_date"))
            # 접수 상태 칸이 없어 마감일로 거릅니다. 마감일이 없으면 담습니다.
            if end and end < today:
                closed += 1
                continue

            sn = (SEQ.search(href) or [None, ""])[1]
            rows.append({
                "id": sn,
                "title": title,
                "career": _span(chunk, "list"),
                "start": start,
                "end": end,
                "url": VIEW.format(menu, sn) if sn else LIST.format(menu, 1),
            })
            got_this_page += 1

        if cards == 0:
            break
        # 이 쪽에서 접수중을 하나도 못 찾았으면 뒤쪽은 더 오래된 공고입니다.
        if got_this_page == 0:
            break
        time.sleep(0.3)

    if not rows:
        print(f"  ! 쿠쿠: 접수중 공고가 없습니다. "
              f"({seen_pages}쪽 확인, 마감으로 걸러진 것 {closed}건)")
    elif closed:
        print(f"  · 쿠쿠: 접수중 {len(rows)}건 (마감 {closed}건 제외)")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company.get("code"))

    jobs = []
    for x in rows:
        # 계열사는 제목에만 섞여 나옵니다. 있으면 그 이름을 씁니다.
        co = name
        for k in ("쿠쿠전자", "쿠쿠홈시스", "쿠쿠홀딩스"):
            if k in x["title"]:
                co = k
                break

        jobs.append({
            "id": f"cuckoo-{x['id'] or re.sub(r'[^0-9]', '', x['end'] + x['start'])[:12]}",
            "unit": "공고",
            "company": co,
            "companySlug": slug,
            "title": x["title"],
            # 근무지를 목록에 주지 않습니다. 지어내지 않습니다.
            "location": "",
            "career": _career(x["career"], x["title"]),
            "postedAt": x["start"],
            "closesAt": x["end"],
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": x["url"],
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })
    return jobs
