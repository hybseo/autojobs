# -*- coding: utf-8 -*-
"""
유진로봇(yujinrobot.com) 채용 수집기.

목록  GET https://yujinrobot.com/company/recruit

물류·청소 자율주행 로봇(AMR). 코스닥. 독일 밀레가 최대주주입니다.

요청 한 번이면 끝납니다
-----------------------
서버가 HTML 을 완성해서 보냅니다. 제목·접수기간·상태가 모두 그 안에 있어
상세를 따로 읽지 않습니다.

함정 — 같은 페이지에 제품 소개가 섞여 있습니다
----------------------------------------------
<article> 이 열두 개인데 채용 공고는 넷뿐입니다. 나머지 여덟은 GoCart
같은 제품 소개입니다. 한 페이지에 채용과 제품이 같이 있습니다.

    <article class="recruit-item">   채용 공고
    <article class="product-item">   제품 소개

class 로 구분합니다. article 만 세면 열두 건이 잡혀 제품까지 공고로
올라갑니다. 2026-09-15 에 실제로 그렇게 잘못 셌습니다.

목록 구조 (2026-09-15 확인)
---------------------------
    <article class="recruit-item" onclick="location.href='...'">
      <h2>스마트자동화시스템사업부 전장설계(경력)</h2>
      <div>2026-09-05 ~ 2026-10-05</div>
      <div>채용중</div>
    </article>

상세 주소가 onclick 안에 있습니다
---------------------------------
<a href> 가 아니라 onclick="location.href='...'" 로 이동합니다.
그래서 링크만 찾으면 하나도 안 잡힙니다. onclick 속성에서 주소를 꺼냅니다.

주소에 한글이 들어갑니다

    /company/recruit/스마트자동화시스템사업부-전장설계경력

퍼센트 인코딩해서 내보냅니다.

상태로 거릅니다
--------------
"채용중" 인 것만 담습니다. 마감된 공고도 목록에 남습니다.
"""
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

# 채용 공고만. 같은 페이지의 product-item 은 제품 소개입니다.
ITEM = re.compile(r'<article[^>]*class="[^"]*recruit-item[^"]*"[^>]*>(.*?)</article>',
                  re.S | re.I)
# 위 정규식이 놓칠 때를 대비해 article 전체도 봅니다.
ANY_ARTICLE = re.compile(r'<article([^>]*)>(.*?)</article>', re.S | re.I)

TITLE = re.compile(r"<h\d[^>]*>(.*?)</h\d>", re.S | re.I)
PERIOD = re.compile(r"(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})")
STATE = re.compile(r"(채용중|채용\s*마감|마감)")
ONCLICK = re.compile(r"""onclick=["'][^"']*?location\.href\s*=\s*['"]([^'"]+)['"]""",
                     re.I)


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


def _url(href):
    """주소에 한글이 들어갑니다. 퍼센트 인코딩해서 내보냅니다."""
    if not href:
        return LIST_URL
    u = urllib.parse.urljoin(LIST_URL + "/", html.unescape(href))
    parts = urllib.parse.urlsplit(u)
    return urllib.parse.urlunsplit((
        parts.scheme, parts.netloc,
        urllib.parse.quote(parts.path, safe="/"),
        parts.query, parts.fragment))


def list_open():
    """채용중 공고만 골라 돌려줍니다. probe 용으로 밖에서도 씁니다."""
    page = _get(LIST_URL)

    chunks = ITEM.findall(page)
    if not chunks:
        # class 이름이 바뀌었을 수 있습니다. 날짜가 있는 article 만 골라 봅니다.
        chunks = [body for attrs, body in ANY_ARTICLE.findall(page)
                  if PERIOD.search(body)]

    rows, closed = [], 0
    for chunk in chunks:
        t = TITLE.search(chunk)
        if not t:
            continue
        title = _text(t.group(1))
        if not title:
            continue

        st = STATE.search(_text(chunk))
        state = st.group(1) if st else ""
        # 마감된 공고도 목록에 남습니다. 채용중만 담습니다.
        if state and state != "채용중":
            closed += 1
            continue

        p = PERIOD.search(chunk)
        start = p.group(1) if p else ""
        end = p.group(2) if p else ""

        oc = ONCLICK.search(chunk)
        rows.append({
            "title": title,
            "start": start,
            "end": end,
            "url": _url(oc.group(1) if oc else ""),
        })

    if not rows:
        # HTML 파싱이라 화면이 바뀌면 조용히 0건이 됩니다.
        print(f"  ! 유진로봇: 채용중 공고를 찾지 못했습니다. ({LIST_URL})")
        print(f"    받은 HTML {len(page)}자 · "
              f"'recruit-item' {page.count('recruit-item')}회 · "
              f"'<article' {page.count('<article')}회 · "
              f"마감으로 걸러진 것 {closed}건")
    elif closed:
        print(f"  · 유진로봇: 채용중 {len(rows)}건 (마감 {closed}건 제외)")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]

    rows = list_open()

    jobs, seen = [], {}
    for x in rows:
        # 공고 번호가 없습니다. 주소 끝조각으로 만듭니다.
        tail = urllib.parse.unquote(x["url"].rstrip("/").split("/")[-1])
        jid = re.sub(r"[^\w]", "", tail)[:20]
        if not jid:
            jid = re.sub(r"[^\w]", "", x["title"])[:20]
        seen[jid] = seen.get(jid, 0) + 1
        if seen[jid] > 1:
            jid = f"{jid}-{seen[jid]}"

        jobs.append({
            "id": f"yujin-{jid}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            "title": x["title"],
            # 근무지를 목록에 주지 않습니다. 지어내지 않습니다.
            "location": "",
            "career": _career(x["title"]),
            "postedAt": x["start"],
            "closesAt": x["end"],
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": x["url"],
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })

    return jobs
