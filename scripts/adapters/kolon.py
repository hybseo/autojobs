# -*- coding: utf-8 -*-
"""
코오롱그룹(dream.kolon.com) 채용 수집기.

목록  POST https://dream.kolon.com/RECRUIT_KOLON/hr/rec/recruit/jobopen/
           controller/candidate/JobOpen310WebController/searchJobOpenByCandidate2018Renew.hr

코오롱인더스트리·코오롱생명과학·코오롱제약·코오롱베니트 등 계열사 공고가
한 곳에 모여 옵니다.

요청
----
본문을 빈 객체({})로 보내도 진행중 공고 전부가 옵니다. 쪽 나눔이 없습니다.
2026-09-22 기준 14건이었고 화면과 같았습니다.

응답
----
    resultData.totalcount   전체 수
    resultData.list         공고 배열

공고 한 건의 칸

    unit_nm            코오롱생명과학(주)          계열사
    jobopen_nm         [코오롱생명과학(주)] 의약QA 신입/경력 채용
    field_nm           품질보증(QA)                직무
    experience         01 신입 / 02 경력 / 03 신입·경력
    receive_start_dt   20260921                  접수 시작(YYYYMMDD)
    receive_end_dt     20260929                  접수 마감
    jobopen_id         KLS202609210002
    difend             -6                        남은 날(음수로 옵니다)

계열사 거르기
-------------
그룹 채용이라 건설·패션·모빌리티 공고도 함께 옵니다. companies.json 의
affiliates 에 적은 계열사만 담습니다. 비워 두면 전부 담습니다.

상세 주소
---------
개별 공고 페이지가 폼 전송으로 열려 주소로 바로 갈 수 없습니다. 모두
목록 페이지로 보냅니다. 없는 주소를 지어내지 않습니다.
"""
import html
import json
import re
import time
import urllib.error
import urllib.request

BASE = "https://dream.kolon.com/RECRUIT_KOLON/hr/rec/recruit"
LIST_API = BASE + "/jobopen/controller/candidate/JobOpen310WebController/searchJobOpenByCandidate2018Renew.hr"
LIST_PAGE = BASE + "/main/controller/candidate/MainRecruitWebController/init.hr"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# 경력 구분 코드. 화면 표시와 맞춰 확인한 값입니다(2026-09-22).
CAREER = {"01": "신입", "02": "경력", "03": "신입/경력"}

DATE = re.compile(r"^(\d{4})(\d{2})(\d{2})$")


def _post(body):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다."""
    req = urllib.request.Request(
        LIST_API, method="POST", data=json.dumps(body).encode(),
        headers={
            "User-Agent": UA,
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": LIST_PAGE,
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


def _text(s):
    s = re.sub(r"<[^>]+>", " ", str(s or ""))
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _date(v):
    """'20260921' → '2026-09-21'. 형식이 다르면 빈 문자열."""
    m = DATE.match(str(v or "").strip())
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def _career(row):
    code = str(row.get("experience") or "").strip()
    if code in CAREER:
        return CAREER[code]
    # 코드가 낯설면 제목에서 읽습니다. 그래도 모르면 무관입니다.
    t = _text(row.get("jobopen_nm"))
    has_new, has_exp = "신입" in t, "경력" in t
    if has_new and has_exp:
        return "신입/경력"
    if has_exp:
        return "경력"
    if has_new:
        return "신입"
    return "무관"


def _norm(s):
    return re.sub(r"[\s()（）㈜.,·-]|주식회사", "", str(s or "")).lower()


def list_open(code=""):
    """진행중 공고 목록. probe 용으로 밖에서도 씁니다."""
    j = _post({})
    data = j.get("resultData") or {}
    rows = data.get("list") or []
    if not rows:
        print(f"  ! 코오롱: 공고 목록이 비어 있습니다. "
              f"resultCode={j.get('resultCode')!r} {str(j.get('resultMsg') or '')[:40]}")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company.get("code"))

    # affiliates 에 적은 계열사만 담습니다.
    want = [_norm(a) for a in (company.get("affiliates") or []) if str(a).strip()]
    if want:
        before = len(rows)
        rows = [x for x in rows
                if any(w in _norm(x.get("unit_nm")) for w in want)]
        if before != len(rows):
            print(f"      · {name}: 계열사 거르기 {before}건 → {len(rows)}건")

    jobs = []
    for x in rows:
        no = str(x.get("jobopen_id") or "").strip()
        title = _text(x.get("jobopen_nm"))
        if not no or not title:
            continue

        # 제목에 직무가 없으면 뒤에 붙입니다. 어떤 자리인지 보이게 합니다.
        field = _text(x.get("field_nm"))
        if field and field not in title:
            title = f"{title} · {field}"

        jobs.append({
            "id": f"kolon-{re.sub(r'[^A-Za-z0-9]', '', no)[:24]}",
            "unit": "공고",
            "company": _text(x.get("unit_nm")) or name,
            "companySlug": slug,
            "title": title,
            # 목록에 근무지가 없습니다. 지어내지 않습니다.
            "location": "",
            "career": _career(x),
            "postedAt": _date(x.get("receive_start_dt")),
            "closesAt": _date(x.get("receive_end_dt")),
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            # 상세가 폼 전송이라 개별 주소가 없습니다. 목록으로 보냅니다.
            "sourceUrl": LIST_PAGE,
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })
    return jobs
