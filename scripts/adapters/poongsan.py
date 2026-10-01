# -*- coding: utf-8 -*-
"""
풍산(join.poongsan.co.kr) 채용 수집기.

목록  GET https://join.poongsan.co.kr/jobs/joblist.aspx
상세  GET https://join.poongsan.co.kr/jobs/view.aspx?jidx={번호}&pidx={번호}

방산(탄약)·신동(구리 가공)을 하는 회사입니다. 자체 채용 시스템을 씁니다.
풍산·풍산홀딩스·풍산FNS·풍산특수금속 등 계열사 공고가 함께 옵니다.

요청 한 번이면 끝납니다
-----------------------
서버가 HTML 을 완성해서 보냅니다. 제목·부문·기간·마감 여부가 모두 그
안에 있어 상세를 따로 읽지 않습니다. 2026-10-01 확인 6건이었습니다.

목록 구조
---------
    <a href="/jobs/view.aspx?jidx=123&pidx=45">
      <div class="job_item">
        <div class="career_name">신입</div>
        <div class="department_name">풍산(신입)</div>
        <div class="subject">2026 풍산그룹 대졸 신입사원 모집</div>
        <span class="icon_dday1">마감</span>        ← 또는 icon_dday3 D-91
        <div class="schedule">2026.09.14(월) 10:00 ~ 마감</div>
      </div>
    </a>

마감 판정
---------
남은 날 표시가 "마감" 이면 지난 공고입니다. 담지 않습니다.
"D-91" 처럼 숫자가 남아 있으면 접수중입니다.

기간은 "2026.09.14(월) 10:00 ~ 2026.09.30(수) 17:00" 처럼 오는데,
끝이 "마감" 으로만 적힌 것도 있어 날짜가 하나뿐이면 마감일을 비웁니다.

계열사
------
department_name 이 "풍산(신입)" "풍산홀딩스" 처럼 옵니다. 괄호 안은
전형 구분이라 떼고 회사명만 씁니다.
"""
import html
import re
import time
import urllib.error
import urllib.request

BASE = "https://join.poongsan.co.kr"
LIST = BASE + "/jobs/joblist.aspx"
VIEW = BASE + "/jobs/view.aspx?jidx={}&pidx={}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

ITEM = re.compile(
    r'<a[^>]+href="([^"]*view\.aspx[^"]*)"[^>]*>(.*?)</a>', re.S | re.I)
DIV = re.compile(r'<div[^>]*class="[^"]*\b{}\b[^"]*"[^>]*>(.*?)</div>', re.S | re.I)
DDAY = re.compile(r'<span[^>]*class="[^"]*\bicon_dday\d*\b[^"]*"[^>]*>(.*?)</span>', re.S | re.I)
IDX = re.compile(r"jidx=(\d+).*?pidx=(\d+)", re.I)
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
            with urllib.request.urlopen(req, timeout=30) as r:
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
    m = re.search(r'<div[^>]*class="[^"]*\b' + re.escape(cls) + r'\b[^"]*"[^>]*>(.*?)</div>',
                  chunk, re.S | re.I)
    return _text(m.group(1)) if m else ""


def _dates(v):
    """'2026.09.14(월) 10:00 ~ 2026.09.30(수) 17:00' → 두 날짜."""
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


def _company(dept, fallback):
    """'풍산(신입)' → '풍산'. 괄호 안은 전형 구분이라 뗍니다."""
    s = re.sub(r"[（(][^)）]*[)）]", "", _text(dept)).strip()
    return s or fallback


def list_open(code=""):
    """접수중인 공고만 돌려줍니다. probe 용으로 밖에서도 씁니다."""
    page = _get(LIST)

    rows, closed = [], 0
    for href, block in ITEM.findall(page):
        title = _field(block, "subject")
        if not title:
            continue

        d = DDAY.search(block)
        dday = _text(d.group(1)) if d else ""
        # "마감" 이면 지난 공고입니다.
        if "마감" in dday:
            closed += 1
            continue

        m = IDX.search(href)
        jidx, pidx = (m.group(1), m.group(2)) if m else ("", "")
        start, end = _dates(_field(block, "schedule"))

        rows.append({
            "jidx": jidx,
            "pidx": pidx,
            "title": title,
            "dept": _field(block, "department_name"),
            "career": _field(block, "career_name"),
            "start": start,
            "end": end,
        })

    if not rows:
        print(f"  ! 풍산: 접수중 공고가 없습니다. (마감으로 걸러진 것 {closed}건)")
    elif closed:
        print(f"  · 풍산: 접수중 {len(rows)}건 (마감 {closed}건 제외)")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company.get("code"))

    jobs = []
    for x in rows:
        no = x["jidx"] or re.sub(r"[^0-9]", "", x["start"] + x["title"])[:12]
        jobs.append({
            "id": f"poongsan-{no}",
            "unit": "공고",
            "company": _company(x["dept"], name),
            "companySlug": slug,
            "title": x["title"],
            # 목록에 근무지가 없습니다. 지어내지 않습니다.
            "location": "",
            "career": _career(x["career"], x["title"]),
            "postedAt": x["start"],
            "closesAt": x["end"],
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": (VIEW.format(x["jidx"], x["pidx"])
                          if x["jidx"] and x["pidx"] else LIST),
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })
    return jobs
