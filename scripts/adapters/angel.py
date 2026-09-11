# -*- coding: utf-8 -*-
"""
엔젤로보틱스(angel-robotics.com) 채용 수집기.

목록  GET https://www.angel-robotics.com/ko/recruit/notice
상세  GET https://www.angel-robotics.com/ko/recruit/notice/{슬러그}

웨어러블 재활로봇. 코스닥. 서울(플래닛 서울)과 대전(플래닛 대전) 두 곳에서
연구·QA·영업 인력을 뽑습니다.

요청 한 번이면 끝납니다
-----------------------
서버가 HTML 을 완성해서 보냅니다. 공고 제목·팀·근무지가 모두 그 안에 있어
상세를 따로 읽지 않습니다. 별도 API 호출도 없습니다.

클래스 이름에 기대지 마세요
---------------------------
Tailwind 를 쓰는 사이트라 클래스가 이렇게 생겼습니다.

    class="scroll-mt-[30vh] border-b border-dd-gray-light/50"
    class="font-bold text-dd-blue"

색과 여백을 나타낼 뿐 의미가 없고, 디자인을 손대면 통째로 바뀝니다.
그래서 클래스 대신 <li> 안의 요소 순서로 값을 찾습니다.

목록 구조 (2026-09-11 확인)
---------------------------
공고 한 건이 <li> 하나이고, 그 안에 span 이 넷, p 가 하나 있습니다.

    <li>
      <a href="./notice/{슬러그}">
        <div>
          <span>Business Development Team</span>   팀
          <span>|</span>                            구분자
          <span>플래닛 서울</span>                   근무지
          <span>Technology & Business Strategy</span>  공고 제목
        </div>
        <div><p>채용 시 마감</p></div>
      </a>
    </li>

두 번째 span 은 화면에 구분자로 찍히는 "|" 입니다. 값이 아닙니다.
아래에서는 그런 한 글자짜리를 건너뛰고 나머지를 순서대로 씁니다.

span 이 셋뿐인 공고도 있을 수 있어(구분자가 없는 등) 개수로 단정하지 않고,
쓸 만한 것만 골라 앞에서부터 팀·근무지·제목으로 봅니다.

마감일에 대하여
--------------
2026-09-11 기준 10건 모두 "채용 시 마감" 이었습니다. 날짜가 아니므로
closesAt 을 비웁니다. 비우면 사이트가 상시채용으로 표시합니다.

경력 구분에 대하여
------------------
목록에 따로 주지 않습니다. 다만 제목 앞에 [경력], [신입/경력] 이 붙는
공고가 많아 그때만 읽습니다. 없으면 무관입니다. 지어내지 않습니다.

건수에 대하여
------------
화면에는 "총 15건" 이라고 적혀 있는데 한 쪽에 10건씩 나옵니다.
2쪽이 있는지 확인해 더 받습니다.
"""
import html
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://www.angel-robotics.com"
LIST_URL = BASE + "/ko/recruit/notice"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

MAX_PAGES = 6   # 한 쪽 10건이면 60건까지 봅니다.

LI = re.compile(r"<li\b", re.I)
SPAN = re.compile(r"<span[^>]*>(.*?)</span>", re.S | re.I)
P = re.compile(r"<p[^>]*>(.*?)</p>", re.S | re.I)
HREF = re.compile(r'href="([^"]+)"', re.I)

# 마감 표시가 이 말이면 날짜가 아닙니다.
ALWAYS = re.compile(r"채용\s*시\s*마감|상시|수시", re.I)


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


def _date(v):
    """'2026.09.30' → '2026-09-30'. "채용 시 마감" 이면 빈 문자열(상시채용)."""
    if ALWAYS.search(str(v or "")):
        return ""
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", str(v or ""))
    if not m:
        return ""
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def _career(title):
    """제목 앞 대괄호에서만 읽습니다. 없으면 무관. 지어내지 않습니다."""
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


def _parse(page):
    """한 쪽에서 공고를 뽑습니다."""
    rows = []
    for chunk in LI.split(page)[1:]:
        chunk = chunk[:2500]
        # 마감 표시가 있는 <li> 만 공고입니다. 메뉴 등은 걸러집니다.
        ps = [_text(x) for x in P.findall(chunk)]
        deadline = next((x for x in ps if x), "")
        if not deadline:
            continue

        # 한 글자짜리(구분자 "|")는 값이 아닙니다.
        spans = [_text(x) for x in SPAN.findall(chunk)]
        spans = [x for x in spans if len(x) > 1]
        if len(spans) < 2:
            continue

        # 앞에서부터 팀 · 근무지 · 제목. 제목이 가장 뒤입니다.
        team = spans[0]
        title = spans[-1]
        location = spans[1] if len(spans) >= 3 else ""
        if not title or title == team:
            continue

        m = HREF.search(chunk)
        href = html.unescape(m.group(1)) if m else ""
        # "./notice/xxx" 처럼 상대 주소로 옵니다.
        #
        # 주의: 기준 주소를 LIST_URL + "/" 로 잡으면 안 됩니다. LIST_URL 이
        # 이미 .../recruit/notice 라서 notice 가 두 번 들어갑니다.
        #   .../recruit/notice/notice/bd-strategy   ← 틀림
        # 한 단계 위(/ko/recruit/)를 기준으로 삼아야 맞습니다.
        url = urllib.parse.urljoin(BASE + "/ko/recruit/", href) if href else LIST_URL

        rows.append({
            "title": title,
            "team": team,
            "location": location,
            "deadline": deadline,
            "url": url,
        })
    return rows


def list_open():
    """공고 목록. probe 용으로 밖에서도 씁니다."""
    rows, seen = [], set()
    for p in range(1, MAX_PAGES + 1):
        url = LIST_URL if p == 1 else f"{LIST_URL}?page={p}"
        page = _get(url)
        got = _parse(page)

        added = 0
        for x in got:
            key = x["url"] or x["title"]
            if key in seen:
                continue
            seen.add(key)
            rows.append(x)
            added += 1

        if added == 0:
            if p == 1:
                # HTML 파싱이라 화면이 바뀌면 조용히 0건이 됩니다.
                print(f"  ! 엔젤로보틱스: 공고를 찾지 못했습니다. ({LIST_URL})")
                print(f"    받은 HTML {len(page)}자 · "
                      f"'<li' {page.count('<li')}회 · "
                      f"'채용 시 마감' {page.count('채용 시 마감')}회")
            break
        time.sleep(0.3)

    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]

    rows = list_open()

    jobs = []
    for i, x in enumerate(rows):
        # 팀명을 제목 앞에 붙입니다. 어느 조직인지 바로 보입니다.
        title = x["title"]
        if x["team"] and x["team"] not in title:
            title = f"[{x['team']}] {title}"

        # 주소 끝조각으로 id 를 만듭니다. 없으면 순번을 씁니다.
        tail = x["url"].rstrip("/").split("/")[-1]
        jid = re.sub(r"[^\w\-]", "", urllib.parse.unquote(tail))[:24] or f"n{i+1}"

        jobs.append({
            "id": f"angel-{jid}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            "title": title,
            "location": x["location"],
            "career": _career(x["title"]),
            # 게시일을 주지 않습니다.
            "postedAt": "",
            # "채용 시 마감" 이면 빈 문자열이 됩니다(상시채용).
            "closesAt": _date(x["deadline"]),
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": x["url"],
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })

    return jobs
