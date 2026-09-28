# -*- coding: utf-8 -*-
"""
회사 홈페이지에 걸린 그리팅 공고 링크를 읽는 수집기.

그리팅을 쓰면서 목록 페이지는 닫아 둔 회사가 있습니다. 개별 공고 주소는
열리는데 목록(/ko)이 404 라 그리팅 어댑터로는 아무것도 받지 못합니다.

    오늘의집   bucketplace.career.greetinghr.com/ko           404
              bucketplace.career.greetinghr.com/ko/o/167227  정상
    밀리의서재  millie.career.greetinghr.com/ko               404
              millie.career.greetinghr.com/o/143986          정상

이런 회사는 자기 홈페이지 채용 화면에 공고 링크를 걸어 둡니다. 그 화면을
읽어 링크와 제목을 꺼냅니다.

companies.json
--------------
    "ats": "greeting_link",
    "code": "https://www.bucketplace.com/careers/"     공고 목록이 있는 주소

    "ats": "greeting_link",
    "code": "https://www.millie.town/careers/"

링크 모양이 두 가지입니다
-------------------------
    .../ko/o/167227     말머리가 붙는 곳(오늘의집)
    .../o/143986        붙지 않는 곳(밀리의서재)

둘 다 받습니다. 공고 번호로 겹치는 것을 걸러냅니다.

담기지 않는 것
--------------
홈페이지 목록에는 날짜·경력·근무지가 없고 본문도 없습니다. 지어내지 않고
비워 두면 사이트가 상시채용으로 표시하고, 카드를 누르면 원문으로 갑니다.
"""
import html
import re
import time
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# 그리팅 공고 링크. 말머리(/ko)가 있을 수도 없을 수도 있습니다.
ITEM = re.compile(
    r'<a[^>]+href="(https://([a-z0-9-]+)\.career\.greetinghr\.com(?:/[a-z]{2})?/o/(\d+))'
    r'[^"]*"[^>]*>(.*?)</a>', re.S | re.I)


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
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def _career(title):
    """제목에서만 읽습니다. 없으면 무관. 지어내지 않습니다."""
    t = title or ""
    has_new = "신입" in t or re.search(r"\b(new\s*grad|intern)", t, re.I)
    has_exp = "경력" in t or re.search(r"\b(senior|lead|staff|principal)\b", t, re.I)
    if has_new and has_exp:
        return "신입/경력"
    if has_exp:
        return "경력"
    if has_new:
        return "신입"
    return "무관"


def list_open(code):
    """공고 목록. probe 용으로 밖에서도 씁니다."""
    url = str(code or "").strip()
    if not url.startswith("http"):
        raise RuntimeError("greeting_link: code 에 채용 목록 주소를 적으세요. "
                           "예) https://www.millie.town/careers/")

    page = _get(url)

    rows, seen = [], set()
    for link, sub, no, label in ITEM.findall(page):
        title = _text(label)
        if not title or no in seen:
            continue
        seen.add(no)
        rows.append({"id": no, "title": title, "url": link})

    if not rows:
        print(f"  ! greeting_link: 공고 링크를 찾지 못했습니다. {url}")
        print(f"    받은 HTML {len(page)}자 · 'greetinghr' {page.count('greetinghr')}회. "
              f"화면 구조가 바뀌었거나 공고가 없을 수 있습니다.")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company["code"])

    jobs = []
    for x in rows:
        jobs.append({
            "id": f"glink-{slug}-{x['id']}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            "title": x["title"],
            # 목록에 근무지·날짜가 없습니다. 지어내지 않습니다.
            "location": "",
            "career": _career(x["title"]),
            "postedAt": "",
            "closesAt": "",
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": x["url"],
            # 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })
    return jobs
