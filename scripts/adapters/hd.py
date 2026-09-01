# -*- coding: utf-8 -*-
"""
HD현대 그룹 통합 채용 수집기.

  목록  GET https://recruit.hd.com/api/v1/jobda/getRecruitNoticeList?isPost=true&LANG=KR
  상세  https://recruit.hd.com/kr/mainLayout/applyDetail/{recruitNoticeSn}

인증 토큰은 필요 없습니다. 목록 한 번으로 본문까지 함께 옵니다.
요청이 공고 수와 무관하게 1회라 상대 서버 부담이 가장 적습니다.

robots.txt (2026-09-01 확인)
---------------------------
  User-agent: *
  Disallow: /hdcareerAdministrator/
  Allow: /

관리자 경로만 막혀 있고 나머지는 허용입니다. 여기서 쓰는
/api/v1/jobda/ 와 /kr/mainLayout/applyDetail/ 은 해당되지 않습니다.
관리자 경로는 절대 요청하지 마세요.

주소에 jobda 가 들어갑니다. 마이다스인의 잡다(JOBDA) 시스템을 쓴다는 뜻이라,
같은 시스템을 쓰는 다른 회사에도 이 구조가 통할 수 있습니다.

계열사를 골라 담습니다
----------------------
HD현대는 조선·해양·건설기계·에너지까지 폭이 넓습니다. 전부 받으면
사이트 성격이 흐려집니다. companies.json 의 "affiliates" 에 회사명을
적으면 그 계열사 공고만 담습니다.

  "affiliates": ["HD현대로보틱스", "HD현대인프라코어"]

비워두면 전부 받습니다. LG·SK 어댑터와 같은 방식입니다.

주의: 부분 일치로 견줍니다. "HD현대" 라고만 적으면 HD현대로보틱스·
HD현대인프라코어까지 전부 걸립니다. 계열사명을 끝까지 적으세요.

응답 구조 (2026-09-01 실제 확인)
--------------------------------
  recruitNoticeSn      공고 번호
  recruitNoticeName    공고 제목
  recruitClassName     경력 구분 ("경력", "신입" 등)
  companyCategory      "HD현대그룹"
  receiveStartDatetime 접수 시작 "2024-07-02 00:00:00"
  receiveEndDatetime   접수 마감 "2024-08-13 13:30:59"
  contents             본문 HTML
  isPost               게시 여부
  recruitSectorList    모집 분야 배열. 각 항목에 companyName, area, job

계열사명과 근무지는 목록이 아니라 recruitSectorList 안에 있습니다.
한 공고에 여러 계열사가 묶이는 경우가 있어 첫 항목만 쓰지 않고 모두 봅니다.
"""
import json
import re
import html
import urllib.request

LIST_URL = ("https://recruit.hd.com/api/v1/jobda/getRecruitNoticeList"
            "?isPost=true&LANG=KR")
DETAIL = "https://recruit.hd.com/kr/mainLayout/applyDetail/{}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# recruitClassName 이 한글로 그대로 옵니다. 표에 없으면 원문을 씁니다.
CAREER = {"경력": "경력", "신입": "신입", "신입/경력": "신입/경력",
          "인턴": "무관", "무관": "무관"}


def _get(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/json", "User-Agent": UA,
        "Referer": "https://recruit.hd.com/"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def _date(v):
    """'2024-08-13 13:30:59' → '2024-08-13'. 값이 없으면 빈 문자열."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", str(v or ""))
    return m.group(1) if m else ""


def _sectors(row):
    return row.get("recruitSectorList") or []


def _companies(row):
    """공고에 묶인 계열사명. 한 공고에 여러 곳이 붙기도 합니다."""
    out = []
    for s in _sectors(row):
        n = (s.get("companyName") or "").strip()
        if n and n not in out:
            out.append(n)
    return out


def _areas(row):
    out = []
    for s in _sectors(row):
        a = (s.get("area") or "").strip()
        if a and a not in out:
            out.append(a)
    if not out:
        return ""
    return out[0] if len(out) == 1 else f"{out[0]} 외 {len(out) - 1}곳"


def list_open(affiliates=()):
    """게시중인 공고 목록. probe 용으로 밖에서도 씁니다."""
    j = _get(LIST_URL)
    rows = j.get("data") or []
    rows = [x for x in rows if x.get("isPost") is not False]

    if not affiliates:
        return rows

    def norm(v):
        return re.sub(r"[\s\.,()]", "", str(v or "")).lower()

    wanted = [norm(a) for a in affiliates]
    keep = [x for x in rows
            if any(w and any(w in norm(c) for c in _companies(x))
                   for w in wanted)]
    if rows and not keep:
        # 목록을 자르면 찾는 회사가 뒤에 있을 때 알 수 없습니다.
        seen = sorted({c for x in rows for c in _companies(x)})
        print(f"      ! HD현대: 지정한 계열사 공고가 없습니다. "
              f"받은 회사 {len(seen)}개:")
        print("        " + ", ".join(seen))
    return keep


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    slug = company["slug"]
    rows = list_open(company.get("affiliates") or [])

    jobs = []
    for x in rows:
        sn = x.get("recruitNoticeSn")
        if not sn:
            continue
        body = x.get("contents") or ""
        text = strip_html(body)
        image_only = len(text) < 50 and "<img" in body.lower()

        cos = _companies(x)
        # 계열사명을 그대로 씁니다. "HD현대" 로 뭉치면 어느 회사인지 모릅니다.
        name = cos[0] if len(cos) == 1 else (
            f"{cos[0]} 외 {len(cos) - 1}곳" if cos else company["name"])

        cls = (x.get("recruitClassName") or "").strip()
        jobs.append({
            "id": f"hd-{sn}",
            "unit": "공고",
            "company": name, "companySlug": slug,
            "title": x.get("recruitNoticeName") or "",
            "location": _areas(x),
            "career": CAREER.get(cls, cls or "무관"),
            "postedAt": _date(x.get("receiveStartDatetime")),
            "closesAt": _date(x.get("receiveEndDatetime")),
            "dday": None,
            "multiRole": image_only or len(cos) > 1,
            "sourceTitle": "",
            "sourceUrl": DETAIL.format(sn),
            "description": body if not image_only else "",
        })
    return jobs
