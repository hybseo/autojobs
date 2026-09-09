# -*- coding: utf-8 -*-
"""
더존ICT그룹(recruit.douzone.com) 수집기.

목록  GET https://recruit.douzone.com/api/rec-post/list?keyword=
상세  GET https://recruit.douzone.com/api/rec-post/detail?pblanc_no=..&pblanc_yy=..&company_cd=..
원문  https://recruit.douzone.com/post/{company_cd}/{pblanc_no}

인증은 필요 없습니다. 목록 한 번이면 끝납니다.

더존비즈온을 찾다가 여기까지 왔습니다
------------------------------------
www.douzone.com 의 채용 메뉴는 안내 페이지일 뿐이고, "채용공고 바로가기"
가 이 사이트로 넘깁니다. 더존비즈온 단독이 아니라 더존ICT그룹 통합
채용이라 그룹 어댑터로 만들었습니다.

company_cd 로 계열사가 구분됩니다(8000, K1000, T1000, 2000, E2000).
다만 이 코드가 어느 회사인지 알려주는 필드가 응답에 없습니다. 회사명을
지어낼 수 없으므로 companies.json 의 name 을 그대로 씁니다.
계열사별로 나누고 싶으면 코드와 회사명 대응을 먼저 확인해야 합니다.

함정 1 — 마감된 공고가 전부 섞여 옵니다
--------------------------------------
목록 API 는 접수중만 주지 않습니다. 2026-09-09 확인 시점에 176건이
왔는데 실제 진행중은 6건이었습니다. 나머지는 그해에 올렸다 마감된
공고입니다.

opbl_yn 은 176건 전부 "Y" 라 접수중 판별에 쓸 수 없습니다.
이름만 보면 게시여부 같은데 마감된 것도 Y 입니다. 믿지 마세요.

start_dt ~ end_dt 안에 오늘이 들어오는지로 걸러야 합니다.
아래 list_open() 이 그 일을 합니다. 이걸 빼면 6건이어야 할 목록이
176건으로 부풀어 오릅니다. 리크루터의 openStatus 함정과 같은 종류입니다.

함정 2 — 본문이 이미지입니다
----------------------------
rcrt_cntn_txt(본문) 필드가 목록에도 상세에도 빈 문자열로 옵니다.
공고 내용은 /api/rec-post/detail/img-list 가 주는 PNG 이미지입니다.
base64 로 인코딩된 파일이 통째로 들어오는데, 한 건에 1.4MB 였습니다.

이미지에서 글자를 읽어낼 방법이 없으므로 description 을 비우고 원문
링크로 보냅니다. 이미지 공고를 다루는 기존 방침과 같습니다.
multiRole 을 True 로 두어 화면에 "여러 직무 포함 가능" 배지를 붙입니다.

img-list 는 호출하지 않습니다. 쓸 수도 없는 1.4MB 를 공고마다 받아올
이유가 없습니다.

함정 3 — 인재풀 공고가 다수입니다
---------------------------------
2026-09-09 기준 진행중 6건 중 5건이 "인재Pool등록" 입니다. 실제 자리가
아니라 이력서를 미리 받아두는 창구입니다.

Ashby·네오위즈 어댑터는 이런 것을 기본 제외하지만, 여기서는 담습니다.
접수기간이 길어 사이트에서 자연히 상시채용으로 분류되고, 구직자에게도
"이 회사가 이 직군을 계속 뽑는다" 는 정보가 됩니다.

대신 제목만 보고 실제 공고로 착각하지 않도록 그대로 둡니다. 원문 제목에
이미 "(인재Pool등록)" 이 붙어 있어 화면에서 구분됩니다. 제외하고 싶으면
companies.json 에 "excludePool": true 를 넣으세요.

응답 구조 (2026-09-09 실제 확인)
--------------------------------
최상위가 배열입니다. 감싸는 객체가 없습니다.

    company_cd    8000            계열사 코드
    pblanc_no     REM2026048      공고 번호
    pblanc_yy     2026            공고 연도
    pblancsj_dc                   공고 제목
    hire_fg_cd    상시채용/수시채용  채용 구분
    start_dt      20260901        접수 시작. 구분자 없는 8자리
    end_dt        20260916        접수 마감
    workarea_cd   강촌(본사)       근무지
    rcrt_cntn_txt ""              본문. 항상 비어 있습니다
"""
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://recruit.douzone.com"
LIST_API = BASE + "/api/rec-post/list?keyword="
DETAIL = BASE + "/post/{}/{}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# 수집 날짜는 한국 시간 기준이어야 합니다.
# 깃허브 Actions 는 UTC 로 돕니다. 그냥 today() 를 쓰면 KST 오전 9시
# 이전 실행에서 하루 전 날짜로 걸러져 마감 당일 공고가 사라집니다.
KST = timezone(timedelta(hours=9))

# 이력서만 받아두는 창구. 기본으로는 담고, 빼고 싶을 때만 씁니다.
POOL = re.compile(r"인재\s*pool|talent\s*pool|인재\s*풀", re.I)


def _get(url):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다."""
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": BASE + "/post",
        "User-Agent": UA,
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


def _ymd(v):
    """'20260916' → '2026-09-16'. 구분자가 없습니다."""
    s = re.sub(r"\D", "", str(v or ""))
    if len(s) != 8:
        return ""
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


def _num(v):
    """비교용 정수. 못 읽으면 None."""
    s = re.sub(r"\D", "", str(v or ""))
    return int(s) if len(s) == 8 else None


def list_open(exclude_pool=False):
    """접수중 공고만 골라 돌려줍니다. probe 용으로 밖에서도 씁니다.

    목록 API 가 마감된 것까지 전부 주므로 접수기간으로 거릅니다.
    """
    rows = _get(LIST_API)
    if not isinstance(rows, list):
        print("  ! 더존: 응답이 배열이 아닙니다. "
              f"{LIST_API} 를 확인하세요.")
        return []
    if not rows:
        print(f"  ! 더존: 공고 목록이 비어 있습니다. {LIST_API} 를 확인하세요.")
        return []

    today = int(datetime.now(KST).strftime("%Y%m%d"))
    live = []
    for x in rows:
        sta, end = _num(x.get("start_dt")), _num(x.get("end_dt"))
        if sta is None or end is None:
            continue
        if sta <= today <= end:
            live.append(x)

    if exclude_pool:
        live = [x for x in live
                if not POOL.search(str(x.get("pblancsj_dc") or ""))]

    # 전체 중 몇 건이 살아 있는지 남깁니다. 이 비율이 갑자기 바뀌면
    # 날짜 필드 형식이 바뀐 것을 의심할 수 있습니다.
    print(f"  · 더존: 전체 {len(rows)}건 중 접수중 {len(live)}건")
    return live


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]

    rows = list_open(exclude_pool=bool(company.get("excludePool")))

    jobs = []
    for x in rows:
        no = (x.get("pblanc_no") or "").strip()
        cd = (x.get("company_cd") or "").strip()
        if not no:
            continue

        jobs.append({
            "id": f"douzone-{cd}-{no}",
            "unit": "공고",
            # company_cd 가 어느 계열사인지 알려주는 필드가 없습니다.
            # 지어내지 않고 등록한 이름을 씁니다.
            "company": name,
            "companySlug": slug,
            "title": (x.get("pblancsj_dc") or "").strip(),
            "location": (x.get("workarea_cd") or "").strip(),
            # 신입/경력을 구분해 주지 않습니다. hire_fg_cd 는
            # 상시채용/수시채용이라 경력 구분이 아닙니다.
            "career": "무관",
            "postedAt": _ymd(x.get("start_dt")),
            "closesAt": _ymd(x.get("end_dt")),
            "dday": None,
            # 본문이 이미지뿐이라 세부 직무를 읽을 수 없습니다.
            "multiRole": True,
            "sourceTitle": "",
            "sourceUrl": DETAIL.format(cd, no),
            # 본문이 PNG 이미지입니다. 글자를 읽을 수 없어 원문으로 보냅니다.
            "description": "",
        })

    return jobs
