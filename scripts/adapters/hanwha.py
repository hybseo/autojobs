# -*- coding: utf-8 -*-
"""
한화인(hanwhain.com) 수집기. 한화그룹 통합 채용 플랫폼입니다.

  목록  POST https://hwadm.hanwhain.com/new-backend/portal/api/rcRecruit/search-rcrt
  상세  https://www.hanwhain.com/portal/apply/recruit/detail?rtSeq={rtSeq}

인증 토큰은 필요 없습니다. 화면이 그대로 호출하는 경로이고, 로그인 없이
누구나 받는 공개 데이터입니다.

robots.txt (2026-09-01 확인)
---------------------------
www.hanwhain.com 과 hwadm.hanwhain.com 모두 robots.txt 가 없습니다.
규칙이 없으면 제한 없음이 표준 해석입니다.

다만 API 도메인 이름이 hwadm 입니다. admin 으로 읽히므로, 여기서는
목록 조회 경로(search-rcrt) 하나만 씁니다. 관리자 기능으로 보이는
다른 경로는 절대 요청하지 마세요. 공개 목록을 읽는 것과 관리 기능을
건드리는 것은 전혀 다른 일입니다.

계열사를 골라 담습니다
----------------------
한화그룹은 계열사가 40곳이 넘습니다. 금융·레저까지 있어 전부 받으면
사이트 성격이 완전히 흐려집니다. companies.json 의 "affiliates" 에
회사명을 적으면 그 계열사만 담습니다.

  "affiliates": ["한화로보틱스", "한화첨단소재", "한화모멘텀"]

부분 일치로 견줍니다. "한화" 라고만 적으면 전부 걸리니 계열사명을
끝까지 적으세요. HD현대 어댑터에서 같은 함정을 겪었습니다.

응답 구조 (2026-09-01 실제 확인)
--------------------------------
  sdNm             계열사명 "한화에어로스페이스"
  rtNm             공고 제목
  rtSeq            공고 번호
  rtAcptStrtDttm   접수 시작 "2026.08.18 15:00"
  rtAcptEndDttm    접수 마감 "2026.09.01 15:00"
  tagList          [{"rttgNm": "생산"}, ...] 근무지·직군이 섞여 옴
  filteredCount / totalCount / hasNext / page / size

목록에 본문이 없습니다
----------------------
제목·계열사·마감일만 옵니다. 그래서 description 을 비우고 원문 링크로
보냅니다. 상세 페이지도 자바스크립트로 그려서 본문을 읽기 어렵습니다.
잘못된 본문을 지어내느니 원문으로 보내는 편이 낫다는 판단이며,
이미지 공고를 다루는 방침과 같습니다.
"""
import json
import re
import urllib.request

LIST_URL = ("https://hwadm.hanwhain.com/new-backend/portal/api/"
            "rcRecruit/search-rcrt")
DETAIL = "https://www.hanwhain.com/portal/apply/recruit/detail?rtSeq={}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

PAGE = 20
MAX_PAGES = 30      # 안전장치. 600건이면 충분합니다.


def _post(page):
    body = {
        "langCd": "ko", "searchText": "",
        "sdSeqList": None, "djSeqList": None, "rjSeqList": None,
        "rtCarrYn": "", "rtIntnYn": "", "rtNrcrtYn": "",
        "rtPermanentWorkYn": "", "rtTempWorkYn": "",
        "page": page, "size": PAGE,
    }
    req = urllib.request.Request(
        LIST_URL, method="POST", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json",
                 "Referer": "https://www.hanwhain.com/",
                 "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def _date(v):
    """'2026.09.01 15:00' → '2026-09-01'. 값이 없으면 빈 문자열."""
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", str(v or ""))
    if not m:
        return ""
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def _tags(row):
    return [t.get("rttgNm") for t in (row.get("tagList") or [])
            if t.get("rttgNm")]


def list_open(affiliates=()):
    """접수중 공고 목록. probe 용으로 밖에서도 씁니다."""
    rows, page = [], 0
    while page < MAX_PAGES:
        j = _post(page)
        data = j.get("data") or {}
        got = data.get("list") or []
        rows += got
        if not data.get("hasNext") or not got:
            break
        page += 1

    if not rows:
        print("      ! 한화: 공고 목록이 비어 있습니다. "
              f"{LIST_URL} 를 확인하세요.")
        return []

    if not affiliates:
        return rows

    def norm(v):
        return re.sub(r"[\s\.,()/]", "", str(v or "")).lower()

    wanted = [norm(a) for a in affiliates]
    keep = [x for x in rows
            if any(w and w in norm(x.get("sdNm")) for w in wanted)]
    # 잡히긴 했는데 적을 때도 무엇이 있었는지 알면 계열사를 넓힐지 판단됩니다.
    if keep and len(keep) < 5:
        seen = sorted({str(x.get("sdNm") or "?") for x in rows})
        print(f"      · 한화: {len(keep)}건 수집. 전체 {len(rows)}건 중 "
              f"회사 {len(seen)}개가 있었습니다:")
        print("        " + ", ".join(seen))
    if not keep:
        # 목록을 자르면 찾는 회사가 뒤에 있을 때 알 수 없습니다.
        seen = sorted({str(x.get("sdNm") or "?") for x in rows})
        print(f"      ! 한화: 지정한 계열사 공고가 없습니다. "
              f"받은 회사 {len(seen)}개:")
        print("        " + ", ".join(seen))
    return keep


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    slug = company["slug"]
    rows = list_open(company.get("affiliates") or [])

    jobs = []
    for x in rows:
        seq = x.get("rtSeq")
        if not seq:
            continue
        tags = _tags(x)
        jobs.append({
            "id": f"hanwha-{seq}",
            "unit": "공고",
            # 계열사명을 그대로 씁니다. "한화" 로 뭉치면 어느 회사인지 모릅니다.
            "company": str(x.get("sdNm") or company["name"]),
            "companySlug": slug,
            "title": str(x.get("rtNm") or ""),
            # 근무지가 별도 필드로 오지 않습니다. 태그에 섞여 있지만
            # 어느 것이 지역인지 구분할 근거가 없어 비워둡니다.
            "location": "",
            # 신입/경력 구분도 목록에 없습니다. 지어내지 않습니다.
            "career": "무관",
            "postedAt": _date(x.get("rtAcptStrtDttm")),
            "closesAt": _date(x.get("rtAcptEndDttm")),
            "dday": None,
            # 태그가 여럿이면 여러 직무가 묶인 공고일 수 있습니다.
            "multiRole": len(tags) > 3,
            "sourceTitle": "",
            "sourceUrl": DETAIL.format(seq),
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })
    return jobs
