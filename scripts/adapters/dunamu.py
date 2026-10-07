# -*- coding: utf-8 -*-
"""
두나무 채용 수집기. 업비트·증권플러스를 만드는 회사입니다.

  목록  GET https://careers.dunamu.com/
  상세  GET https://careers.dunamu.com/detail/{번호}

robots.txt (2026-10-07 확인)
---------------------------
  User-Agent: *
  Allow: /
  (Googlebot / Googlebot-image / MSNBot / Yeti / Daumoa 도 모두 Allow: /)
전체 허용입니다. 막는 경로가 하나도 없습니다.

주소를 두 개 혼동하면 안 됩니다 — 실제로 그래서 404 가 났습니다
-------------------------------------------------------------
두나무는 채용 관련 주소가 두 개입니다.

  www.dunamu.com/careers/jobs   채용 "소식" 페이지입니다. 공고가 아닙니다.
  careers.dunamu.com            실제 공고 목록입니다. ← 여기를 씁니다.

앞의 주소를 받아 보면 __NEXT_DATA__ 안에 pageProps.articles 가 있고
첫 항목이 "두나무를 소개합니다!" 입니다. 공고가 아니라 블로그 글
목록입니다. 공고가 많아 보여도 공고가 아닙니다.

또 하나. 두나무는 예전에 Greenhouse 를 썼습니다. 그래서 Greenhouse
전수조사 때 code "dunamu" 로 찾으면 404 가 납니다. 회사가 사라진 게
아니라 자체 시스템으로 옮긴 것입니다. 404 를 보고 "폐업" 으로 적지
마세요.

API 가 없습니다
---------------
careers.dunamu.com 은 서버가 완성된 HTML 을 내려줍니다. 공고 데이터를
주는 XHR·JSON 요청이 하나도 없고 __NEXT_DATA__ 도 없습니다
(2026-10-07 브라우저 네트워크 기록으로 확인). 그래서 HTML 을 직접
읽습니다. API 를 찾느라 시간을 쓰지 마세요. 없습니다.

목록 구조 (2026-10-07 서버 원본 HTML 에서 확인)
-----------------------------------------------
    <div class="main_list_item">
      <a class="main_list_link" target="_blank" href="/detail/624">
        <div class="main_list_title">Security</div>        ← 직군
        <div class="main_list_cont">
          <div class="main_list_name">개인정보 보호 담당자</div>  ← 직무명
        </div>
        <div class="main_list_type">
          <span>경력</span><span>정규직</span>
        </div>
      </a>
    </div>

속성이 class·href 뿐이고 군더더기가 없습니다. 7개 블록이 전부이고
더보기·페이지 번호가 없습니다. 한 번 받으면 끝입니다.

본문 구조 (2026-10-07 확인)
---------------------------
    <div class="detailView_header">
      <div class="detailView_title">개인정보 보호 담당자</div>
    </div>
    <div class="detailView_banner"> ... </div>
    <div class="detailView_information"> ... 본문 ... </div>   ← 이것만 씁니다
    <div class="detailView_button">채용공고 목록</div>

detailView_information 안에는 div 가 하나도 없습니다(공고 5건 전부
확인). h3·p·ul·li·span·br·hr·a 로만 되어 있어 끊어내기 쉽습니다.
그래도 안전하게 detailView_button 앞까지를 본문으로 봅니다.

제목은 <title> 이 아니라 detailView_title 에서 가져옵니다.
<title> 은 "개인정보 보호 담당자 | 두나무" 라 회사명이 붙습니다.

날짜가 없습니다
---------------
게시일도 마감일도 사이트에 없습니다. 공고 5건 본문을 모두 뒤져도
날짜 형태의 문자열이 하나도 안 나옵니다. 지어내지 않고 빈 값으로
둡니다. 전부 상시채용으로 표시되고, 게시일은 fetch_jobs.py 가
처음 본 날(firstSeenAt)로 채웁니다.

근무지도 사이트에 없습니다. 본사가 서울인 걸 알아도 적지 않습니다.
공고마다 다를 수 있고, 확인한 값이 아닙니다.

인재풀 제외
-----------
"Talent Pool" 직군의 "개발직군 인재풀"·"일반직군 인재풀" 2건은
실제 채용이 아니라 이력서를 받아두는 창구입니다. 다른 어댑터
(Ashby 등)와 같은 기준으로 제외합니다. 그래서 7건 중 5건이 올라갑니다.

companies.json 의 code 에 대하여
-------------------------------
이 어댑터는 code 를 쓰지 않습니다. 두나무 전용이라 주소가 하나뿐입니다.
그래도 companies.json 에 code 를 반드시 적어야 합니다. fetch_jobs.py 의
load_companies() 가 name·slug·ats·code 네 칸을 모두 요구하고, 하나라도
비면 수집을 시작하지도 않고 멈춥니다(REQUIRED).

실제로 2026-10-07 에 code 를 빼고 올려서 "490번째 항목에 ['code'] 이(가)
없습니다" 로 수집이 7초에 중단됐습니다. 다른 자체 사이트 어댑터
(시프트업·SOOP·넷마블·다우기술 등)와 같이 slug 와 같은 값을 적습니다.

구조가 바뀌면 0건이 아니라 오류를 냅니다
---------------------------------------
main_list_item 이 하나도 없으면 빈 리스트를 돌려주지 않고 예외를
냅니다. 0건으로 조용히 넘기면 공고 5건이 하루아침에 사라진 것처럼
보입니다. 예외를 내면 fetch_jobs.py 가 어제 공고를 그대로 이어받고
(carry_over) 실패 목록에 적어 줍니다.
"""
import re
import html
import time
import urllib.request

LIST = "https://careers.dunamu.com/"
DETAIL = "https://careers.dunamu.com/detail/{}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# 목록의 <span> 두 개가 각각 경력 구분과 고용형태입니다. 순서를 믿지 않고
# 값으로 구분합니다. 자리를 바꿔 넣으면 "정규직 경력" 같은 게 나옵니다.
CAREER_WORDS = {"신입", "경력", "신입/경력", "무관"}
EMPLOY_WORDS = {"정규직", "계약직", "인턴", "파트타임", "프리랜서", "위촉직"}

# 이력서만 받아두는 창구. 실제 채용 공고가 아닙니다.
POOL = re.compile(r"인재\s*풀|talent\s*pool|인재\s*등록", re.I)

ITEM = re.compile(r'class="main_list_item"(.*?)</a>', re.S)
HREF = re.compile(r'href="/detail/(\d+)"')
GROUP = re.compile(r'class="main_list_title"\s*>(.*?)</div>', re.S)
NAME = re.compile(r'class="main_list_name"\s*>(.*?)</div>', re.S)
SPAN = re.compile(r"<span[^>]*>(.*?)</span>", re.S)

TITLE = re.compile(r'class="detailView_title"\s*>(.*?)</div>', re.S)
BODY = re.compile(
    r'class="detailView_information"\s*>(.*?)<div class="detailView_button"', re.S)
BODY_FALLBACK = re.compile(
    r'class="detailView_information"\s*>(.*?)</div>', re.S)


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def _text(s):
    """태그를 떼고 공백을 정리합니다. 목록의 짧은 문구용입니다."""
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def _clean_body(h):
    """본문 HTML 을 그대로 쓰되 죽은 class 만 떼어냅니다.

    두나무 쪽 class 이름(_1tnpauf2 같은 것)은 우리 사이트에 해당 CSS 가
    없어 아무 일도 하지 않습니다. 남겨두면 나중에 우리 class 와 이름이
    겹칠 수 있어 지웁니다. style 은 margin·line-height·white-space 뿐이라
    그대로 둡니다. 링크(a href)는 절대 주소라 손대지 않습니다.
    """
    return re.sub(r'\sclass="[^"]*"', "", h or "").strip()


def list_open():
    """접수중 공고 목록. probe 용으로 밖에서도 씁니다.

    돌려주는 값은 (번호, 직군, 직무명, 경력, 고용형태) 입니다.
    """
    page = _get(LIST)
    blocks = ITEM.findall(page)
    if not blocks:
        # 구조가 바뀐 것입니다. 0건으로 넘기면 공고가 사라진 것처럼 보입니다.
        raise RuntimeError(
            "careers.dunamu.com 목록에서 main_list_item 을 찾지 못했습니다. "
            "페이지 구조가 바뀐 것 같습니다.")

    out = []
    for b in blocks:
        m = HREF.search(b)
        if not m:
            continue
        nid = m.group(1)
        g = GROUP.search(b)
        n = NAME.search(b)
        group = _text(g.group(1)) if g else ""
        name = _text(n.group(1)) if n else ""
        tags = [_text(x) for x in SPAN.findall(b)]
        tags = [t for t in tags if t]

        career = next((t for t in tags if t in CAREER_WORDS), "")
        employ = next((t for t in tags if t in EMPLOY_WORDS), "")
        # 표에 없는 값이 오면 지어내지 않고 비워둡니다.
        out.append((nid, group, name, career, employ))
    return out


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    include_pool = bool(company.get("includePool"))

    jobs = []
    for nid, group, jobname, career, employ in list_open():
        if not include_pool and (POOL.search(jobname) or POOL.search(group)):
            continue

        url = DETAIL.format(nid)
        try:
            page = _get(url)
        except Exception:
            # 한 건을 못 읽어도 나머지는 올립니다.
            continue

        m = TITLE.search(page)
        title = _text(m.group(1)) if m else jobname
        if not title:
            title = jobname

        if employ and employ != "정규직" and employ not in title:
            title = f"{title} ({employ})"

        m = BODY.search(page) or BODY_FALLBACK.search(page)
        body = _clean_body(m.group(1)) if m else ""
        text = strip_html(body)
        image_only = len(text) < 50 and "<img" in body.lower()

        jobs.append({
            "id": f"dunamu-{nid}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            "title": title,
            # 사이트에 근무지가 없습니다. 본사 주소를 지어넣지 않습니다.
            "location": "",
            "career": career or "무관",
            # 게시일·마감일이 사이트에 없습니다. firstSeenAt 이 대신 쓰입니다.
            "postedAt": "",
            "closesAt": "",
            "dday": None,
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": url,
            "description": body if not image_only else "",
        })
        time.sleep(0.3)

    return jobs
