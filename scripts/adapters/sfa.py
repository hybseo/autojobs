# -*- coding: utf-8 -*-
"""
에스에프에이(recruit.sfa.co.kr) 채용 수집기.

목록  GET https://recruit.sfa.co.kr/sfa/recruit
상세  GET https://recruit.sfa.co.kr/sfa/recruit?id={번호}&pg=1

디스플레이·2차전지·물류 자동화 설비. 코스피.

요청 한 번이면 끝납니다
-----------------------
자체 시스템인데 서버가 HTML 을 완성해서 보냅니다. 표 한 장에 제목·모집부문·
근무지·접수기간·진행상황이 다 들어 있어 상세를 따로 읽지 않습니다.

목록 구조 (2026-09-15 확인)
---------------------------
    <tbody>
      <tr>
        <td><a href="?id=1530&pg=1">2026년 4차 수시채용_구매 부문 (10월11일 마감)</a></td>
        <td>구매</td>                                     모집부문
        <td>동탄</td>                                     근무지
        <td>2026.09.15 09시 ~ 2026.10.11 23시</td>        접수기간
        <td>원서접수중</td>                                진행상황
        <td>...</td>                                     입사지원 버튼
      </tr>

칸이 여섯입니다. 순서로 읽습니다. 클래스 이름이 없어서 다른 방법이 없습니다.

상세 주소가 물음표로 시작합니다
------------------------------
href 가 "?id=1530&pg=1" 형태입니다. 경로가 없고 쿼리만 있습니다.
목록 주소에 그대로 붙이면 됩니다.

    https://recruit.sfa.co.kr/sfa/recruit?id=1530&pg=1

진행상황으로 거릅니다
---------------------
"원서접수중" 인 것만 담습니다. 마감된 공고도 표에 남아 있습니다.

한 공고에 여러 부문이 묶입니다
------------------------------
"2026년 4차 수시채용_11개 부문" 처럼 여러 직무를 한 공고에 담는 일이
잦습니다. 모집부문 칸에도 "솔루션개발(Digital Twin),..." 처럼 잘려서
옵니다. 그런 공고는 multiRole 을 켜서 "여러 직무 포함 가능" 으로 표시합니다.
"""
import html
import re
import time
import urllib.error
import urllib.request

BASE = "https://recruit.sfa.co.kr"
LIST_URL = BASE + "/sfa/recruit"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
LINK = re.compile(r'href="([^"]*id=(\d+)[^"]*)"', re.I)

# 여러 부문을 묶은 공고인지 판단합니다.
MULTI = re.compile(r"\d+\s*개\s*부문|,\s*\.\.\.|\.\.\.$")


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


def _dates(v):
    """'2026.09.15 09시 ~ 2026.10.11 23시' → 두 날짜."""
    got = re.findall(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", str(v or ""))
    out = [f"{y}-{int(m):02d}-{int(d):02d}" for y, m, d in got[:2]]
    while len(out) < 2:
        out.append("")
    return out[0], out[1]


def _career(title, part):
    """제목과 모집부문에서만 읽습니다. 없으면 무관. 지어내지 않습니다."""
    t = f"{title} {part}"
    has_new = "신입" in t
    has_exp = "경력" in t
    if has_new and has_exp:
        return "신입/경력"
    if has_exp:
        return "경력"
    if has_new:
        return "신입"
    return "무관"


def list_open():
    """접수중 공고만 골라 돌려줍니다. probe 용으로 밖에서도 씁니다."""
    page = _get(LIST_URL)

    rows, closed = [], 0
    for chunk in ROW.findall(page):
        cells = [_text(c) for c in CELL.findall(chunk)]
        # 칸이 여섯입니다. 적으면 머리글이거나 다른 표입니다.
        if len(cells) < 5:
            continue

        m = LINK.search(chunk)
        if not m:
            continue
        href, jid = m.group(1), m.group(2)

        title, part, loc, period, state = cells[0], cells[1], cells[2], cells[3], cells[4]
        if not title:
            continue

        # 마감된 공고도 표에 남습니다. 접수중만 담습니다.
        if state and "접수중" not in state:
            closed += 1
            continue

        start, end = _dates(period)
        rows.append({
            "id": jid,
            "title": title,
            "part": part,
            "location": loc,
            "start": start,
            "end": end,
            "url": LIST_URL + html.unescape(href) if href.startswith("?")
                   else urllib_join(href),
        })

    if not rows:
        # HTML 파싱이라 화면이 바뀌면 조용히 0건이 됩니다.
        print(f"  ! 에스에프에이: 접수중 공고를 찾지 못했습니다. ({LIST_URL})")
        print(f"    받은 HTML {len(page)}자 · "
              f"'<tr' {page.count('<tr')}회 · "
              f"'원서접수중' {page.count('원서접수중')}회 · "
              f"마감으로 걸러진 것 {closed}건")
    elif closed:
        print(f"  · 에스에프에이: 접수중 {len(rows)}건 (마감 {closed}건 제외)")
    return rows


def urllib_join(href):
    """상대 주소를 절대 주소로. 물음표로 시작하지 않는 예외 상황용입니다."""
    import urllib.parse
    return urllib.parse.urljoin(LIST_URL, html.unescape(href))


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]

    rows = list_open()

    jobs = []
    for x in rows:
        # 여러 부문을 묶은 공고는 세부 직무를 원문에서 봐야 합니다.
        multi = bool(MULTI.search(x["title"]) or MULTI.search(x["part"]))

        # 모집부문을 제목 뒤에 붙입니다. 어떤 자리인지 바로 보입니다.
        title = x["title"]
        if x["part"] and not multi and x["part"] not in title:
            title = f"{title} · {x['part']}"

        jobs.append({
            "id": f"sfa-{x['id']}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            "title": title,
            "location": x["location"],
            "career": _career(x["title"], x["part"]),
            "postedAt": x["start"],
            "closesAt": x["end"],
            "dday": None,
            "multiRole": multi,
            "sourceTitle": "",
            "sourceUrl": x["url"],
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })

    return jobs
