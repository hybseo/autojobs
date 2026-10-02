# -*- coding: utf-8 -*-
"""
대주전자재료(daejoo.co.kr) 채용 수집기.

목록  GET https://www.daejoo.co.kr/kr/career/recruit_list.php
상세  GET https://www.daejoo.co.kr/kr/career/recruit_view.php?pid={번호}

이차전지 실리콘 음극재·전자재료(MLCC 페이스트)를 만드는 회사입니다.
자체 게시판을 씁니다.

요청 한 번이면 끝납니다
-----------------------
서버가 HTML 을 완성해 보냅니다. 제목·기간·상태가 표 안에 있어 상세를
따로 읽지 않습니다. 2026-10-02 확인 6건 중 "채용중" 1건이었습니다.

목록 구조
---------
    <tbody>
      <tr>
        <td class="num">5</td>
        <td class="title"><a href="recruit_view.php?pid=10821">사업부별 수시채용 모집</a></td>
        <td class="date">2021.04.05 ~ 2021.08.31</td>   ← 비어 있기도 합니다
        <td class="hits">채용중</td>                      ← 또는 "채용마감"
      </tr>

상태 칸을 보고 거릅니다
-----------------------
마지막 칸(hits)에 "채용중" / "채용마감" 이 들어옵니다. 칸 이름이 hits
(조회수)인데 상태가 들어오는 것은 이 사이트가 게시판 틀을 그대로 쓰면서
칸만 바꿔 썼기 때문입니다. 이름이 아니라 값을 봅니다.

날짜가 없을 수 있습니다
-----------------------
"채용시까지" 로 적히거나 아예 비어 있는 공고가 있습니다. 날짜가 없으면
비워 두고 상시채용으로 표시합니다. 지어내지 않습니다.
"""
import html
import re
import time
import urllib.error
import urllib.request

BASE = "https://www.daejoo.co.kr"
LIST = BASE + "/kr/career/recruit_list.php"
VIEW = BASE + "/kr/career/recruit_view.php?pid={}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
PID = re.compile(r"pid=(\d+)", re.I)
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


def _dates(v):
    """'2021.04.05 ~ 2021.08.31' → 두 날짜. 없으면 둘 다 빕니다."""
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
    """'채용중' 인 공고만 돌려줍니다. probe 용으로 밖에서도 씁니다."""
    page = _get(LIST)

    rows, closed, seen = [], 0, set()
    for chunk in ROW.findall(page):
        cells = [_text(c) for c in TD.findall(chunk)]
        if len(cells) < 3:
            continue

        m = PID.search(chunk)
        if not m:
            continue
        pid = m.group(1)
        if pid in seen:
            continue

        # 제목은 링크가 들어 있는 칸입니다.
        a = re.search(r"<a[^>]*>(.*?)</a>", chunk, re.S | re.I)
        title = _text(a.group(1)) if a else ""
        if not title:
            continue

        # 상태는 마지막 칸에 들어옵니다("채용중" / "채용마감").
        state = cells[-1]
        if "마감" in state:
            closed += 1
            continue

        start, end = _dates(" ".join(cells))
        seen.add(pid)
        rows.append({"id": pid, "title": title, "start": start, "end": end})

    if not rows:
        print(f"  ! 대주전자재료: 채용중 공고가 없습니다. (마감 {closed}건)")
    elif closed:
        print(f"  · 대주전자재료: 채용중 {len(rows)}건 (마감 {closed}건 제외)")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company.get("code"))

    jobs = []
    for x in rows:
        jobs.append({
            "id": f"daejoo-{x['id']}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            "title": x["title"],
            # 목록에 근무지가 없습니다. 지어내지 않습니다.
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
