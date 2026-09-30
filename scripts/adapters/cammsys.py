# -*- coding: utf-8 -*-
"""
캠시스(cammsys.net) 채용 수집기.

목록  GET https://www.cammsys.net/kor/recruit/notice
상세  GET https://www.cammsys.net/kor/recruit/notice?viewMode=view&idx={번호}

차량용 카메라모듈을 만드는 회사입니다. 자체 게시판을 씁니다.

요청 한 번이면 끝납니다
-----------------------
서버가 HTML 을 완성해 보냅니다. 제목·작성일이 표 안에 있어 상세를 따로
읽지 않습니다. 2026-09-30 확인 4건이었습니다.

목록 구조
---------
    <tbody>
      <tr>
        <td class="no">4</td>
        <td class="sbj"><a href="...idx=17">(주)캠시스 마케팅부문 구매part 채용</a></td>
        <td class="writer">관리자</td>
        <td class="date">작성일26.08.12</td>
        <td class="view">조회883</td>
      </tr>

마감일이 없습니다
-----------------
게시판이라 접수 마감일 칸이 없습니다. 상시채용으로 표시하고 카드를 누르면
원문으로 보냅니다. 없는 날짜를 지어내지 않습니다.

작성일은 "작성일26.08.12" 처럼 글자가 붙어 오고 연도가 두 자리입니다.
20xx 로 펴서 게시일로 씁니다.
"""
import html
import re
import time
import urllib.error
import urllib.request

BASE = "https://www.cammsys.net"
LIST = BASE + "/kor/recruit/notice"
VIEW = BASE + "/kor/recruit/notice?viewMode=view&idx={}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
CELL = re.compile(r'<td[^>]*class="[^"]*\b{}\b[^"]*"[^>]*>(.*?)</td>', re.S | re.I)
LINK = re.compile(r'href="([^"]*idx=(\d+)[^"]*)"', re.I)
YMD = re.compile(r"(\d{2})\.(\d{1,2})\.(\d{1,2})")


def _get(url):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9",
    })
    # 2026-09-30 수집에서 25초로는 모자라 시간 초과가 났습니다.
    # 국내 중견기업 사이트는 해외 서버에서 부를 때 느린 경우가 있습니다.
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


def _cell(chunk, cls):
    m = re.search(r'<td[^>]*class="[^"]*\b' + re.escape(cls) + r'\b[^"]*"[^>]*>(.*?)</td>',
                  chunk, re.S | re.I)
    return _text(m.group(1)) if m else ""


def _date(v):
    """'작성일26.08.12' → '2026-08-12'. 두 자리 연도를 20xx 로 폅니다."""
    m = YMD.search(str(v or ""))
    if not m:
        return ""
    return f"20{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def _career(title):
    t = title or ""
    has_new = "신입" in t
    has_exp = "경력" in t
    if has_new and has_exp:
        return "신입/경력"
    if has_exp:
        return "경력"
    if has_new:
        return "신입"
    return "무관"


def list_open(code=""):
    """공고 목록. probe 용으로 밖에서도 씁니다."""
    page = _get(LIST)

    rows, seen = [], set()
    for chunk in ROW.findall(page):
        title = _cell(chunk, "sbj")
        if not title:
            continue
        m = LINK.search(chunk)
        no = m.group(2) if m else ""
        if not no or no in seen:
            continue
        seen.add(no)
        rows.append({
            "id": no,
            "title": title,
            "posted": _date(_cell(chunk, "date")),
        })

    if not rows:
        print(f"  ! 캠시스: 공고를 찾지 못했습니다. 받은 HTML {len(page)}자. "
              f"화면 구조가 바뀌었거나 공고가 없을 수 있습니다. {LIST}")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company.get("code"))

    jobs = []
    for x in rows:
        jobs.append({
            "id": f"cammsys-{x['id']}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            "title": x["title"],
            # 목록에 근무지가 없습니다. 지어내지 않습니다.
            "location": "",
            "career": _career(x["title"]),
            "postedAt": x["posted"],
            # 게시판이라 마감일 칸이 없습니다.
            "closesAt": "",
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": VIEW.format(x["id"]),
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })
    return jobs
