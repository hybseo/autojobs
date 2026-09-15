# -*- coding: utf-8 -*-
"""
유진로봇(yujinrobot.com) 채용 수집기.

목록  GET https://yujinrobot.com/company/recruit
상세  GET https://yujinrobot.com/company/recruit/{이름}

물류·청소 자율주행 로봇(AMR). 코스닥. 독일 밀레가 최대주주입니다.

화면을 보고 짜면 안 됩니다 — 실제로 그래서 0건이 났습니다
----------------------------------------------------------
처음에는 개발자도구 화면을 보고 짰습니다. 거기에는 이렇게 보였습니다.

    <article class="recruit-item">
      <h2>...</h2>
      <div>2026-09-05 ~ 2026-10-05</div>
      <div>채용중</div>
    </article>

그런데 2026-09-15 수집에서 0건이 나왔습니다. 서버가 주는 HTML 을 그대로
받아 보니 셋 다 없었습니다.

    recruit-item   0회
    날짜            0회
    "채용중"        0회

클래스도 날짜도 상태도 전부 자바스크립트가 나중에 만든 것이었습니다.
시프트업·리크루터 구버전에 이어 세 번째로 같은 실수를 했습니다.
개발자도구에 보이는 것은 자바스크립트가 다 돌고 난 뒤의 모습입니다.
수집기는 그 전 상태를 받습니다.

서버 HTML 의 실제 구조 (2026-09-15 확인)
----------------------------------------
    <article ...>
      <span class="postList">
        <div class="thumbNail">...</div>
        <div class="description">
          <h2>자율주행솔루션사업부 PM (경력)</h2>
        </div>
      </span>
    </article>

클래스는 postList·thumbNail·description 입니다. 날짜와 상태는 없습니다.

채용 공고와 제품 소개를 어떻게 가르는가
--------------------------------------
같은 페이지에 제품 소개가 섞여 있습니다. article 열두 개 중 공고는 넷입니다.

    0~3   채용 공고   onclick 에 /company/recruit/... 주소가 있음
    4~11  제품 소개   GoCart180, 커스텀 AMR 등. onclick 이 없음

그래서 onclick 에 상세 주소가 있는 것만 공고로 봅니다. article 만 세면
GoCart 가 공고로 올라갑니다.

마감일과 상태에 대하여
---------------------
서버 HTML 에 없습니다. 자바스크립트가 만들기 때문에 가져올 수 없습니다.

    closesAt  비웁니다 → 사이트가 상시채용으로 표시
    상태 필터  못 합니다 → 목록에 남은 것을 모두 담습니다

2026-09-15 기준 목록의 넷이 모두 채용중이었습니다. 마감된 공고가 목록에
남는 회사라면 마감된 것까지 담기게 됩니다. 그때는 상세 페이지를 읽어
날짜를 가져오도록 고쳐야 합니다.

주소에 한글이 들어갑니다
------------------------
    /company/recruit/스마트자동화시스템사업부-전장설계경력

퍼센트 인코딩해서 내보냅니다. 영문 주소(rnd_pm, rnd_swe)인 공고도 섞여
있어 둘 다 처리합니다.
"""
import hashlib
import html
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://yujinrobot.com"
LIST_URL = BASE + "/company/recruit"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

TITLE = re.compile(r"<h2[^>]*>([\s\S]{1,120}?)</h2>", re.I)
# onclick 안의 상세 주소. 한글이 인코딩된 것도, 영문도 모두 잡습니다.
DETAIL = re.compile(r"/company/recruit/([^'\"\s>]+)", re.I)


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
    """제목 괄호에서만 읽습니다. 없으면 무관. 지어내지 않습니다."""
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


def _url(tail):
    """상세 주소. 한글이 들어가므로 퍼센트 인코딩해서 내보냅니다."""
    if not tail:
        return LIST_URL
    t = html.unescape(tail).strip("'\" ")
    # 이미 인코딩된 주소는 그대로 둡니다. 두 번 인코딩하면 깨집니다.
    if re.search(r"%[0-9A-Fa-f]{2}", t):
        return f"{LIST_URL}/{t}"
    return f"{LIST_URL}/{urllib.parse.quote(t, safe='')}"


def list_open():
    """공고 목록. probe 용으로 밖에서도 씁니다."""
    page = _get(LIST_URL)

    rows, products = [], 0
    for chunk in page.split("<article")[1:]:
        # 다음 article 전까지만 봅니다. 마지막 조각에는 뒤쪽 내용이 붙습니다.
        body = chunk.split("</article>")[0]

        # 상세 주소가 있는 것만 채용 공고입니다.
        # 제품 소개(GoCart 등)에는 onclick 이 없습니다.
        m = DETAIL.search(body)
        if not m:
            products += 1
            continue

        t = TITLE.search(body)
        if not t:
            continue
        title = _text(t.group(1))
        if not title:
            continue

        rows.append({"title": title, "url": _url(m.group(1))})

    if not rows:
        # HTML 파싱이라 화면이 바뀌면 조용히 0건이 됩니다.
        print(f"  ! 유진로봇: 공고를 찾지 못했습니다. ({LIST_URL})")
        print(f"    받은 HTML {len(page)}자 · "
              f"'<article' {page.count('<article')}개 · "
              f"'/company/recruit/' {page.count('/company/recruit/')}회 · "
              f"제품으로 걸러진 것 {products}건")
    elif products:
        print(f"  · 유진로봇: 공고 {len(rows)}건 (제품 소개 {products}건 제외)")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]

    rows = list_open()

    jobs, seen = [], {}
    for x in rows:
        # 공고 번호가 없습니다. 주소 끝조각으로 만듭니다.
        #
        # id 는 우리 사이트의 주소(/job/{id}/)가 되므로 영문·숫자만 씁니다.
        # 한글 주소인 공고가 있어 그대로 쓰면 주소에 한글이 섞입니다.
        # 한글뿐이면 주소 전체를 짧은 숫자로 바꿔 씁니다.
        tail = urllib.parse.unquote(x["url"].rstrip("/").split("/")[-1])
        jid = re.sub(r"[^A-Za-z0-9_]", "", tail)[:20]
        if len(jid) < 3:
            # hash() 는 파이썬을 새로 띄울 때마다 값이 달라집니다. 그러면
            # 갱신할 때마다 id 가 바뀌어 같은 공고가 새 공고로 보입니다.
            # md5 는 언제 돌려도 같은 값이 나옵니다.
            jid = hashlib.md5(x["url"].encode()).hexdigest()[:10]
        seen[jid] = seen.get(jid, 0) + 1
        if seen[jid] > 1:
            jid = f"{jid}{seen[jid]}"

        jobs.append({
            "id": f"yujin-{jid}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            "title": x["title"],
            # 근무지를 목록에 주지 않습니다. 지어내지 않습니다.
            "location": "",
            "career": _career(x["title"]),
            # 게시일과 마감일이 서버 HTML 에 없습니다. 상시채용으로 둡니다.
            "postedAt": "",
            "closesAt": "",
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": x["url"],
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })

    return jobs
