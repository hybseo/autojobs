# -*- coding: utf-8 -*-
"""
오늘의집(bucketplace.com) 채용 수집기.

목록  GET https://www.bucketplace.com/careers/
상세  https://bucketplace.career.greetinghr.com/ko/o/{번호}

왜 그리팅 어댑터를 쓰지 않는가
------------------------------
오늘의집은 그리팅을 쓰긴 합니다. 그런데 목록 페이지를 닫아 두었습니다.

    bucketplace.career.greetinghr.com/ko          404
    bucketplace.career.greetinghr.com/ko/recruit  404
    bucketplace.career.greetinghr.com/ko/o/167227 정상 (개별 공고)

그리팅 어댑터는 /ko 를 읽어 목록을 만드는데 그 페이지가 없어 404 가 났습니다
(2026-09-22 수집 실패). 목록은 회사 홈페이지에만 있습니다.

목록 구조 (2026-09-22 확인)
---------------------------
서버가 HTML 을 완성해서 보냅니다. 직군별로 묶여 있습니다.

    <div class="recruit-page__job-list__list__wrap__title">Engineering</div>
    <a href="https://bucketplace.career.greetinghr.com/ko/o/167227"
       class="recruit-page__job-list__list__wrap__item">Senior Backend Engineer, ...</a>

직군 이름은 제목 앞에 붙이지 않습니다. 사이트가 직무를 따로 분류하기 때문에
제목을 건드리면 오히려 분류가 어긋납니다.

담기지 않는 것
--------------
목록에 날짜·경력·근무지가 없습니다. 본문도 없습니다. 지어내지 않고 비워
두면 사이트가 상시채용으로 표시하고, 카드를 누르면 원문으로 보냅니다.
"""
import html
import re
import time
import urllib.error
import urllib.request

LIST_URL = "https://www.bucketplace.com/careers/"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# 공고 링크. 그리팅 개별 공고 주소로 나갑니다.
ITEM = re.compile(
    r'<a[^>]+href="(https://[a-z0-9-]+\.career\.greetinghr\.com/ko/o/(\d+))"[^>]*>(.*?)</a>',
    re.S | re.I)


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


def list_open(code=""):
    """공고 목록. probe 용으로 밖에서도 씁니다."""
    page = _get(LIST_URL)

    rows, seen = [], set()
    for url, no, label in ITEM.findall(page):
        title = _text(label)
        if not title or no in seen:
            continue
        seen.add(no)
        rows.append({"id": no, "title": title, "url": url})

    if not rows:
        print(f"  ! 오늘의집: 공고를 찾지 못했습니다. ({LIST_URL})")
        print(f"    받은 HTML {len(page)}자 · "
              f"'greetinghr' {page.count('greetinghr')}회. 화면 구조가 바뀌었을 수 있습니다.")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company.get("code"))

    jobs = []
    for x in rows:
        jobs.append({
            "id": f"bucketplace-{x['id']}",
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
