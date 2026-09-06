# -*- coding: utf-8 -*-
"""
네이버 채용(recruit.navercorp.com) 수집기.

  목록  GET https://recruit.navercorp.com/rcrt/loadJobList.do
            ?annoId=&sw=&subJobCdArr=&sysCompanyCdArr=&empTypeCdArr=
            &entTypeCdArr=&workAreaCdArr=&firstIndex={0,10,20,...}
  상세  응답의 jobDetailLink 를 그대로 씁니다.

인증은 필요 없습니다. 화면이 스크롤할 때 부르는 것과 같은 경로입니다.

robots.txt (2026-09-08 확인)
---------------------------
recruit.navercorp.com/robots.txt 가 404 입니다. 규칙이 없으면 제한
없음이 표준 해석입니다. 한화(hanwhain.com)도 같은 경우였습니다.

참고로 카카오(careers.kakao.com)는 robots.txt 가 401 이라 규칙을
확인할 수 없어 수집하지 않기로 했습니다. 404 와 401 은 다릅니다.
404 는 "규칙이 없다", 401 은 "확인 불가" 입니다.

한 주소로 계열사가 다 나옵니다
------------------------------
처음에는 계열사마다 도메인이 따로 있는 줄 알고 일곱 곳을 각각 받으려
했습니다(recruit.navercloudcorp.com, recruit.snowcorp.com 등).
실제로는 이 한 주소에 전부 들어 있습니다.

  2026-09-08 기준 39건
    NAVER WEBTOON 26 · NAVER Cloud 8 · NAVER 3 · NAVER LABS 1 · SNOW 1

sysCompanyCdNm 에 계열사명이 들어오므로 그대로 회사명으로 씁니다.
"NAVER" 로 뭉치면 어느 계열사인지 알 수 없습니다.

페이지 넘김
-----------
firstIndex 를 10 씩 늘립니다. 응답의 totalSize 가 전체 건수입니다.

응답 구조 (2026-09-08 실제 확인)
--------------------------------
  { "result": "Y", "totalSize": 39, "list": [ ... ] }

  annoId          공고 번호
  sysCompanyCdNm  계열사명 "NAVER WEBTOON"
  annoSubject     제목 "[NAVER] 사내 변호사 (경력)"
  entTypeCdNm     경력 구분 "경력" / "신입" / "무관"
  empTypeCdNm     고용형태 "정규" / "계약" / "인턴"
  workAreaCd      근무지 코드
  staYmd, endYmd  접수 기간 "20260827" (구분자 없음)
  classCdNm       직군 "Corporate" / "Tech"
  subJobCdNm      직무 "법무"
  jobDetailLink   원문 주소
"""
import json
import re
import urllib.request

LIST = ("https://recruit.navercorp.com/rcrt/loadJobList.do"
        "?annoId=&sw=&subJobCdArr=&sysCompanyCdArr=&empTypeCdArr="
        "&entTypeCdArr=&workAreaCdArr=&firstIndex={}")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

PAGE = 10
MAX_PAGES = 40      # 안전장치. 400건이면 충분합니다.

# 화면 필터에서 확인한 대응입니다. 추측이 아닙니다.
AREA = {"0010": "분당", "0020": "서울", "0030": "춘천",
        "0040": "세종", "0050": "글로벌"}

# entTypeCdNm 이 한글로 그대로 옵니다. 표에 없으면 원문을 씁니다.
CAREER = {"경력": "경력", "신입": "신입", "무관": "무관",
          "신입/경력": "신입/경력", "인턴": "무관"}


def _get(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/json, text/javascript, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://recruit.navercorp.com/rcrt/list.do",
        "User-Agent": UA,
    })
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def _date(v):
    """'20260827' → '2026-08-27'. 구분자가 없습니다."""
    s = re.sub(r"\D", "", str(v or ""))
    if len(s) != 8:
        return ""
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


def list_open():
    """접수중 공고 목록. probe 용으로 밖에서도 씁니다."""
    rows, total = [], None
    for p in range(MAX_PAGES):
        j = _get(LIST.format(p * PAGE))
        got = j.get("list") or []
        if total is None:
            total = j.get("totalSize")
        rows += got
        if not got or (total is not None and len(rows) >= total):
            break

    if not rows:
        print("      ! 네이버: 공고 목록이 비어 있습니다. "
              f"{LIST.format(0)} 를 확인하세요.")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    slug = company["slug"]
    rows = list_open()

    # 계열사를 고르고 싶으면 companies.json 에 affiliates 를 적습니다.
    aff = company.get("affiliates") or []
    if aff:
        def norm(v):
            return re.sub(r"[\s\.,()/]", "", str(v or "")).lower()
        want = [norm(a) for a in aff]
        keep = [x for x in rows
                if any(w and w in norm(x.get("sysCompanyCdNm")) for w in want)]
        if not keep:
            seen = sorted({str(x.get("sysCompanyCdNm") or "?") for x in rows})
            print(f"      ! 네이버: 지정한 계열사 공고가 없습니다. "
                  f"받은 회사 {len(seen)}개: " + ", ".join(seen))
        rows = keep

    jobs = []
    for x in rows:
        aid = x.get("annoId")
        if not aid:
            continue
        # 직군·직무를 근무지 뒤에 붙이지 않습니다. location 은 근무지만.
        area = AREA.get(str(x.get("workAreaCd") or ""), "")
        ent = (x.get("entTypeCdNm") or "").strip()
        jobs.append({
            "id": f"naver-{aid}",
            "unit": "공고",
            # 계열사명을 그대로 씁니다. "NAVER" 로 뭉치면 어느 회사인지 모릅니다.
            "company": (x.get("sysCompanyCdNm") or company["name"]).strip(),
            "companySlug": slug,
            "title": (x.get("annoSubject") or "").strip(),
            "location": area,
            "career": CAREER.get(ent, ent or "무관"),
            "postedAt": _date(x.get("staYmd")),
            "closesAt": _date(x.get("endYmd")),
            "dday": None,
            "multiRole": (x.get("subJobCdCnt") or 0) > 1,
            "sourceTitle": "",
            "sourceUrl": (x.get("jobDetailLink")
                          or f"https://recruit.navercorp.com/rcrt/view.do?annoId={aid}"),
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })
    return jobs
