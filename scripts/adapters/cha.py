# -*- coding: utf-8 -*-
"""
차병원·차바이오그룹(recruit.chamc.co.kr) 채용 수집기.

목록  POST https://recruit.chamc.co.kr/recruit/announcement/recruitAnnouncementListMain.ckd
화면  https://recruit.chamc.co.kr/page.ckd#/main

예전에는 이 주소가 리크루터 구버전이었는데 자체 시스템으로 바뀌었습니다.
그래서 /app/jobnotice/list.json 이 404 가 나며 계속 실패했습니다
(2026-09-28 원인 확인).

요청
----
빈 본문({})으로 POST 하면 전체가 옵니다. GET 은 405 입니다. 쪽 나눔이
없어 한 번에 다 받습니다(2026-09-28 기준 45건).

응답
----
    recruitAnnouncementListMain   공고 배열

공고 한 건의 칸

    recrNm       차 여성의학연구소 잠실센터 수술간호사 채용 안내     제목
    psitnNm      차바이오텍                                  기관·회사
    recrTpNm     경력무관 / 신입 / 경력                        경력 구분
    rcritStaDt   2026-09-26 12:00                           접수 시작
    rcritEndDt   2026-10-11 23:50                           접수 마감
    closYn       N                                          마감 여부
    recrGrpId    RG20268893                                 공고 번호

병원 공고를 걸러야 합니다
-------------------------
차병원그룹이라 분당차병원·강남차병원 같은 의료기관 공고가 절반 넘게
옵니다. 간호사·의사 채용은 우리 사이트 산업과 맞지 않습니다.
companies.json 의 affiliates 에 담을 회사를 적습니다. 비워 두면 전부
담깁니다.

2026-09-28 기준 45건 중 차바이오텍 15건·마티카바이오랩스 4건이었고
나머지는 병원·연구소 공고였습니다.

상세 주소
---------
공고를 누르면 화면 안에서 열리고 주소가 #/main 그대로라, 주소로 바로
갈 수 있는 개별 페이지가 없습니다. 모두 목록으로 보냅니다.
"""
import html
import json
import re
import time
import urllib.error
import urllib.request

BASE = "https://recruit.chamc.co.kr"
LIST_API = BASE + "/recruit/announcement/recruitAnnouncementListMain.ckd"
LIST_PAGE = BASE + "/page.ckd#/main"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


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
    m = DATE.search(str(v or ""))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def _career(row):
    """recrTpNm 이 '경력무관' 이면 무관입니다."""
    t = _text(row.get("recrTpNm"))
    if "무관" in t:
        return "무관"
    both = f"{t} {_text(row.get('recrNm'))}"
    has_new, has_exp = "신입" in both, "경력" in both
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
    """마감되지 않은 공고 목록. probe 용으로 밖에서도 씁니다."""
    j = _post({})
    rows = j.get("recruitAnnouncementListMain") or []
    if not rows:
        print(f"  ! 차바이오: 공고 목록이 비어 있습니다. result={str(j.get('result'))[:40]}")
        return []
    return [x for x in rows if str(x.get("closYn") or "").upper() != "Y"]


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company.get("code"))

    # affiliates 에 적은 회사만 담습니다(병원 공고 제외).
    want = [_norm(a) for a in (company.get("affiliates") or []) if str(a).strip()]
    if want:
        before = len(rows)
        rows = [x for x in rows
                if any(w in _norm(x.get("psitnNm")) for w in want)]
        if before != len(rows):
            print(f"      · {name}: 담을 회사만 거릅니다 {before}건 → {len(rows)}건")

    jobs = []
    for x in rows:
        no = str(x.get("recrGrpId") or "").strip()
        title = _text(x.get("recrNm"))
        if not no or not title:
            continue

        jobs.append({
            "id": f"cha-{re.sub(r'[^A-Za-z0-9]', '', no)[:20]}",
            "unit": "공고",
            "company": _text(x.get("psitnNm")) or name,
            "companySlug": slug,
            "title": title,
            # 목록에 근무지가 없습니다. 지어내지 않습니다.
            "location": "",
            "career": _career(x),
            "postedAt": _date(x.get("rcritStaDt")),
            "closesAt": _date(x.get("rcritEndDt")),
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": LIST_PAGE,
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })
    return jobs
