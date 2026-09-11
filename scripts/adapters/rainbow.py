# -*- coding: utf-8 -*-
"""
레인보우로보틱스(rainbow-robotics.com) 채용 수집기.

목록  GET https://rainbow-robotics.com/채용/채용공고/
상세  https://rainbow-robotics.com/채용/채용공고/?mod=document&uid={번호}

협동로봇·휴머노이드. 코스닥. 삼성전자가 최대주주입니다.

요청 한 번이면 끝납니다
-----------------------
워드프레스에 KBoard 게시판을 얹은 구조라 서버가 HTML 을 완성해서 보냅니다.
공고 제목·부서·요약·근무지·경력·고용형태가 모두 그 안에 들어 있어
상세 페이지를 따로 읽지 않습니다.

주소에 한글이 들어갑니다
------------------------
경로가 /채용/채용공고/ 입니다. 퍼센트 인코딩해서 보내야 합니다.
아래 LIST_URL 에 인코딩된 형태로 적어 두었습니다. 브라우저 주소창에서
복사하면 이미 인코딩된 상태로 나옵니다.

화면 텍스트만 보고 판단하지 마세요
----------------------------------
이 페이지는 get_page_text 같은 도구로 읽으면 맨 아래 FAQ("채용 관련 문의는
어디로 하면 되나요?")만 잡힙니다. 공고 표가 <article> 밖에 있기 때문입니다.

2026-09-11 에 그것만 보고 "공고 없음" 으로 잘못 판단했습니다. 실제로는
10건이 멀쩡히 있었습니다. 서버 HTML 을 직접 받아서 확인하세요.

목록 구조 (2026-09-11 확인)
---------------------------
    <tr>
      <td class="kboard-list-title rb-job-title-cell" data-label="직무명">
        <a class="rb-job-link" href="...?mod=document&uid=146">
          <span class="rb-job-title-text">로봇 AI 플랫폼 SW 개발</span>
          <span class="rb-job-department">SW개발</span>
          <span class="rb-job-summary">로봇 백엔드 개발</span>
        </a>
      </td>
      <td class="rb-job-meta-cell rb-job-location-cell">판교</td>
      <td class="... rb-job-type-cell">경력</td>
      <td class="... rb-job-employment-cell">정규직</td>
      <td class="... rb-job-deadline-cell">채용 시까지</td>
    </tr>

첫 번째 rb-job-deadline-cell 은 표 머리글("마감일")입니다. 공고가 아닙니다.
아래에서는 제목이 있는 행만 담으므로 자연히 걸러집니다.

마감일에 대하여
--------------
2026-09-11 기준 10건 모두 "채용 시까지" 였습니다. 날짜가 아니므로
closesAt 을 비웁니다. 비우면 사이트가 상시채용으로 표시합니다.

나중에 날짜가 적힌 공고가 생기면 _date() 가 알아서 읽습니다.

페이지 나눔이 없습니다
----------------------
?pageid=2 를 붙여도 1쪽과 똑같은 내용이 옵니다. 한 화면에 전부 나옵니다.
공고가 늘어 나뉘기 시작하면 그때 페이지 처리를 넣으세요.
"""
import html
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://rainbow-robotics.com"
# /채용/채용공고/ 를 퍼센트 인코딩한 것입니다.
LIST_PATH = "/%EC%B1%84%EC%9A%A9/%EC%B1%84%EC%9A%A9%EA%B3%B5%EA%B3%A0/"
LIST_URL = BASE + LIST_PATH

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

TITLE = re.compile(r'class="rb-job-title-text"[^>]*>(.*?)</span>', re.S | re.I)
DEPT = re.compile(r'class="rb-job-department"[^>]*>(.*?)</span>', re.S | re.I)
SUMMARY = re.compile(r'class="rb-job-summary"[^>]*>(.*?)</span>', re.S | re.I)
LINK = re.compile(r'href="([^"]*uid=(\d+)[^"]*)"', re.I)
LOC = re.compile(r'class="[^"]*rb-job-location-cell[^"]*"[^>]*>(.*?)</td>', re.S | re.I)
TYPE = re.compile(r'class="[^"]*rb-job-type-cell[^"]*"[^>]*>(.*?)</td>', re.S | re.I)
EMP = re.compile(r'class="[^"]*rb-job-employment-cell[^"]*"[^>]*>(.*?)</td>', re.S | re.I)
DEADLINE = re.compile(r'class="[^"]*rb-job-deadline-cell[^"]*"[^>]*>(.*?)</td>', re.S | re.I)

# rb-job-type-cell 값 → 사이트 career 표기.
CAREER = {"경력": "경력", "신입": "신입", "신입/경력": "신입/경력",
          "무관": "무관", "경력무관": "무관", "인턴": "무관"}


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
    """'2026.09.20' 또는 '2026-09-20' → '2026-09-20'.

    "채용 시까지" 처럼 날짜가 아니면 빈 문자열(상시채용)입니다.
    """
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", str(v or ""))
    if not m:
        return ""
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def list_open():
    """공고 목록. probe 용으로 밖에서도 씁니다."""
    page = _get(LIST_URL)
    # 공고 한 건이 rb-job-title-cell 로 시작합니다.
    blocks = page.split("rb-job-title-cell")[1:]

    rows, seen = [], set()
    for b in blocks:
        chunk = b[:2500]
        t = TITLE.search(chunk)
        if not t:
            # 표 머리글 등 제목 없는 조각은 공고가 아닙니다.
            continue
        title = _text(t.group(1))
        if not title:
            continue

        m = LINK.search(chunk)
        uid = m.group(2) if m else ""
        if uid and uid in seen:
            continue
        if uid:
            seen.add(uid)

        d = DEPT.search(chunk)
        s = SUMMARY.search(chunk)
        lo = LOC.search(chunk)
        ty = TYPE.search(chunk)
        em = EMP.search(chunk)
        dl = DEADLINE.search(chunk)

        rows.append({
            "uid": uid,
            "title": title,
            "dept": _text(d.group(1)) if d else "",
            "summary": _text(s.group(1)) if s else "",
            "location": _text(lo.group(1)) if lo else "",
            "type": _text(ty.group(1)) if ty else "",
            "employment": _text(em.group(1)) if em else "",
            "deadline": _text(dl.group(1)) if dl else "",
        })

    if not rows:
        # HTML 파싱이라 화면이 바뀌면 조용히 0건이 됩니다.
        print(f"  ! 레인보우로보틱스: 공고를 찾지 못했습니다. ({LIST_URL})")
        print(f"    받은 HTML {len(page)}자 · "
              f"'rb-job-title-cell' {page.count('rb-job-title-cell')}회 · "
              f"'rb-job-title-text' {page.count('rb-job-title-text')}회")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]

    rows = list_open()

    jobs = []
    for x in rows:
        # 부서를 제목 앞에 붙입니다. 어느 조직인지가 바로 보입니다.
        title = x["title"]
        if x["dept"] and x["dept"] not in title:
            title = f"[{x['dept']}] {title}"
        # 정규직이 아니면 표시합니다.
        emp = x["employment"]
        if emp and emp != "정규직" and emp not in title:
            title = f"{title} ({emp})"

        url = (f"{LIST_URL}?mod=document&uid={x['uid']}"
               if x["uid"] else LIST_URL)

        jobs.append({
            "id": f"rainbow-{x['uid']}" if x["uid"] else f"rainbow-{abs(hash(x['title'])) % 10**8}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            "title": title,
            "location": x["location"],
            "career": CAREER.get(x["type"], "무관"),
            # 게시일을 주지 않습니다.
            "postedAt": "",
            # "채용 시까지" 면 날짜가 아니라 빈 문자열이 됩니다(상시채용).
            "closesAt": _date(x["deadline"]),
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": url,
            # 목록에 한 줄 요약만 있고 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })

    return jobs
