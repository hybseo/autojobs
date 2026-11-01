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

목록에 본문이 없습니다 — 상세를 한 번 더 받습니다 (2026-11-01 고침)
--------------------------------------------------------------
목록은 제목·계열사·마감일만 줍니다. 예전에는 그래서 description 을 비우고
원문 링크로만 보냈습니다. 상세 페이지가 자바스크립트로 그려져 본문을
읽을 수 없다고 적어두었는데, 틀린 판단이었습니다.

상세 페이지가 화면을 그릴 때 부르는 경로가 따로 있습니다. 목록과 같은
공개 경로이고 토큰도 로그인도 필요 없습니다. 브라우저로 직접 확인했습니다.

  상세  POST https://hwadm.hanwhain.com/new-backend/portal/api/rcRecruit/get-rcrt
        본문 {"rtSeq": 20065}

응답의 data.item 안에 모집단위 배열이 있고, 여기에 본문이 들어 있습니다.

  rtNm         공고 제목
  unitDt[]     모집단위. 공고 하나에 여러 직무가 들어가는 구조입니다
    ruNm         모집단위명      "구매/물류 시스템 PI 담당자"
    ruDtlJob     세부업무·자격요건·우대사항이 한 덩어리로 (HTML)
    ruWorkpl     근무지역        "서울"
    ruRcrtPrsn   계획인원

이 경로 덕분에 56건이 본문 없이 나가던 문제가 풀렸습니다. 다만
**ruDtlJob 이 비어 있는 공고가 실제로 있습니다.** 한화오션 공고 10여 건이
그렇고, 화면에서도 모집단위가 아예 그려지지 않습니다. 직접 확인했습니다.
없는 것을 지어내지 않고 그대로 빈 본문으로 둡니다.

hwadm 이 admin 으로 읽히는 문제는 위에 적은 대로입니다. get-rcrt 역시
화면이 그대로 부르는 조회 경로라 search-rcrt 와 성격이 같습니다.
목록·상세 이 둘 말고는 어떤 경로도 부르지 마세요.
"""
import json
import re
import time
import urllib.request

LIST_URL = ("https://hwadm.hanwhain.com/new-backend/portal/api/"
            "rcRecruit/search-rcrt")
DETAIL_API = ("https://hwadm.hanwhain.com/new-backend/portal/api/"
              "rcRecruit/get-rcrt")
DETAIL = "https://www.hanwhain.com/portal/apply/recruit/detail?rtSeq={}"

# 공고 하나마다 상세를 한 번 더 받습니다. 사이에 쉬는 시간입니다.
DETAIL_GAP = 0.3

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
    # 2026-09-08 갱신에서 timed out 으로 실패해 17건이 통째로 빠졌습니다.
    # 같은 주소를 브라우저로 부르면 73건이 정상으로 왔습니다.
    # 서버가 가끔 느린 것이라 몇 초 쉬었다 다시 걸어봅니다.
    last = None
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception as e:
            last = e
            if i < 2:
                time.sleep(3 + i * 3)
    raise last


def _detail(seq):
    """공고 하나의 상세를 받습니다. 실패하면 None 입니다.

    한 건이 실패해도 그 공고만 본문 없이 두고 넘어갑니다. 전체 수집이
    멈추는 편이 훨씬 나쁩니다.
    """
    req = urllib.request.Request(
        DETAIL_API, method="POST",
        data=json.dumps({"rtSeq": int(seq)}).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json",
                 "Referer": "https://www.hanwhain.com/",
                 "User-Agent": UA})
    for i in range(2):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                j = json.load(r)
            return ((j.get("data") or {}).get("item")) or None
        except Exception:
            if i == 0:
                time.sleep(2)
    return None


def _body(item):
    """모집단위들을 하나의 본문 HTML 로 엮습니다.

    모집단위마다 이름·근무지·세부내용이 있습니다. 세부내용이 하나도
    없으면 빈 문자열을 돌려줍니다. 제목만 있는 껍데기 본문을 만들면
    상세 페이지와 JobPosting 스키마가 내용 없이 생성되어 더 나쁩니다.
    """
    units = (item or {}).get("unitDt") or []
    parts, has = [], False
    for u in units:
        job = str(u.get("ruDtlJob") or "").strip()
        if not re.sub(r"<[^>]*>", "", job).strip():
            continue
        has = True
        name = str(u.get("ruNm") or "").strip()
        place = str(u.get("ruWorkpl") or "").strip()
        head = name + (f" ({place})" if place else "")
        if head:
            parts.append(f"<h3>{head}</h3>")
        parts.append(job)
    return "\n".join(parts) if has else ""


def _place(item):
    """모집단위의 근무지역 칸. 공고가 준 값이라 추측이 아닙니다.

    단위마다 근무지가 다르면 합쳐 적습니다. 셋을 넘으면 비워둡니다.
    "서울 / 판교 / 구미 / 창원" 은 근무지로서 뜻이 없습니다.
    """
    units = (item or {}).get("unitDt") or []
    seen = []
    for u in units:
        p = str(u.get("ruWorkpl") or "").strip()
        if p and p not in seen:
            seen.append(p)
    if not seen or len(seen) > 3:
        return ""
    return " / ".join(seen)


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
        # 상세를 한 번 더 받아 본문과 근무지를 채웁니다. 자세한 사정은
        # 파일 맨 위 "목록에 본문이 없습니다" 설명을 보세요.
        item = _detail(seq)
        time.sleep(DETAIL_GAP)
        jobs.append({
            "id": f"hanwha-{seq}",
            "unit": "공고",
            # 계열사명을 그대로 씁니다. "한화" 로 뭉치면 어느 회사인지 모릅니다.
            "company": str(x.get("sdNm") or company["name"]),
            "companySlug": slug,
            "title": str(x.get("rtNm") or ""),
            # 모집단위의 근무지역 칸입니다. 목록에는 없고 상세에만 있습니다.
            "location": _place(item),
            # 신입/경력 구분도 목록에 없습니다. 지어내지 않습니다.
            "career": "무관",
            "postedAt": _date(x.get("rtAcptStrtDttm")),
            "closesAt": _date(x.get("rtAcptEndDttm")),
            "dday": None,
            # 태그가 여럿이면 여러 직무가 묶인 공고일 수 있습니다.
            "multiRole": len(tags) > 3,
            "sourceTitle": "",
            "sourceUrl": DETAIL.format(seq),
            # 상세에서 받은 본문입니다. 세부내용이 없는 공고는 빈 문자열이
            # 되고, 그때는 예전처럼 원문 링크로만 보냅니다.
            "description": _body(item),
        })

    got = sum(1 for j in jobs if j["description"])
    if jobs:
        print(f"      · 한화: {len(jobs)}건 중 본문 {got}건")
    return jobs
