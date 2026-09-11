# -*- coding: utf-8 -*-
"""
리크루터(recruiter.co.kr) 구버전 수집기.

목록  GET https://{code}.recruiter.co.kr/app/jobnotice/list
상세  GET https://{code}.recruiter.co.kr/app/jobnotice/view?systemKindCode={종류}&jobnoticeSn={번호}

recruiter.py 와 무엇이 다른가
------------------------------
같은 회사(인크루트 리크루터)의 서비스인데 화면이 두 세대입니다.

    신버전  /career/home        api-recruiter.recruiter.co.kr 의 JSON API
    구버전  /app/jobnotice/list 서버가 그린 HTML

신버전용 어댑터(recruiter.py)로 구버전 회사를 부르면 400 이 떨어집니다.
회사가 신버전으로 옮기면 이 어댑터가 0건이 되니, 그때는 recruiter.py 로
바꾸고 code 만 옮기면 됩니다.

2026-09-11 확인 기준 구버전을 쓰는 곳
    효성그룹     hyosung    접수중 3건 (계열사 여럿)
    메디톡스      medytox    접수중 1건
    JW중외제약    jwholdings
    차바이오텍     chamc

목록 구조 (2026-09-11 효성 확인)
--------------------------------
    <div class="list-bbs with-tab">
      <ul>
        <li>
          <div class="list-bbs-type">공채</div>
          <h2 class="list-bbs-title">
            <a href="/app/jobnotice/view?..."
               data-jobnoticesn="265361"
               data-systemkindcode="MRS2">2026 하반기 효성그룹 신입·경력사원 채용</a>
          </h2>
          <span class="list-bbs-date">2026.09.07(월) 09:00 ~ 2026.09.20(일) 23:59</span>
          <span class="list-bbs-dday">D-9</span>
          <div class="list-bbs-status"><span class="text-label open">접수중</span></div>
        </li>

공고 번호는 href 를 파싱하지 말고 data-jobnoticesn 속성에서 꺼냅니다.
주소 형식이 바뀌어도 이 속성은 잘 안 바뀝니다.

함정 1 — 마감된 공고가 함께 옵니다
----------------------------------
2026-09-11 효성 기준 10건 중 접수중은 3건뿐이었고 나머지는 접수마감이었습니다.
text-label 의 글자가 "접수중" 인 것만 담습니다.

신버전의 submissionStatus 와 같은 역할입니다. 걸러내지 않으면 지난 공고가
진행중으로 올라갑니다.

함정 2 — 상세 주소에 값이 둘 필요합니다
---------------------------------------
jobnoticeSn 만으로는 상세 페이지가 열리지 않습니다. systemKindCode 도
함께 넘겨야 합니다. 회사마다 값이 다를 수 있어(효성은 MRS2) 목록에서
읽은 것을 그대로 씁니다. 고정값으로 박아두지 마세요.

본문에 대하여
------------
상세 페이지는 자바스크립트로 그려집니다. 서버가 주는 HTML 은 빈 껍데기라
(효성 기준 6,780자) 본문을 가져올 수 없었습니다. description 을 비우고
원문 링크로 보냅니다.

삼성·한화·NC 어댑터와 같은 방침입니다. 본문이 없으면 자체 상세 페이지와
JobPosting 스키마도 만들어지지 않습니다.

계열사에 대하여
--------------
효성처럼 그룹 통합 채용이면 계열사 공고가 섞여 옵니다. 회사 구분 필드가
없고 제목 앞 대괄호로만 표시되므로([효성티앤씨㈜] ...), 회사명은
companies.json 의 name 을 그대로 씁니다.
"""
import html
import re
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# 공고 한 덩어리. list-bbs 안의 <li> 입니다.
BLOCK = re.compile(r"<li[^>]*>(.*?)</li>", re.S | re.I)
# 공고 링크. 번호와 종류를 속성에서 꺼냅니다.
LINK = re.compile(
    r'<a[^>]*?data-jobnoticesn="(\d+)"[^>]*?data-systemkindcode="([^"]*)"[^>]*>(.*?)</a>',
    re.S | re.I)
# 속성 순서가 반대인 경우도 대비합니다.
LINK_ALT = re.compile(
    r'<a[^>]*?data-systemkindcode="([^"]*)"[^>]*?data-jobnoticesn="(\d+)"[^>]*>(.*?)</a>',
    re.S | re.I)
STATUS = re.compile(r'class="[^"]*text-label[^"]*"[^>]*>([^<]{0,12})<', re.I)
DATE = re.compile(r'class="[^"]*list-bbs-date[^"]*"[^>]*>(.*?)</', re.S | re.I)
DDAY = re.compile(r'class="[^"]*list-bbs-dday[^"]*"[^>]*>([^<]{0,12})<', re.I)
TYPE = re.compile(r'class="[^"]*list-bbs-type[^"]*"[^>]*>([^<]{0,20})<', re.I)

# list-bbs-type 값 → 사이트 career 표기.
CAREER = {"신입": "신입", "경력": "경력", "신입/경력": "신입/경력",
          "경력무관": "무관", "무관": "무관", "공채": "신입/경력",
          "상시채용": "무관", "인턴": "무관"}


def _base(code):
    c = (code or "").strip().rstrip("/")
    if not c:
        raise RuntimeError(
            "recruiter_v1: code 가 비어 있습니다. "
            "채용 사이트 앞자리를 적으세요. 예: hyosung")
    if c.startswith("http"):
        return c
    if "." in c:
        return "https://" + c
    return f"https://{c}.recruiter.co.kr"


def _get(url):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Upgrade-Insecure-Requests": "1",
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


def _dates(v):
    """'2026.09.07(월) 09:00 ~ 2026.09.20(일) 23:59' → 두 날짜."""
    got = re.findall(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", str(v or ""))
    out = [f"{y}-{int(m):02d}-{int(d):02d}" for y, m, d in got[:2]]
    while len(out) < 2:
        out.append("")
    return out[0], out[1]


def _dday(v):
    """'D-9' → 9. 부호를 그대로 읽으면 음수가 되어 마감으로 취급됩니다."""
    t = str(v or "").strip()
    if not t:
        return None
    if re.search(r"오늘|D-?DAY", t, re.I):
        return 0
    m = re.search(r"\d+", t)
    return int(m.group(0)) if m else None


def list_open(code):
    """접수중 공고만 골라 돌려줍니다. probe 용으로 밖에서도 씁니다."""
    base = _base(code)
    url = base + "/app/jobnotice/list"
    page = _get(url)

    rows, closed = [], 0
    for chunk in BLOCK.findall(page):
        m = LINK.search(chunk)
        if m:
            sn, kind, title_html = m.group(1), m.group(2), m.group(3)
        else:
            m = LINK_ALT.search(chunk)
            if not m:
                continue
            kind, sn, title_html = m.group(1), m.group(2), m.group(3)

        st = STATUS.search(chunk)
        state = _text(st.group(1)) if st else ""
        # 마감된 공고가 함께 옵니다. 접수중만 담습니다.
        if state and state != "접수중":
            closed += 1
            continue

        title = _text(title_html)
        if not title:
            continue

        d = DATE.search(chunk)
        start, end = _dates(_text(d.group(1)) if d else "")
        t = TYPE.search(chunk)
        dd = DDAY.search(chunk)

        rows.append({
            "sn": sn,
            "kind": kind,
            "title": title,
            "type": _text(t.group(1)) if t else "",
            "start": start,
            "end": end,
            "dday": _dday(dd.group(1) if dd else ""),
            "url": (f"{base}/app/jobnotice/view"
                    f"?systemKindCode={urllib.parse.quote(kind)}&jobnoticeSn={sn}"),
        })

    if not rows:
        # HTML 파싱이라 화면이 바뀌면 조용히 0건이 됩니다.
        print(f"  ! recruiter_v1({code}): 접수중 공고를 찾지 못했습니다. ({url})")
        print(f"    받은 HTML {len(page)}자 · "
              f"'list-bbs' {page.count('list-bbs')}회 · "
              f"'data-jobnoticesn' {page.count('data-jobnoticesn')}회 · "
              f"마감으로 걸러진 것 {closed}건")
        print(f"    신버전으로 옮겼다면 recruiter 어댑터를 쓰세요.")
    elif closed:
        print(f"  · recruiter_v1({code}): 접수중 {len(rows)}건 (마감 {closed}건 제외)")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    code = company["code"]

    rows = list_open(code)

    jobs = []
    for x in rows:
        jobs.append({
            "id": f"recruiterv1-{slug}-{x['sn']}",
            "unit": "공고",
            # 계열사 구분 필드가 없습니다. 등록한 이름을 씁니다.
            "company": name,
            "companySlug": slug,
            "title": x["title"],
            # 근무지를 목록에 주지 않습니다. 지어내지 않습니다.
            "location": "",
            "career": CAREER.get(x["type"], "무관"),
            "postedAt": x["start"],
            "closesAt": x["end"],
            "dday": x["dday"],
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": x["url"],
            # 상세가 자바스크립트로 그려져 본문을 가져올 수 없습니다. 원문으로 보냅니다.
            "description": "",
        })

    return jobs
