# -*- coding: utf-8 -*-
"""
인크루트 '리크루터' ATS 수집기.
국내 자동차부품 대기업 다수가 이걸 씁니다.

  목록  POST https://api-recruiter.recruiter.co.kr/position/v1/jobflex
  상세  GET  https://api-recruiter.recruiter.co.kr/position/v2/jobflex/{positionSn}

인증 토큰은 필요 없습니다. 대신 함정이 두 개 있으니 반드시 지킬 것.

함정 1 — prefix 헤더
  없으면 무조건 500 입니다. 기업 식별자 역할을 합니다.

함정 2 — 접수중 판별
  submissionStatus == "IN_SUBMISSION" 인 것만 접수중입니다.
  openStatus 는 접수중을 뜻하지 않습니다. 마감된 지 수백 일 지난 공고도 OPEN 입니다.
  이걸 잘못 쓰면 33건이어야 할 목록이 365건으로 부풀어 오릅니다.
  아래에서 서버 필터와 파이썬 필터를 이중으로 거는 이유입니다.
"""
import json
import time
import html
import re
import urllib.request

API = "https://api-recruiter.recruiter.co.kr"

# API 가 주는 careerType → 화면 표기.
# 표에 없는 값이 그대로 새어 나가면 구직자 화면에 "NONE" 같은 영문이 필터로 뜹니다.
# 실제로 그런 일이 있었습니다. 모르는 값은 아래 _career() 에서 "무관" 으로 접습니다.
CAREER = {"CAREER": "경력", "NEW": "신입", "NEW_CAREER": "신입/경력",
          "ANY": "무관", "FIELD_DIFFERENCE": "분야별상이",
          "NONE": "무관"}


def _career(v):
    """모르는 값이나 빈 값은 '무관' 으로 봅니다. 조건을 안 정한 공고입니다."""
    return CAREER.get(v, "무관")


def _host(prefix):
    """prefix 헤더에 넣을 호스트.

    리크루터는 자체 도메인을 붙일 수 있습니다. 그 경우 헤더에도 그 도메인을
    그대로 넣어야 합니다. 회사 코드만 넣으면 HTTP 400 이 옵니다.
    실제로 파두(careers.fadu.io)·고려아연(careers.koreazinc.co.kr) 등
    네 곳이 그래서 실패했습니다.

    companies.json 에 "domain" 을 적으면 그 값을 씁니다.
      "code": "fadu", "domain": "careers.fadu.io"
    """
    p = (prefix or "").strip()
    if "." in p:                      # 이미 도메인 형태면 그대로
        return p.replace("https://", "").replace("http://", "").rstrip("/")
    return f"{p}.recruiter.co.kr"


def _post(path, prefix, body):
    req = urllib.request.Request(
        API + path, method="POST",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "prefix": _host(prefix)})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _get(path, prefix):
    req = urllib.request.Request(
        API + path, headers={"prefix": _host(prefix)})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def list_open(prefix):
    """접수중 공고 목록. probe 용으로 밖에서도 씁니다."""
    out, page = [], 1
    while page <= 10:
        j = _post("/position/v1/jobflex", prefix, {
            "pageableRq": {"page": page, "size": 100, "sort": ["END_DATE_TIME"]},
            "filter": {"keyword": "", "tagSnList": [], "jobGroupSnList": [],
                       "careerTypeList": [], "regionSnList": [],
                       "submissionStatusList": ["IN_SUBMISSION"],
                       "openStatusList": [], "resumeLanguageTypeList": []}})
        out += [x for x in j.get("list", []) if x.get("submissionStatus") == "IN_SUBMISSION"]
        pg = j.get("pagination") or {}
        if page >= pg.get("totalPages", 1):
            break
        page += 1
        time.sleep(0.3)
    return out


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    # 자체 도메인이 있으면 그것을 씁니다. 없으면 code 로 조립합니다.
    prefix = (company.get("domain") or "").strip() or company["code"]

    rows = list_open(prefix)

    jobs, seen = [], {}
    for x in rows:
        sn = x["positionSn"]
        key = f"{prefix}-{sn}"
        seen[key] = seen.get(key, 0) + 1
        jid = key if seen[key] == 1 else f"{key}-{seen[key]}"

        try:
            d = _get(f"/position/v2/jobflex/{sn}", prefix)
            raw = d.get("jobDescription") or ""
        except Exception:
            raw = ""

        text = strip_html(raw)
        # 본문이 이미지 한 장뿐인 공고는 세부 직무를 읽을 수 없습니다.
        # 억지로 분해하지 않고 원문으로 보냅니다.
        image_only = len(text) < 50 and "<img" in raw.lower()

        jobs.append({
            "id": jid,
            "unit": "공고",
            "company": name, "companySlug": slug,
            "title": x["title"],
            "location": "",
            "career": _career(x.get("careerType")),
            "postedAt": (x.get("startDateTime") or "")[:10],
            "closesAt": (x.get("endDateTime") or "")[:10],
            "dday": x.get("dday"),
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": f"https://{prefix}.recruiter.co.kr/career/jobs/{sn}",
            # 본문이 있으면 상세 페이지와 JobPosting 스키마가 생성됩니다.
            "description": raw if not image_only else "",
        })
        time.sleep(0.2)

    return jobs
