# -*- coding: utf-8 -*-
"""
빅텍(victek.co.kr) 채용 수집기.

목록  GET https://www.victek.co.kr/07_rec/job.html
상세  GET https://www.victek.co.kr/07_rec/job_view.html?idx={번호}

방산 전자부품(피아식별장치·전원공급장치)을 만드는 회사입니다.
자체 게시판을 씁니다.

요청 한 번이면 끝납니다
-----------------------
서버가 HTML 을 완성해 보냅니다. 번호·제목·지원구분·접수기한이 표 안에
있어 상세를 따로 읽지 않습니다.

목록 구조
---------
    <tbody>
      <tr>
        <td>37</td>
        <td><a href="javascript:goView('37')">(주)빅텍 2026년 각 부문별 신입(경력)사원 모집</a></td>
        <td>신입/경력</td>
        <td>2026-08-07</td>     ← 접수기한
        <td>1046</td>
      </tr>

상세 주소가 자바스크립트입니다
------------------------------
링크가 goView('37') 형태라 주소가 없습니다. 번호로 job_view.html 을
만들어 보냅니다. 열리지 않으면 목록으로 보내도 됩니다.

마감 판정
---------
접수기한만 있고 "진행중/마감" 표시가 없습니다. 기한이 오늘보다 이르면
담지 않습니다. 2026-10-01 확인 13건이 모두 기한이 지난 상태였습니다.
"""
import html
import re
import time
import urllib.error
import urllib.request
from datetime import date

BASE = "https://www.victek.co.kr"
LIST = BASE + "/07_rec/job.html"
VIEW = BASE + "/07_rec/job_view.html?idx={}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
IDX = re.compile(r"goView\(\s*['\"](\d+)['\"]\s*\)", re.I)
YMD = re.compile(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})")


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


def _date(v):
    m = YMD.search(str(v or ""))
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""


def _career(v, title):
    t = f"{v} {title}"
    has_new, has_exp = "신입" in t, "경력" in t
    if has_new and has_exp:
        return "신입/경력"
    if has_exp:
        return "경력"
    if has_new:
        return "신입"
    return "무관"


def list_open(code=""):
    """접수기한이 남은 공고만 돌려줍니다. probe 용으로 밖에서도 씁니다."""
    page = _get(LIST)
    today = date.today().isoformat()

    rows, closed, seen = [], 0, set()
    for chunk in ROW.findall(page):
        cells = [_text(c) for c in TD.findall(chunk)]
        if len(cells) < 4:
            continue
        # 머리글 줄은 번호 자리가 숫자가 아닙니다.
        if not cells[0].isdigit():
            continue

        m = IDX.search(chunk)
        no = m.group(1) if m else cells[0]
        if no in seen:
            continue

        title = cells[1]
        kind = cells[2]
        end = _date(cells[3])
        if not title:
            continue

        # 접수기한이 지난 공고는 담지 않습니다.
        if end and end < today:
            closed += 1
            continue

        seen.add(no)
        rows.append({"id": no, "title": title, "kind": kind, "end": end})

    if not rows:
        print(f"  ! 빅텍: 접수중 공고가 없습니다. (기한이 지난 것 {closed}건)")
    elif closed:
        print(f"  · 빅텍: 접수중 {len(rows)}건 (기한 지남 {closed}건 제외)")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company.get("code"))

    jobs = []
    for x in rows:
        jobs.append({
            "id": f"victek-{x['id']}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            "title": x["title"],
            # 목록에 근무지가 없습니다. 지어내지 않습니다.
            "location": "",
            "career": _career(x["kind"], x["title"]),
            # 목록에 게시일이 없습니다. 접수기한만 있습니다.
            "postedAt": "",
            "closesAt": x["end"],
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": VIEW.format(x["id"]),
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })
    return jobs
