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
        try:
            d = _post("retrieveJobNoticesDetail", {"jobNoticeId": nid})
            det = (d.get("data") or {}).get("jobNoticesDetail") or {}
            det = det.get("jobNoticesDetail") or det
            # 자격요건이 본문의 핵심입니다. 전형절차·기타는 보조입니다.
            body = "\n".join(filter(None, [
                det.get("qualForAppInfo"),
                det.get("recProcessInfo"),
                det.get("otherInfo")]))
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
            "location": "",
            "career": _career(x),
            "postedAt": "",
            "closesAt": _date(x.get("recEndDateTime")),
            "dday": x.get("recDateDiff"),
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": SITE.format(nid),
            "description": body if not image_only else "",
        })
        time.sleep(0.3)

    return jobs
