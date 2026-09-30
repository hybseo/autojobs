# -*- coding: utf-8 -*-
"""
이수그룹(recruit.isu.co.kr) 채용 수집기.

목록  GET https://recruit.isu.co.kr/future_recruit/
상세  https://recruit.isu.co.kr/?page_id=...&announceId={번호}

이수페타시스(AI 서버용 고다층 기판)·이수스페셜티케미컬 등 계열사 공고가
한곳에 모여 옵니다. 워드프레스로 만든 자체 사이트입니다.

요청 한 번이면 끝납니다
-----------------------
서버가 HTML 을 완성해 보냅니다. 70만 자가 넘지만 공고는 다섯 건 남짓이고,
제목·기간·구분이 모두 그 안에 있어 상세를 따로 읽지 않습니다.

공고 한 건의 생김새 (2026-09-30 확인)
-------------------------------------
    <a href="...announceId=2450243">
      <div class="column_attr">
        <span>수시</span>
        <span class="task-type">상시</span>
        <h3 class="title">2026년 이수페타시스 경력사원 공개채용</h3>
        <span>2026.09.22</span>
        <span>~ 채용시까지</span>

마감일이 두 가지로 옵니다
-------------------------
    "~ 채용시까지"            마감일 없음 → 상시채용으로 표시
    "~" 다음에 2026.10.13     그 날짜가 마감일

계열사 거르기
-------------
건설 계열사도 함께 옵니다. companies.json 의 affiliates 에 적은 곳만
담습니다. 회사명이 따로 오지 않고 제목에만 들어 있어 제목에서 찾습니다.
"""
import html
import re
import time
import urllib.error
import urllib.request

BASE = "https://recruit.isu.co.kr"
LIST = BASE + "/future_recruit/"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

ITEM = re.compile(
    r'<a[^>]+href="([^"]*announceId=(\d+)[^"]*)"[^>]*>(.*?)</a>', re.S | re.I)
TITLE = re.compile(r'<h3[^>]*class="[^"]*\btitle\b[^"]*"[^>]*>(.*?)</h3>', re.S | re.I)
SPAN = re.compile(r"<span[^>]*>(.*?)</span>", re.S | re.I)
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
            with urllib.request.urlopen(req, timeout=30) as r:
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
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def _career(title, kind):
    t = f"{title} {kind}"
    has_new = "신입" in t or "공채" in t
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

    rows, seen = [], set()
    for href, no, block in ITEM.findall(page):
        if no in seen:
            continue
        m = TITLE.search(block)
        if not m:
            continue
        title = _text(m.group(1))
        if not title:
            continue
        seen.add(no)

        spans = [s for s in (_text(x) for x in SPAN.findall(block)) if s]
        dates = []
        for s in spans:
            d = DATE.search(s)
            if d:
                dates.append(f"{d.group(1)}-{int(d.group(2)):02d}-{int(d.group(3)):02d}")
        always = any("채용시까지" in s for s in spans)

        rows.append({
            "id": no,
            "title": title,
            "kind": next((s for s in spans if s in ("공채", "수시", "상시")), ""),
            "posted": dates[0] if dates else "",
            "closes": "" if always else (dates[1] if len(dates) > 1 else ""),
            "url": href if href.startswith("http") else BASE + "/" + href.lstrip("/"),
        })

    if not rows:
        print(f"  ! 이수그룹: 공고를 찾지 못했습니다. 받은 HTML {len(page)}자. "
              f"화면 구조가 바뀌었을 수 있습니다. {LIST}")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company.get("code"))

    want = [a for a in (company.get("affiliates") or []) if str(a).strip()]
    if want:
        before = len(rows)
        rows = [x for x in rows if any(_norm(w) in _norm(x["title"]) for w in want)]
        if before != len(rows):
            print(f"      · {name}: 계열사 거르기 {before}건 → {len(rows)}건")

    jobs = []
    for x in rows:
        # 제목에 들어 있는 계열사명을 회사명으로 씁니다.
        co = name
        for w in want:
            if _norm(w) in _norm(x["title"]):
                co = w
                break

        jobs.append({
            "id": f"isu-{x['id']}",
            "unit": "공고",
            "company": co,
            "companySlug": slug,
            "title": x["title"],
            # 목록에 근무지가 없습니다. 지어내지 않습니다.
            "location": "",
            "career": _career(x["title"], x["kind"]),
            "postedAt": x["posted"],
            "closesAt": x["closes"],
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": x["url"],
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })
    return jobs
