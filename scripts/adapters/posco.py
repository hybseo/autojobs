# -*- coding: utf-8 -*-
"""
포스코그룹(recruit.posco.com) 채용 수집기.

목록  GET https://recruit.posco.com/h22a01-recruit/H22A1000/list?{파라미터}
상세  https://recruit.posco.com/h22a01-front/H22A1001.html?id={공고번호}

상세 주소를 지어내서 1년 가까이 전부 404 였습니다 (2026-10-12)
----------------------------------------------------------------
전에는 이렇게 적혀 있었습니다.

    H22A1010.html?noticeId={공고번호}

그럴듯해 보이지만 **확인하지 않고 지어낸 주소**였습니다. H22A1010.html
이라는 화면은 포스코 사이트에 아예 없습니다. 그래서 우리 사이트에서
포스코 공고를 누르면 전부 포스코 서버의 404 페이지로 갔습니다.

포스코 공고는 목록에 본문이 없어 description 이 빈 값입니다. 그래서
우리 상세 페이지를 만들지 않고 원문으로 바로 보냅니다. 즉 이 주소가
틀리면 포스코 공고는 하나도 열리지 않습니다. 사용자가 "클릭하면 404"
라고 알려주기 전까지 아무도 몰랐습니다.

맞는 주소는 목록 화면(H22A1000.html)이 줄을 그리는 자바스크립트에서
찾았습니다.

    "<td><a href='H22A1001.html?id=" + list[i].HR_AFTC_MRG_ADOP_NTIC_ID + "' ...

1000 이 목록, 1001 이 상세입니다. 공고번호 5건(707002·707004·715000·
719000·721001)으로 확인했습니다. 새 주소는 전부 200, 옛 주소는 전부
404 였습니다.

교훈: 주소 형식은 눈으로 확인한 것만 적습니다. 규칙을 유추해서
채우면 이렇게 조용히 망가집니다.

포스코·포스코DX·포스코퓨처엠·포스코인터내셔널 등 계열사 40곳 안팎의
공고가 한곳에 모여 옵니다. 2026-10-01 확인 16건이었습니다.

GET 입니다. POST 가 아닙니다
----------------------------
화면 코드(h22Common.submitAjax)가 POST 처럼 보이고 JSON 본문을 만드는
자리가 있어 POST 로 여러 번 시도했는데 전부 HTTP 500 이 났습니다.
실제로 목록을 부를 때는 GET 이고, 값은 본문이 아니라 주소 뒤에 붙습니다.
2026-09-22 에 이것을 못 찾아 어댑터를 포기했던 적이 있습니다.

    AJAX: true        헤더가 있어야 합니다. 없으면 화면 HTML 이 옵니다.

파라미터
--------
    rowCount, pageSize   한 번에 받을 건수. 100 을 넣으면 전부 옵니다
    currPage, offset     1, 0 고정
    SEARCH_ORDER         s1 (마감순)
    SEARCH_TYPE          빈 값 = 전체
    SEARCH_COMP          빈 값 = 전 계열사. 숫자를 넣으면 그 계열사만
    SEARCH_KEYWORD       빈 값
    SEARCH_VALUE         빈 값

응답
----
    recuList   공고 배열
    summary    상단 숫자(전체/신입/경력 등)

공고 한 건의 칸

    HR_AFTC_MRG_ADOP_NTIC_SUJX   2026년 포스코리튬솔루션(주) 경력직 채용(구매)
    COMPANY_NAME                 포스코리튬솔루션
    RECU_FIELD                   구매/계약
    HR_AFTC_MRG_ADOP_CLTA_TP_TP_NM  전문경력 / 신입 / 연봉계약직
    END_ACTIVE_DATE              2026.10.14
    DDAY                         13
    HR_AFTC_MRG_ADOP_NTIC_ID     707002
    TOT_CNT                      16          전체 건수

게시일은 상세에서 따로 읽습니다 (2026-10-12)
--------------------------------------------
목록에는 마감일만 있고 접수 시작일이 없습니다. 전에는 지어내지 않고
비워 뒀는데, 상세 API 에 들어 있는 것을 찾아 채우게 했습니다.
_posted_at 을 보세요. 공고가 10여 건뿐이라 요청이 늘어도 전체 갱신
시간에는 영향이 없습니다.

계열사 거르기
-------------
철강·소재·건설·IT 가 섞여 옵니다. companies.json 의 affiliates 를 적으면
그곳만 담습니다. 비워 두면 전부 담습니다.
"""
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://recruit.posco.com"
LIST_API = BASE + "/h22a01-recruit/H22A1000/list"
LIST_PAGE = BASE + "/h22a01-front/H22A1000.html"
# 공고 한 건의 상세. 접수 시작일이 여기에만 있습니다(_posted_at 참고).
FIND_API = BASE + "/h22a01-recruit/H22A1000/find"
VIEW = BASE + "/h22a01-front/H22A1001.html?id={}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

DATE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")


def _get(params):
    """목록을 받습니다. 일시적 실패만 몇 초 쉬었다 다시 시도합니다."""
    return _req(LIST_API + "?" + urllib.parse.urlencode(params))


def _req(url):
    """주소 하나를 불러 JSON 으로 돌려줍니다."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        # 이 헤더가 없으면 목록 JSON 대신 화면 HTML 이 옵니다.
        "AJAX": "true",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": LIST_PAGE,
    })
    last = None
    for i in range(2):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError:
            raise
        except Exception as e:
            last = e
            if i < 1:
                time.sleep(3)
    raise last


def _text(s):
    s = re.sub(r"<[^>]+>", " ", str(s or ""))
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _date(v):
    m = DATE.search(str(v or ""))
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""


def _posted_at(no):
    """공고 한 건의 접수 시작일을 상세에서 읽어옵니다.

    목록에는 접수 시작일이 없고 마감일만 있습니다. 상세를 한 번 더
    불러야 합니다. 2026-10-12 에 추가했습니다.

    상세 화면(H22A1001.html)의 HTML 에는 날짜가 없습니다. 화면이 뜬 뒤
    자바스크립트가 이 API 를 불러 채웁니다. 그래서 화면 HTML 을 긁는
    방법으로는 안 되고 API 를 직접 불러야 합니다.

        ACTIVE_DATE   2026-09-16(수) 15:00 ~ 2026-10-14(수) 23:59

    앞쪽이 접수 시작, 뒤쪽이 마감입니다. 공고 11건으로 형식이 일정한
    것을 확인했습니다.

    없는 공고번호를 넣으면 빈 값이 옵니다. 그때는 빈 문자열을
    돌려줍니다. 날짜를 지어내지 않습니다.

    실패해도 수집 전체를 멈추지 않습니다. 접수 시작일은 있으면 좋은
    정보이지, 없다고 공고를 버릴 이유는 아닙니다.
    """
    # 공고 수가 10여 건이라 전체 갱신 시간에 거의 영향이 없습니다.
    # 연달아 두드리지 않는 쪽이 예의라 짧게 쉽니다.
    time.sleep(0.3)
    try:
        j = _req(FIND_API + "?" + urllib.parse.urlencode({
            "GCS_COMP_CODE": "",
            "HR_AFTC_MRG_ADOP_NTIC_ID": no,
            "CURURL": "",
        }))
    except Exception as e:
        print(f"      · 포스코 {no}: 접수 시작일을 못 읽었습니다({type(e).__name__}). 비웁니다.")
        return ""

    # "시작 ~ 마감" 중 앞쪽만 씁니다. 물결이 없으면 통째로 넘겨도
    # _date 가 맨 앞 날짜를 집으므로 결과는 같습니다.
    return _date(str(j.get("ACTIVE_DATE") or "").split("~")[0])


def _career(row):
    """'전문경력' '신입' '연봉계약직' 같은 값이 옵니다."""
    t = _text(row.get("HR_AFTC_MRG_ADOP_CLTA_TP_TP_NM"))
    title = _text(row.get("HR_AFTC_MRG_ADOP_NTIC_SUJX"))
    both = f"{t} {title}"
    has_new = "신입" in both
    has_exp = "경력" in both
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
    params = {
        "rowCount": 100,
        "pageSize": 100,
        "currPage": 1,
        "offset": 0,
        "SEARCH_TYPE": "",
        "SEARCH_ORDER": "s1",
        "SEARCH_KEYWORD": "",
        "SEARCH_COMP": "",
        "SEARCH_VALUE": "",
    }
    data = _get(params)
    rows = data.get("recuList") or []
    if not rows:
        print(f"  ! 포스코: 공고 목록이 비어 있습니다. 이 API 는 POST 가 아니라 "
              f"GET 이고 AJAX 헤더가 필요합니다. {LIST_API}")
        return []

    total = int(rows[0].get("TOT_CNT") or len(rows))
    if total > len(rows):
        print(f"  · 포스코: 전체 {total}건 중 {len(rows)}건만 받았습니다. "
              f"rowCount 를 늘리세요")
    return rows



def _short_field(field):
    """모집분야를 제목 뒤에 붙일 만한 길이로 줄입니다.

    왜 필요한가 (2026-10-10)
    ------------------------
    RECU_FIELD 는 보통 "구매/계약" 처럼 짧습니다. 그래서 제목 뒤에
    붙이면 어떤 자리인지 한눈에 보여 도움이 됐습니다.

    그런데 한 공고가 수십 개 직무를 한꺼번에 뽑는 경우가 있습니다.
    포스코이앤씨 공고(707000)가 그랬습니다. 모집분야가 쉼표로 이어져
    제목이 223자가 됐고, 목록에서 카드 하나가 화면을 가득 메웠습니다.

        포스코이앤씨 경력직 / PJT전문직 채용 · 기술직-건축 기계,기술직-건축
        전기,기술직-건축 건축,특수직-변호사(국내),특수직-노무사,세무회계,
        포스코이앤씨-플랜트-원자력-영업, ... (계속)

    앞의 두 개만 보이고 나머지는 숫자로 접습니다. 구직자가 "여러 직무를
    한꺼번에 뽑는 공고구나" 를 알면 충분하고, 자세한 목록은 원문에 있습니다.

    자르지 않고 그대로 두면 안 되는 이유는 목록 화면이 망가지기 때문이고,
    아예 떼어버리면 안 되는 이유는 직무 한두 개짜리 공고가 훨씬 많아서
    그쪽 정보가 사라지기 때문입니다.
    """
    f = (field or "").strip()
    if not f:
        return ""
    parts = [x.strip() for x in f.split(",") if x.strip()]
    if len(parts) <= 2:
        return ", ".join(parts)
    return f"{parts[0]}, {parts[1]} 외 {len(parts) - 2}개"

def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company.get("code"))

    want = [_norm(a) for a in (company.get("affiliates") or []) if str(a).strip()]
    if want:
        before = len(rows)
        rows = [x for x in rows
                if any(w in _norm(x.get("COMPANY_NAME")) for w in want)]
        if before != len(rows):
            print(f"      · {name}: 계열사 거르기 {before}건 → {len(rows)}건")

    jobs = []
    for x in rows:
        no = str(x.get("HR_AFTC_MRG_ADOP_NTIC_ID") or "").strip()
        title = _text(x.get("HR_AFTC_MRG_ADOP_NTIC_SUJX"))
        if not no or not title:
            continue

        field = _short_field(_text(x.get("RECU_FIELD")))
        # 직무가 제목에 없으면 뒤에 붙입니다. 어떤 자리인지 보이게 합니다.
        if field and field not in title:
            title = f"{title} · {field}"

        jobs.append({
            "id": f"posco-{re.sub(r'[^0-9A-Za-z]', '', no)[:20]}",
            "unit": "공고",
            "company": _text(x.get("COMPANY_NAME")) or name,
            "companySlug": slug,
            "title": title,
            # 목록에 근무지가 없습니다. 지어내지 않습니다.
            "location": "",
            "career": _career(x),
            # 목록에는 없어서 상세를 한 번 더 읽습니다.
            "postedAt": _posted_at(no),
            "closesAt": _date(x.get("END_ACTIVE_DATE")),
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": VIEW.format(no),
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })
    return jobs
