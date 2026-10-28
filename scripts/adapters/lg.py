# -*- coding: utf-8 -*-
"""
LG Careers 수집기. LG 그룹 통합 채용 사이트입니다.

  목록  POST https://api.careers.lg.com/rmk/job/retrieveJobNoticesList
  상세  POST https://api.careers.lg.com/rmk/job/retrieveJobNoticesDetail

인증 토큰은 필요 없습니다.

robots.txt (2026-08-28 확인)
---------------------------
  User-agent: *
  Content-Signal: search=yes, ai-train=no, use=reference
  Allow: /
검색 색인 목적 수집이 명시적으로 허용돼 있습니다. AI 학습용 봇만 차단합니다.

지금까지의 어댑터와 다른 점
---------------------------
리크루터·그리팅은 기업 하나에 사이트 하나였습니다. LG 는 그룹 전체가 한 사이트를
쓰므로, companies.json 의 한 항목이 여러 계열사를 가리킬 수 있습니다.
code 에 계열사 코드를 쉼표로 적으면 그 계열사만 받아옵니다.

  "code": "LGE,LGIT,MAGNA,LGES"

이게 중요한 이유는, 전부 받으면 IT·통신·화학 공고까지 섞여 사이트 성격이
흐려지기 때문입니다. 자동차와 관련된 계열사만 골라 담습니다.

계열사 코드 (2026-08-28 확인)
  LGE   LG전자            LGIT  LG이노텍        MAGNA LG Magna
  LGES  LG에너지솔루션      LGC   LG화학          CNS   LG CNS
  LGU   LG유플러스         RBO   로보스타         BIZ   비즈테크아이
  HIM   하이엠솔루텍        SVO   D&O            GIIR  HSAD
  LGA   LG경영연구원        HIC   하이케어솔루션    TWB   TW바이오매스에너지

주의
----
- 회사명은 API 가 주는 계열사명을 씁니다. companies.json 의 name 이 아닙니다.
  한 항목이 여러 계열사를 담으므로, "LG그룹" 하나로 뭉뚱그리면 구직자가
  어느 회사 공고인지 알 수 없습니다.
- noticeStatus 가 POSTING 인 것만 접수중입니다.
- 마감일이 "2026.09.13 23:00" 형식입니다. 앞 10자를 잘라 하이픈으로 바꿉니다.
"""
import json
import re
import time
import html
import urllib.request

API = "https://api.careers.lg.com/rmk/job"
SITE = "https://careers.lg.com/apply/detail?id={}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# 실제 응답에서 확인한 값입니다. 추측하지 마세요.
# D 를 "무관" 으로 잘못 적어뒀다가 실제 데이터에서 "신입/경력" 인 것을 확인했습니다.
# 표에 없는 값은 API 가 주는 한글명을 쓰고, 그것도 없으면 "무관" 으로 접습니다.
CAREER = {"A": "신입", "B": "경력", "D": "신입/경력", "E": "산학장학생"}


def _career(x):
    code = x.get("careerTypeCode")
    if code in CAREER:
        return CAREER[code]
    return x.get("careerTypeName") or "무관"


def _post(path, body):
    req = urllib.request.Request(
        f"{API}/{path}", method="POST",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def _first_list(d):
    """응답 안에서 배열을 찾아냅니다. 키 이름이 바뀌어도 견디게 합니다."""
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        for v in d.values():
            if isinstance(v, list):
                return v
    return []


def list_open(codes=""):
    """접수중 공고 목록. codes 가 비면 그룹 전체입니다."""
    company_list = [c.strip() for c in (codes or "").split(",") if c.strip()]
    j = _post("retrieveJobNoticesList", {
        "lnbSearch": "", "hashTagText": "",
        "recDate": "CREATION_DATE", "order": "DESC",
        "careerList": [], "companyCodeList": company_list,
        "desireLocList": [], "jobGroupList": []})
    rows = _first_list(j.get("data"))
    # 게시중인 것만. 마감·대기 상태가 섞여 옵니다.
    return [x for x in rows if x.get("noticeStatus") == "POSTING"]


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def _date(s):
    """'2026.09.13 23:00' → '2026-09-13'. 값이 없으면 빈 문자열."""
    if not s:
        return ""
    return str(s)[:10].replace(".", "-")


def _to_html(text):
    """줄바꿈만 있는 평문을 문단으로 바꿉니다.

    LG API 는 본문을 HTML 이 아니라 평문으로 줍니다. 줄바꿈(\n)으로만
    구분돼 있는데, HTML 에서 줄바꿈은 공백으로 취급되므로 화면에서
    한 덩어리로 붙어 보입니다.

    실제로 "2027년 전기 연세대 이차전지융합공학과 신입생 모집" 공고가
    지원자격·접수방법·유의사항이 전부 한 문단으로 이어져 읽기
    어려웠습니다. 다른 어댑터(그리팅·리크루터·Ashby 등)는 HTML 을
    주므로 이 처리가 필요 없습니다.

    빈 줄이 있으면 문단을 나누고, 한 줄 줄바꿈은 <br> 로 둡니다.
    이미 HTML 이 섞여 있으면 건드리지 않습니다.
    """
    t = (text or "").strip()
    if not t:
        return ""
    if re.search(r"<(p|br|div|ul|li)\b", t, re.I):
        return t          # 이미 HTML 입니다.

    import html as _html
    blocks = re.split(r"\n\s*\n", t)
    out = []
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        lines = [_html.escape(x.strip()) for x in b.split("\n") if x.strip()]
        if lines:
            out.append("<p>" + "<br>".join(lines) + "</p>")
    return "\n".join(out)


def _sections(rec_list):
    """직무별 모집 내용을 본문으로 엮습니다 (2026-10-28 추가).

    왜 필요한가
    -----------
    예전에는 본문을 qualForAppInfo·recProcessInfo·otherInfo 세 칸으로
    만들었습니다. 그런데 그 세 칸은 전부 안내문입니다.

      qualForAppInfo  "해외여행 결격사유 없는 자, 병역필 또는 면제자"
      recProcessInfo  대부분 비어 있습니다
      otherInfo       "보훈대상자 우대, 허위기재 시 합격 취소"

    실제 모집 내용은 recList 에 직무별로 따로 들어 있는데 쓰지 않고
    있었습니다. LG유플러스 공고는 qualForAppInfo 에 아예
    "지원자격은 상세내역 참고" 라고 적어 두었습니다. 그 상세내역이
    recList 입니다.

    recList 한 항목에 들어 있는 것 (2026-10-28 확인)
      orgName        CTO
      jobGroupName   제품시뮬레이션
      locationName   서초R&D캠퍼스        ← 직무별 근무지
      detailContext  직무 소개
      mainTask       주요 업무
      requiredItem   자격 요건
      preferredItem  우대 사항

    한 공고에 여러 직무가 들어 있습니다. LG에너지솔루션 Pack/BMS 공고는
    7개, LG전자 R&D 해외유학생 공고는 6개입니다. 화면에서는 직무마다
    접힌 칸으로 나뉘어 있습니다.

    값은 평문이 아니라 HTML 로 옵니다. 그대로 이어 붙입니다.

    majorCodeName 과 numbers 는 담지 않습니다
    -----------------------------------------
    majorCodeName 에 화면 조각(<div class="MuiBox-root ...">)이 그대로
    들어오는 공고가 있고, numbers 는 "0" 이나 "-" 가 대부분이라
    쓸 수 있는 값이 아닙니다.
    """
    out = []
    for x in rec_list or []:
        if not isinstance(x, dict):
            continue
        chunk = []
        head = " ".join(w for w in (str(x.get("orgName") or "").strip(),
                                    str(x.get("jobGroupName") or "").strip()) if w)
        if head:
            chunk.append("<h3>" + html.escape(head) + "</h3>")
        loc = str(x.get("locationName") or "").strip()
        if loc:
            chunk.append("<p>근무지: " + html.escape(loc) + "</p>")
        body_added = False
        for label, key in (("직무 소개", "detailContext"),
                           ("주요 업무", "mainTask"),
                           ("자격 요건", "requiredItem"),
                           ("우대 사항", "preferredItem")):
            v = str(x.get(key) or "").strip()
            # 태그만 있고 글이 없는 칸이 있습니다(<p>-</p> 같은 것).
            if not v or len(strip_html(v)) < 2:
                continue
            chunk.append("<h4>" + label + "</h4>")
            chunk.append(v)
            body_added = True
        if body_added:
            out.append("\n".join(chunk))
    return "\n".join(out)


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    slug = company["slug"]
    rows = list_open(company.get("code", ""))

    jobs = []
    for x in rows:
        nid = x.get("jobNoticeId")
        if not nid:
            continue

        body = ""
        # 게시일은 상세 응답에만 있습니다 (2026-10-06 확인).
        #
        # 목록 API 응답에는 마감일(recEndDateTime)만 있고 게시일이 없어
        # postedAt 을 빈 값으로 두었는데, 그 때문에 LG 계열 125건이 구글
        # JobPosting 구조화 데이터에서 datePosted 누락으로 걸렸습니다.
        #
        # 상세 응답에는 recStartDate(접수 시작일)가 있습니다.
        #   data.jobNoticesDetail.jobNoticesDetail.recStartDate = "2026.10.09 09:00"
        # 본문을 받으려고 어차피 상세를 부르고 있어 요청이 늘지 않습니다.
        posted = ""
        place = ""
        roles = 0
        try:
            d = _post("retrieveJobNoticesDetail", {"jobNoticeId": nid})
            outer = (d.get("data") or {}).get("jobNoticesDetail") or {}
            det = outer.get("jobNoticesDetail") or outer
            rec = outer.get("recList") or []
            roles = len(rec)

            # 모집 내용은 recList 에 직무별로 들어 있습니다. _sections 설명 참고.
            body = _sections(rec)

            # 공통 지원자격은 뒤에 붙입니다. 병역·해외여행 결격 같은 내용이라
            # 길지 않고, 없는 공고도 있습니다. otherInfo 와 recProcessInfo 는
            # 순수 안내문이라 담지 않습니다.
            qual = str(det.get("qualForAppInfo") or "").strip()
            if qual and len(strip_html(qual)) > 2:
                qual = "<h4>공통 지원 자격</h4>\n" + qual
                body = (body + "\n" + qual) if body else qual

            posted = _date(det.get("recStartDate"))
            # 근무지가 상세에 있습니다. 예전에는 빈 값으로 두었습니다.
            #   "서초R&D캠퍼스, 대전기술연구원(제2캠퍼스)"
            place = str(det.get("workLocation") or "").strip()
        except Exception:
            body = ""

        text = strip_html(body)
        # 본문이 이미지 한 장뿐인 공고가 있습니다. 억지로 분해하지 않고 원문으로 보냅니다.
        image_only = len(text) < 50 and "<img" in body.lower()

        jobs.append({
            "id": f"lg-{nid}",
            "unit": "공고",
            # 계열사명을 그대로 씁니다. "LG그룹" 으로 뭉치면 어느 회사인지 알 수 없습니다.
            "company": x.get("companyName") or company["name"],
            "companySlug": slug,
            "title": x.get("jobNoticeName") or "",
            # 상세의 workLocation 입니다. 없으면 비워 둡니다. 지어내지 않습니다.
            "location": place,
            "career": _career(x),
            "postedAt": posted,
            "closesAt": _date(x.get("recEndDateTime")),
            "dday": x.get("recDateDiff"),
            # 본문이 이미지뿐이라 직무를 모르는 경우와, recList 에 직무가
            # 여럿 들어 있는 경우 둘 다 "여러 직무 포함 가능" 입니다.
            # LG전자 R&D 해외유학생 공고는 한 건에 직무가 6개입니다.
            "multiRole": image_only or roles > 1,
            "sourceTitle": "",
            "sourceUrl": SITE.format(nid),
            "description": _to_html(body) if not image_only else "",
        })
        time.sleep(0.3)

    return jobs
