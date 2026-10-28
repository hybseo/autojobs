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

본문은 상세 페이지에서 받습니다 (2026-10-28 추가)
------------------------------------------------
목록(loadJobList.do)에는 본문이 없습니다. 예전에는 그래서 비워 두고
원문 링크로 보냈습니다. 그런데 상세 페이지(view.do)는 서버가 HTML 을
다 그려서 보내므로 그대로 읽을 수 있습니다. 자바스크립트가 필요 없습니다.

  2026-10-28 annoId 30005625 확인
    원본 HTML 109,882자 · 본문 글자 5,234자
    <div class="detail_box"> 가 5개이고, 각각이 공고의 한 단락입니다
      0 조직 소개      308자
      1 담당 업무      485자
      2 필요 역량      544자
      3 우대 사항      520자
      4 전형 절차 및 안내 사항  1,306자

그래서 detail_box 를 전부 모아 본문으로 씁니다. 화면에 보이는 순서가
그대로 유지됩니다. 전형 절차는 요약 단계에서 걸러냅니다.

detail_box 가 하나도 없으면 구조가 바뀐 것입니다. 그때는 본문을
비우고 넘어갑니다. 엉뚱한 글을 본문으로 넣지 않습니다.
"""
import json
import re
import time
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


# 본문 단락을 감싼 태그. 여는 태그만 찾고, 다음 여는 태그까지를 한 단락으로
# 봅니다. 닫는 </div> 를 세어 짝을 맞추려 하면 안쪽에 div 가 중첩돼 있어
# 어긋납니다.
DETAIL_BOX = re.compile(r'<div[^>]*class="[^"]*\bdetail_box\b[^"]*"[^>]*>', re.I)

# 단락 끝을 알리는 태그.
#
# 마지막 단락(전형 절차) 뒤에는 지원 버튼과 바닥글이 이어집니다.
# 2026-10-28 annoId 30005625 에서 실제로 확인한 순서입니다.
#   <div class="detail_box">  전형 절차 …
#   <script>                  화면 스크립트
#   <div class="half_detail_box">   빈 레이아웃
#   <footer class="footer">   약관·개인정보 처리방침·관련 사이트
#
# 바닥글이 <footer> 요소라서, div 의 class 만 보던 식으로는 안 걸렸습니다.
# 그래서 요소 이름으로도 끊습니다.
TAIL = re.compile(
    r'<footer\b'
    r'|<div[^>]*class="[^"]*\b(?:btn_area|relate_site|apply_area'
    r'|half_detail_box|family_list|site_list)\b', re.I)

# 스크립트·스타일은 미리 지웁니다. 안 지우면 전형 절차 단락에 jQuery
# 코드가 본문으로 섞여 들어옵니다(실제로 그랬습니다).
SCRIPT = re.compile(r"<(script|style)\b[^>]*>[\s\S]*?</\1>", re.I)

VIEW = "https://recruit.navercorp.com/rcrt/view.do?annoId={}"


def _html(url):
    req = urllib.request.Request(url, headers={
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://recruit.navercorp.com/rcrt/list.do",
        "User-Agent": UA,
    })
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def _body(anno_id):
    """상세 페이지에서 본문 단락들을 모아 돌려줍니다.

    실패하거나 단락을 못 찾으면 빈 문자열입니다. 그때는 예전처럼
    원문 링크로 보냅니다. 엉뚱한 글을 본문으로 넣지 않습니다.
    """
    try:
        page = _html(VIEW.format(anno_id))
    except Exception:
        return ""

    page = SCRIPT.sub(" ", page)
    starts = [m.end() for m in DETAIL_BOX.finditer(page)]
    if not starts:
        return ""

    parts = []
    for i, s in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(page)
        seg = page[s:end]
        # 마지막 단락 뒤에는 버튼·관련 사이트가 붙습니다. 거기서 끊습니다.
        cut = TAIL.search(seg)
        if cut:
            seg = seg[:cut.start()]
        seg = seg.strip()
        if seg:
            parts.append(seg)
    return "\n".join(parts)


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
    bodies = 0
    for x in rows:
        aid = x.get("annoId")
        if not aid:
            continue
        # 직군·직무를 근무지 뒤에 붙이지 않습니다. location 은 근무지만.
        area = AREA.get(str(x.get("workAreaCd") or ""), "")
        ent = (x.get("entTypeCdNm") or "").strip()
        raw = _body(aid)
        if raw:
            bodies += 1
        time.sleep(0.3)
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
            "sourceUrl": (x.get("jobDetailLink") or VIEW.format(aid)),
            # 상세 페이지에서 받아옵니다. 못 받으면 비우고 원문으로 보냅니다.
            "description": raw,
        })
    if bodies:
        print(f"      · 본문 {bodies}건 수집")
    return jobs
