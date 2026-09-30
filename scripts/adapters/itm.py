# -*- coding: utf-8 -*-
"""
아이티엠반도체(itmsemiconductor.com) 채용 수집기.

목록  GET https://www.itmsemiconductor.com/kor/recruit/recruit_notice.php
상세  GET https://www.itmsemiconductor.com/kor/recruit/recruit_notice.php?mode=view&idx={번호}

배터리 보호회로·모듈을 만드는 회사입니다. 자체 게시판을 씁니다.

요청 한 번이면 끝납니다
-----------------------
서버가 HTML 을 완성해 보냅니다. 제목·작성일이 표 안에 있습니다.
2026-09-30 확인 3건이었습니다.

    [채용] 2026년 하반기 신입/경력 수시채용   2026-09-15
    [채용] 생산기술직(안성) 채용              2026-08-20
    [채용] 품질개발 공정개발 채용             2026-07-30

제목 앞의 [채용] 은 떼고 담습니다. 목록에 그 말머리가 모든 줄에 붙어 있어
정보가 되지 못하고 제목만 길어집니다.

마감일이 없습니다
-----------------
게시판이라 접수 마감일 칸이 없습니다. 상시채용으로 표시하고 카드를 누르면
원문으로 보냅니다. 없는 날짜를 지어내지 않습니다.

사이트가 가끔 응답하지 않습니다
-------------------------------
2026-09-30 확인 중에도 한동안 연결되지 않았습니다. 수집이 실패하면
잠시 뒤 다시 시도하며, 계속 실패하면 로그에 남깁니다.
"""
import html
import re
import time
import urllib.error
import urllib.request

BASE = "https://www.itmsemiconductor.com"
LIST = BASE + "/kor/recruit/recruit_notice.php"
VIEW = BASE + "/kor/recruit/recruit_notice.php?mode=view&idx={}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
LINK = re.compile(r'href="([^"]*idx=(\d+)[^"]*)"', re.I)
YMD = re.compile(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})")
HEAD = re.compile(r"^\s*\[\s*채\s*용\s*\]\s*")


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
                time.sleep(3 + i * 3)
    raise last


def _text(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def _date(v):
    m = YMD.search(str(v or ""))
    if not m:
        return ""
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


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
        m = LINK.search(chunk)
        if not m:
            continue
        no = m.group(2)
        if no in seen:
            continue

        # 제목은 링크 글자입니다. m.group(0) 은 href 까지 통째로라
        # 그대로 쓰면 주소가 제목이 됩니다. 링크 안쪽만 꺼냅니다.
        a = re.search(r'<a[^>]*idx=' + no + r'[^>]*>(.*?)</a>', chunk, re.S | re.I)
        title = _text(a.group(1)) if a else ""
        if not title:
            # 링크 글자가 비면 칸 중에서 가장 긴 글자를 제목으로 봅니다.
            cells = [_text(c) for c in TD.findall(chunk)]
            for c in cells:
                if len(c) > len(title) and not c.isdigit():
                    title = c
        title = HEAD.sub("", title).strip()
        cells = [_text(c) for c in TD.findall(chunk)]
        if not title:
            continue

        posted = ""
        for c in cells:
            d = _date(c)
            if d:
                posted = d
                break

        seen.add(no)
        rows.append({"id": no, "title": title, "posted": posted})

    if not rows:
        print(f"  ! 아이티엠반도체: 공고를 찾지 못했습니다. 받은 HTML {len(page)}자. "
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
            "id": f"itm-{x['id']}",
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
