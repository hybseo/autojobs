# -*- coding: utf-8 -*-
"""
코스모신소재(cosmoamt.com) 채용 수집기.

목록  GET https://www.cosmoamt.com/?page_id=11170
상세  GET https://www.cosmoamt.com/?mod=document&page_id=11170&uid={번호}

이차전지 양극재와 MLCC 이형필름을 만드는 회사입니다. 워드프레스에
게시판(KBoard)을 붙여 씁니다.

요청 한 번이면 끝납니다
-----------------------
서버가 HTML 을 완성해 보냅니다(15만 자). 제목·작성일이 표 안에 있어
상세를 따로 읽지 않습니다. 2026-10-02 확인 공고가 있었습니다.

목록 구조
---------
    <table class="kboard-list"><tbody>
      <tr>
        <td class="cosmo_num">15</td>
        <td class="cosmo_title"><a href="?mod=document&page_id=11170&uid=15114">
            품질관리 경력사원 채용</a></td>
        <td class="cosmo_name">코스모신소재</td>
        <td class="cosmo_date">2026-02-13</td>
      </tr>

칸 이름이 cosmo_ 로 시작합니다. 흔한 게시판 틀이 아니므로 이름을 그대로
찾습니다.

마감 여부를 알 수 없습니다
--------------------------
접수 기간도 "진행중/마감" 표시도 없고 작성일만 있습니다. 그래서 작성일이
1년이 지난 공고는 담지 않습니다. 지난 공고를 지우지 않고 쌓아 두는
게시판이라 전부 담으면 몇 년 전 공고가 사이트에 올라옵니다.

지원은 recruit.cosmoamt.com 에서 받지만 그곳은 로그인을 요구해서
목록을 읽을 수 없습니다. 홈페이지 게시판만 봅니다.
"""
import html
import re
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

BASE = "https://www.cosmoamt.com"
LIST = BASE + "/?page_id=11170"
VIEW = BASE + "/?mod=document&page_id=11170&uid={}"

# 작성일이 이보다 오래된 공고는 담지 않습니다.
MAX_AGE_DAYS = 365

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
UID = re.compile(r"uid=(\d+)", re.I)
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
            with urllib.request.urlopen(req, timeout=45) as r:
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
        title = _cell(chunk, "cosmo_title")
        if not title:
            continue

        m = UID.search(chunk)
        no = m.group(1) if m else _cell(chunk, "cosmo_num")
        if not no or no in seen:
            continue

        posted = _date(_cell(chunk, "cosmo_date"))
        if posted and posted < cut:
            old += 1
            continue

        seen.add(no)
        rows.append({"id": no, "title": title, "posted": posted})

    if not rows:
        print(f"  ! 코스모신소재: 최근 1년 안에 올라온 공고가 없습니다. (오래된 글 {old}건)")
    elif old:
        print(f"  · 코스모신소재: {len(rows)}건 (1년 넘은 글 {old}건 제외)")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company.get("code"))

    jobs = []
    for x in rows:
        jobs.append({
            "id": f"cosmoamt-{x['id']}",
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
            "sourceUrl": VIEW.format(x["id"]),
            "description": "",
        })
    return jobs
