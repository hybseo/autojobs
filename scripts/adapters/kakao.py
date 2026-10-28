# -*- coding: utf-8 -*-
"""
카카오(careers.kakao.com) 채용 수집기.

목록  GET https://careers.kakao.com/public/api/job-list?page={쪽}&company=ALL&part={직군}
상세  https://careers.kakao.com/jobs/{공고번호}

카카오와 공동체(계열사) 공고가 한 곳에 모여 옵니다. 2026-09-28 기준
카카오 26건·카카오모빌리티 21건·카카오페이 18건·카카오게임즈 3건·
카카오헬스케어 2건·카카오페이손해보험 2건이었습니다.

직군을 하나씩 불러야 합니다
---------------------------
이 API 는 직군(part)별로 나뉘어 있고, 값을 주지 않으면 테크 직군만
돌려줍니다. 화면에는 72건인데 그냥 부르면 35건만 옵니다.

    TECHNOLOGY         테크        35건
    BUSINESS_SERVICES  서비스·비즈  26건
    STAFF              스태프       8건
    DESIGN             디자인       3건

그래서 네 직군을 각각 부른 뒤 합칩니다. part=ALL 같은 값은 없습니다
(넣어도 테크만 옵니다). 공고 번호(realId)로 겹치는 것을 걸러냅니다.

company=ALL 을 빼면 카카오 본사 공고만 옵니다. 공동체까지 담으려면
꼭 넣어야 합니다.

쪽 나눔
-------
한 쪽에 15건입니다. size 를 키워도 무시하므로 totalJobCount 만큼
쪽을 넘깁니다.

본문
----
목록의 introduction 에 회사·직무 소개가 1,600자쯤 들어 있습니다.
workContentDesc·qualification 은 빈 값으로 와서 쓰지 않습니다.

계열사 거르기
-------------
companies.json 의 affiliates 에 적은 계열사만 담습니다. 비워 두면
전부 담습니다. 카카오게임즈는 자체 사이트(recruit.kakaogames.com)로
따로 수집하므로 여기서는 빼는 것이 좋습니다. 그러지 않으면 같은 공고가
두 번 올라옵니다.
"""
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://careers.kakao.com"
LIST = BASE + "/public/api/job-list?page={}&company=ALL&part={}"
VIEW = BASE + "/jobs/{}"

# 직군. 하나씩 부르지 않으면 테크만 옵니다.
PARTS = ("TECHNOLOGY", "BUSINESS_SERVICES", "STAFF", "DESIGN")
MAX_PAGE = 20

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _get(url):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": BASE + "/jobs",
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
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def _date(v):
    m = DATE.search(str(v or ""))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def _career(row):
    """직원유형과 제목에서 읽습니다. 없으면 무관. 지어내지 않습니다."""
    t = f"{_text(row.get('employeeTypeName'))} {_text(row.get('jobOfferTitle'))}"
    has_new = "신입" in t or "인턴" in t
    has_exp = "경력" in t
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
    """공고 목록. probe 용으로 밖에서도 씁니다."""
    rows, per_part = {}, []
    for part in PARTS:
        total, got = 0, 0
        for page in range(1, MAX_PAGE + 1):
            j = _get(LIST.format(page, part))
            total = int(j.get("totalJobCount") or 0)
            chunk = j.get("jobList") or []
            if not chunk:
                break
            for x in chunk:
                rid = str(x.get("realId") or "").strip()
                if rid:
                    rows[rid] = x          # 직군이 겹치면 한 번만 담깁니다
            got += len(chunk)
            if got >= total:
                break
            time.sleep(0.2)
        per_part.append(f"{part} {got}/{total}")

    if not rows:
        print("  ! 카카오: 공고를 받지 못했습니다. 직군별 결과: " + ", ".join(per_part))
    return list(rows.values())


DETAIL = BASE + "/public/api/job-detail?id={}"


def _detail(real_id):
    """공고 하나의 상세를 받습니다 (2026-10-28 추가).

    왜 필요한가
    -----------
    목록에는 introduction 만 채워져 옵니다. 그래서 예전에는 그것만
    썼습니다. 그런데 본사(P-) 공고는 introduction 이 팀 소개뿐이고
    업무와 자격은 다른 칸에 들어 있습니다.

      P-14559  introduction 616자(팀 소개) · workContentDesc 360자
               · qualification 935자
      P-13744  introduction 180자뿐 — 이대로는 요약을 쓸 수 없습니다

    공동체(S-) 공고는 introduction 안에 "◆ 조직소개 ◆ 업무내용" 이
    전부 들어 있어 예전 방식으로도 읽혔습니다. 그래서 본사 공고만
    내용이 부족했고, 2026-10-28 기준 73건 중 27건이 그랬습니다.

    상세에는 근무지(locationName)도 있습니다. 목록에는 없어서
    비워 두던 값입니다. 본사 공고는 "판교" 가 들어 있고, 공동체
    공고는 비어 있어 그때는 그대로 비웁니다.

    robots.txt (2026-10-28 확인)
      careers.kakao.com/robots.txt 는 HTTP 401 입니다. 규칙을 받지
      못하는 것이지 금지가 아니며, 2026-10-28 에 허용으로 보기로
      정했습니다. 목록 API 와 같은 호스트·같은 공개 경로입니다.

    실패하면 빈 dict 를 돌려줍니다. 그 공고만 예전처럼 둡니다.
    """
    try:
        d = _get(DETAIL.format(urllib.parse.quote(real_id)))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company.get("code"))

    # affiliates 에 적은 계열사만 담습니다.
    want = [_norm(a) for a in (company.get("affiliates") or []) if str(a).strip()]
    if want:
        before = len(rows)
        rows = [x for x in rows if _norm(x.get("companyName")) in want]
        if before != len(rows):
            print(f"      · {name}: 계열사 거르기 {before}건 → {len(rows)}건")

    jobs = []
    for x in rows:
        rid = str(x.get("realId") or "").strip()
        title = _text(x.get("jobOfferTitle"))
        if not rid or not title:
            continue

        # 마감된 공고는 담지 않습니다.
        if x.get("closeFlag") is True:
            continue

        # 상세에서 업무·자격·근무지를 받아 채웁니다. _detail 설명 참고.
        d = _detail(rid)
        place = _text(d.get("locationName"))
        parts = []
        for label, key in (("", "introduction"),
                           ("업무 내용", "workContentDesc"),
                           ("지원 자격", "qualification")):
            v = str(d.get(key) or x.get(key) or "").strip()
            # 태그만 있고 글이 없는 칸이 섞여 옵니다.
            if not v or len(_text(v)) < 2:
                continue
            if label:
                parts.append("<h4>" + label + "</h4>")
            parts.append(v)
        # 전형 안내(jobOfferProcessDesc)는 담지 않습니다. 안내문입니다.
        body = "\n".join(parts)
        if not parts:
            body = str(x.get("introduction") or "")

        jobs.append({
            "id": f"kakao-{re.sub(r'[^A-Za-z0-9]', '', rid)[:20]}",
            "unit": "공고",
            "company": _text(x.get("companyName")) or name,
            "companySlug": slug,
            "title": title,
            # 상세의 locationName 입니다. 공동체 공고는 비어 있어 그대로 둡니다.
            "location": place,
            "career": _career(x),
            "postedAt": _date(x.get("regDate")),
            # 상시채용은 마감일이 비어 옵니다. 그대로 비웁니다.
            "closesAt": _date(x.get("endDate")),
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": VIEW.format(rid),
            "description": body if len(_text(body)) >= 50 else "",
        })
        # 공고마다 상세를 한 번 더 받으므로 쉬어 갑니다.
        time.sleep(0.3)
    return jobs
