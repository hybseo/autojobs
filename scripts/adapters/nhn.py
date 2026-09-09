# -*- coding: utf-8 -*-
"""
NHN Careers(careers.nhn.com) 수집기. NHN 그룹 통합 채용입니다.

목록  GET https://careers.nhn.com/v1/job-postings?page=0&size=200
상세  GET https://careers.nhn.com/v1/job-postings/{id}
원문  https://careers.nhn.com/recruits/{id}?type=list

인증은 필요 없습니다. 로그인이 필요한 것은 /v1/applicants/me 같은
마이페이지 경로뿐입니다.

함정 1 — Accept 헤더를 반드시 보내세요
--------------------------------------
이 API 는 Accept 헤더에 따라 형식이 바뀝니다. 브라우저 주소창으로 열면
XML(ApiResponse) 이 오고, Accept: application/json 을 주면 JSON 이 옵니다.

처음에는 XML 인 줄 알고 파서를 짜려 했는데, 헤더 하나로 JSON 이 되므로
그럴 이유가 없습니다. XML 파싱은 태그 구조가 조금만 바뀌어도 깨집니다.
아래에서 Accept 를 명시하는 이유입니다. 빼지 마세요.

함정 2 — 페이지가 0부터 시작합니다
----------------------------------
page=1 로 시작하면 두 번째 쪽부터 받게 되어 앞의 공고를 통째로 놓칩니다.
넥슨(page=1 시작)과 반대라 헷갈리기 쉽습니다.

함정 3 — 상시채용은 2999-12-31 로 옵니다
----------------------------------------
화면에 "채용시까지" 로 보이는 공고는 postingEndDatetime 이
2999-12-31T23:59:00 입니다. 그대로 closesAt 에 넣으면 화면에 엉뚱한
마감일이 찍힙니다. 2100년 이후는 마감 없음으로 봅니다.
넷마블 어댑터와 같은 처리입니다.

해외 법인을 제외합니다
----------------------
NHN JAPAN, NHN Cloud Japan 등 일본 법인 공고가 섞여 옵니다.
2026-09-09 기준 67건 중 4건이 그렇습니다. 국내 구직자용 사이트이므로
기본은 국내 법인만 담습니다. 해외까지 원하면 companies.json 에
"overseas": true 를 넣으세요. Ashby·Greenhouse 어댑터와 같은 방식입니다.

본문에 대하여
------------
상세 응답의 jobPostingContentsItems 가 섹션 배열입니다. 한 덩어리 HTML 이
아니라 이렇게 조각나 있습니다.

    { title: "이런 업무를 해요 (주요업무)",
      contentsTypeEnum: "LIST",
      contents: ["동행복권 통합복권 상담", "..."],
      footer: "<p>고객문의 인바운드 업무</p>" }

title 은 소제목, contents 는 항목 배열, footer 는 자유 HTML 입니다.
아래 _body() 가 이것을 하나의 HTML 로 조립합니다. orderNo 로 정렬해야
화면 순서와 같아집니다.

응답 구조 (2026-09-09 실제 확인)
--------------------------------
{ "header": {...}, "result": [ ... ], "paging": {"totalSize": 67, ...} }

    id                    공고 번호
    corporation.name      계열사명 "NHN Cloud"
    name                  공고 제목
    careerType.name       경력 구분 "경력"/"신입"/"무관"
    employeeType.name     고용형태 "정규"/"계약"
    postingStaDatetime    "2026-08-24T00:00:00"
    postingEndDatetime    "2026-09-09T23:59:00"
    finishYn / postingYn  마감 여부 / 게시 여부
    jobSeries[].jobGroup.name  직군
"""
import html
import json
import re
import time
import urllib.error
import urllib.request

BASE = "https://careers.nhn.com"
API = BASE + "/v1/job-postings"
SITE = BASE + "/recruits/{}?type=list"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

PAGE = 200
MAX_PAGES = 20  # 안전장치. 4,000건이면 충분합니다.

# careerType.name 이 한글로 그대로 옵니다. 표에 없으면 "무관" 으로 접습니다.
CAREER = {"경력": "경력", "신입": "신입", "무관": "무관",
          "신입/경력": "신입/경력", "인턴": "무관"}

# 해외 법인. 회사명에 이 말이 들어가면 국내가 아닙니다.
OVERSEAS = re.compile(r"japan|jp\b|china|global|america|usa", re.I)


def _get(url):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다. 4xx/5xx 는 재시도하지 않습니다."""
    req = urllib.request.Request(url, headers={
        # 이 헤더가 없으면 XML 이 옵니다. 빼지 마세요.
        "Accept": "application/json",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "User-Agent": UA,
    })
    last = None
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError:
            raise
        except Exception as e:
            last = e
            if i < 2:
                time.sleep(2 + i * 2)
    raise last


def _date(v):
    """'2026-09-09T23:59:00' → '2026-09-09'.

    2100년 이후는 상시채용을 뜻하는 가짜 날짜라 빈 문자열로 돌려줍니다.
    """
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(v or ""))
    if not m:
        return ""
    if int(m.group(1)) >= 2100:
        return ""
    return m.group(0)


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def _body(items):
    """섹션 조각을 하나의 HTML 로 조립합니다.

    한 항목은 소제목(title) + 항목 배열(contents) + 자유 HTML(footer) 입니다.
    orderNo 순으로 놓아야 화면과 같은 순서가 됩니다.
    """
    out = []
    for it in sorted(items or [], key=lambda x: float(x.get("orderNo") or 0)):
        title = (it.get("title") or "").strip()
        if title:
            out.append("<h3>" + html.escape(title) + "</h3>")

        lines = [str(c).strip() for c in (it.get("contents") or []) if str(c).strip()]
        if lines:
            if (it.get("contentsTypeEnum") or "").upper() == "LIST":
                out.append("<ul>" + "".join(
                    "<li>" + html.escape(x) + "</li>" for x in lines) + "</ul>")
            else:
                out += ["<p>" + html.escape(x) + "</p>" for x in lines]

        foot = (it.get("footer") or "").strip()
        if foot:
            # footer 는 이미 HTML 입니다. 그대로 둡니다.
            out.append(foot)
    return "\n".join(out)


def _is_korea(row):
    name = ((row.get("corporation") or {}).get("name") or "")
    return not OVERSEAS.search(name)


def list_open(overseas=False):
    """게시중인 공고 목록. probe 용으로 밖에서도 씁니다."""
    rows, page = [], 0
    while page < MAX_PAGES:
        j = _get(f"{API}?page={page}&size={PAGE}")
        got = j.get("result") or []
        rows += got
        total = ((j.get("paging") or {}).get("totalSize")) or 0
        if not got or len(rows) >= total:
            break
        page += 1
        time.sleep(0.3)

    if not rows:
        print(f"  ! NHN: 공고 목록이 비어 있습니다. {API} 를 확인하세요.")
        return []

    # 게시중이고 마감되지 않은 것만.
    rows = [x for x in rows
            if x.get("postingYn") != "N" and x.get("finishYn") != "Y"]

    if overseas:
        return rows

    kept = [x for x in rows if _is_korea(x)]
    if rows and not kept:
        seen = sorted({(x.get("corporation") or {}).get("name") or "?" for x in rows})
        print(f"  ! NHN: 국내 법인으로 인식된 공고가 없습니다. "
              f"받은 회사: {seen[:8]}")
    return kept


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    slug = company["slug"]
    rows = list_open(overseas=bool(company.get("overseas")))

    jobs = []
    for x in rows:
        pid = x.get("id")
        if not pid:
            continue

        raw = ""
        try:
            d = _get(f"{API}/{pid}")
            raw = _body((d.get("result") or {}).get("jobPostingContentsItems"))
        except Exception:
            raw = ""

        text = strip_html(raw)
        # 본문이 이미지뿐이면 세부 직무를 읽을 수 없습니다. 원문으로 보냅니다.
        image_only = len(text) < 50 and "<img" in raw.lower()

        career = ((x.get("careerType") or {}).get("name") or "").strip()
        jobs.append({
            "id": f"nhn-{pid}",
            "unit": "공고",
            # 계열사명을 그대로 씁니다. "NHN" 으로 뭉치면 어느 회사인지 모릅니다.
            "company": ((x.get("corporation") or {}).get("name")
                        or company["name"]).strip(),
            "companySlug": slug,
            "title": (x.get("name") or "").strip(),
            # 근무지를 주지 않습니다. 지어내지 않습니다.
            "location": "",
            "career": CAREER.get(career, "무관"),
            "postedAt": _date(x.get("postingStaDatetime")),
            # 2100년 이후는 _date 가 빈 문자열로 돌려줍니다(상시채용).
            "closesAt": _date(x.get("postingEndDatetime")),
            "dday": None,
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": SITE.format(pid),
            "description": raw if not image_only else "",
        })
        time.sleep(0.2)

    return jobs
