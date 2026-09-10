# -*- coding: utf-8 -*-
"""
HPSP(thehpsp.com) 채용 수집기.

목록  GET https://thehpsp.com/bbs/board.php?bo_table=career
상세  GET https://thehpsp.com/bbs/board.php?bo_table=career&wr_id={번호}

고압 수소 어닐링 장비 회사입니다. 코스닥.

게시판입니다. 그래도 담는 이유
------------------------------
채용 시스템이 아니라 그누보드 게시판입니다. 보통 게시판은 "이런 직무를
뽑는다" 는 안내만 있어 담지 않지만(리노공업·한미반도체를 그래서 뺐습니다),
여기는 다릅니다.

    [Asia GPS] Asia GPS Manager 채용
    [Sales] Sales Account Manager 채용
    [Engineering] Electrical Engineer 채용

포지션이 하나씩 특정되어 있고 본문에 담당업무·자격요건·근무조건이
제대로 적혀 있습니다. 구직자에게 쓸모 있는 실제 구인 정보입니다.

마감일이 없습니다 — 전부 상시채용입니다
---------------------------------------
본문에 "접수기간 : 2025.11.14~채용시" 처럼 적혀 있습니다. 끝나는 날이
정해져 있지 않습니다. closesAt 을 비우면 사이트가 상시채용으로 표시합니다.

게시일이 오래돼 보여도 마감이 아닙니다. 2026-09-10 확인 시점에 가장 최근
글이 2025년 11월이었는데, 채용 시 마감이라 여전히 열려 있는 자리입니다.
날짜만 보고 걸러내면 안 됩니다.

지원은 외부 포털로 갑니다
-------------------------
본문 끝에 사람인·잡코리아 링크가 붙어 있습니다. 우리는 원문(이 게시글)
으로 보내고, 거기서 구직자가 포털을 고르게 둡니다. 중간에 끼어들어
어느 포털로 보낼지 정하지 않습니다.

목록 구조 (2026-09-10 확인)
---------------------------
그누보드 기본 틀입니다.

    <tr>
      <td class="td_num2">8</td>
      <td class="td_subject"><div class="bo_tit">
        <a href="...&wr_id=64">[Asia GPS] Asia GPS Manager 채용</a>
      </div></td>
      <td class="td_name sv_use">관리자hr</td>
      <td class="td_num">4534</td>
      <td class="td_datetime">11-17</td>
    </tr>

목록의 날짜는 "11-17" 로 연도가 없습니다. 상세 페이지에는
"25-11-17 14:48" 로 연도가 있으니 그쪽을 씁니다.

본문 영역은 class="bo_v_con" 입니다.

직군 표시에 대하여
------------------
제목 앞 대괄호가 조직 구분입니다([Sales], [Engineering], [FM] 등).
그대로 두면 구직자가 어느 팀인지 바로 압니다. 떼어내지 않습니다.
"""
import html
import re
import time
import urllib.error
import urllib.request

BASE = "https://thehpsp.com"
BOARD = BASE + "/bbs/board.php?bo_table=career"
DETAIL = BASE + "/bbs/board.php?bo_table=career&wr_id={}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

MAX_PAGES = 10  # 안전장치. 게시판 한 쪽에 보통 15건입니다.

# 목록의 글 링크. wr_id 가 글 번호입니다.
ROW = re.compile(r'<a[^>]+href="([^"]*wr_id=(\d+)[^"]*)"[^>]*>(.*?)</a>', re.S | re.I)
# 상세 본문.
BODY = re.compile(r'<div[^>]+class="[^"]*bo_v_con[^"]*"[^>]*>(.*?)</div>', re.S | re.I)
# 상세의 작성일. "25-11-17 14:48"
WROTE = re.compile(r"(\d{2})-(\d{2})-(\d{2})\s+\d{2}:\d{2}")

# 제목에 이런 말이 들어가면 채용 공고가 아닙니다.
SKIP = re.compile(r"공지|안내문|FAQ|자주\s*묻는", re.I)


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


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def _posted(page):
    """상세 페이지에서 작성일을 꺼냅니다. '25-11-17' → '2025-11-17'."""
    m = WROTE.search(page or "")
    if not m:
        return ""
    yy, mm, dd = m.groups()
    return f"20{yy}-{mm}-{dd}"


def _career(title, body):
    """제목과 본문에서만 읽습니다. 없으면 무관. 지어내지 않습니다."""
    t = f"{title} {body[:600]}"
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
    """공고 목록. probe 용으로 밖에서도 씁니다."""
    seen, rows = set(), []

    for p in range(1, MAX_PAGES + 1):
        url = BOARD if p == 1 else f"{BOARD}&page={p}"
        page = _get(url)

        added = 0
        for href, wid, title_html in ROW.findall(page):
            title = _text(title_html)
            # 링크 텍스트가 비었거나(아이콘 등) 너무 짧으면 글 제목이 아닙니다.
            if len(title) < 4 or wid in seen:
                continue
            if SKIP.search(title):
                continue
            seen.add(wid)
            rows.append({"id": wid, "title": title})
            added += 1

        if added == 0:
            if p == 1:
                # HTML 파싱이라 화면이 바뀌면 조용히 0건이 됩니다.
                print(f"  ! HPSP: 공고를 하나도 찾지 못했습니다. ({BOARD})")
                print(f"    받은 HTML {len(page)}자 · "
                      f"'wr_id=' {page.count('wr_id=')}회 · "
                      f"'bo_tit' {page.count('bo_tit')}회")
            break
        time.sleep(0.3)

    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]

    rows = list_open()

    jobs = []
    for x in rows:
        url = DETAIL.format(x["id"])

        raw, posted = "", ""
        try:
            page = _get(url)
            m = BODY.search(page)
            raw = m.group(1) if m else ""
            posted = _posted(page)
        except Exception:
            pass
        time.sleep(0.3)

        text = strip_html(raw)
        # 본문이 이미지뿐이면 세부 직무를 읽을 수 없습니다. 원문으로 보냅니다.
        image_only = len(text) < 50 and "<img" in raw.lower()

        jobs.append({
            "id": f"hpsp-{x['id']}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            # 제목 앞 대괄호가 조직 구분입니다. 그대로 둡니다.
            "title": x["title"],
            # 근무지가 본문에만 있고 표기가 일정하지 않습니다. 지어내지 않습니다.
            "location": "",
            "career": _career(x["title"], text),
            "postedAt": posted,
            # 전부 "채용시 마감" 입니다. 비우면 상시채용으로 표시됩니다.
            "closesAt": "",
            "dday": None,
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": url,
            "description": raw if not image_only else "",
        })

    return jobs
