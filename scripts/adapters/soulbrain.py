# -*- coding: utf-8 -*-
"""
솔브레인(soulbrain.co.kr) 채용 수집기.

목록  GET https://www.soulbrain.co.kr/m64.php
상세  목록 화면 안에서 열려 개별 주소가 없습니다. 목록으로 보냅니다.

반도체·디스플레이 식각액과 이차전지 전해액을 만드는 회사입니다.
자체 게시판을 씁니다.

요청 한 번이면 끝납니다
-----------------------
서버가 HTML 을 완성해 보냅니다. 제목과 작성일이 표 안에 있습니다.
2026-10-02 확인 10건이었습니다.

목록 구조
---------
    <table class="board_list"><tbody>
      <tr>
        <td class="num">10</td>
        <td class="subject"><a href="javascript:;" onclick="goView('10')">
            2026년 하반기 솔브레인 신입/경력 수시채용</a></td>
        <td class="date">2026-09-15</td>
        <td class="hit">1204</td>
      </tr>

마감 여부를 알 수 없습니다
--------------------------
접수 기간도, "진행중/마감" 표시도 없습니다. 작성일만 있습니다.
그래서 작성일이 1년이 지난 공고는 담지 않습니다. 이 게시판은 지난
공고를 지우지 않고 쌓아 두기 때문에(2023년 글까지 남아 있습니다),
전부 담으면 3년 전 공고가 사이트에 올라옵니다.

1년은 넉넉한 기준입니다. 수시채용 공고는 1년 넘게 열어 두기도 하지만,
그보다 오래된 것은 사실상 끝난 공고로 봅니다.

상세 주소가 없습니다
--------------------
링크가 goView('10') 형태의 자바스크립트이고 주소가 바뀌지 않습니다.
카드를 누르면 목록 화면으로 보냅니다.
"""
import html
import re
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

BASE = "https://www.soulbrain.co.kr"
LIST = BASE + "/m64.php"

# 작성일이 이보다 오래된 공고는 담지 않습니다.
MAX_AGE_DAYS = 365

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
CELL = re.compile(r'<td[^>]*class="[^"]*\b{}\b[^"]*"[^>]*>(.*?)</td>', re.S | re.I)
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
            with urllib.request.urlopen(req, timeout=50) as r:
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


def _cell(chunk, cls):
    m = re.search(r'<td[^>]*class="[^"]*\b' + re.escape(cls) + r'\b[^"]*"[^>]*>(.*?)</td>',
                  chunk, re.S | re.I)
    return _text(m.group(1)) if m else ""


def _date(v):
    m = YMD.search(str(v or ""))
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""


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
    """최근 1년 안에 올라온 공고만 돌려줍니다."""
    page = _get(LIST)
    cut = (date.today() - timedelta(days=MAX_AGE_DAYS)).isoformat()

    rows, old, seen = [], 0, set()
    for chunk in ROW.findall(page):
        title = _cell(chunk, "subject")
        if not title:
            # 칸 이름이 다를 수 있어 링크 글자로 한 번 더 봅니다.
            a = re.search(r"<a[^>]*>(.*?)</a>", chunk, re.S | re.I)
            title = _text(a.group(1)) if a else ""
        if not title:
            continue

        m = IDX.search(chunk)
        no = m.group(1) if m else _cell(chunk, "num")
        if not no or no in seen:
            continue

        posted = _date(_cell(chunk, "date")) or _date(" ".join(_text(c) for c in TD.findall(chunk)))
        if posted and posted < cut:
            old += 1
            continue

        seen.add(no)
        rows.append({"id": no, "title": title, "posted": posted})

    if not rows:
        print(f"  ! 솔브레인: 최근 1년 안에 올라온 공고가 없습니다. (오래된 글 {old}건)")
    elif old:
        print(f"  · 솔브레인: {len(rows)}건 (1년 넘은 글 {old}건 제외)")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company.get("code"))

    jobs = []
    for x in rows:
        jobs.append({
            "id": f"soulbrain-{x['id']}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            "title": x["title"],
            # 목록에 근무지가 없습니다. 지어내지 않습니다.
            "location": "",
            "career": _career(x["title"]),
            "postedAt": x["posted"],
            # 접수 기간이 없습니다. 상시채용으로 표시됩니다.
            "closesAt": "",
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            # 상세가 화면 안에서 열려 개별 주소가 없습니다.
            "sourceUrl": LIST,
            "description": "",
        })
    return jobs
