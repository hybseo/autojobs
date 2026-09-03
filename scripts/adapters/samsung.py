# -*- coding: utf-8 -*-
"""
삼성 채용(samsungcareers.com) 수집기. 삼성그룹 통합 채용 플랫폼입니다.

  목록  POST https://www.samsungcareers.com/hr/list.data
        currentPageNo=1&intNo=0&strVal=&strTxt=&strKey=
        &strCompany=&strType=&strOrderBy=&strEntity=
  상세  https://www.samsungcareers.com/hr/?no={공고번호}

인증 토큰은 필요 없습니다.

robots.txt (2026-09-03 확인)
---------------------------
robots.txt 가 없습니다. 규칙이 없으면 제한 없음이 표준 해석입니다.

사이트에 reCAPTCHA 가 붙어 있지만 로그인·지원서 제출 쪽입니다.
목록 조회(list.data)는 인증 없이 응답합니다. 지원 관련 경로는
절대 건드리지 마세요. 우리가 쓰는 것은 공개 목록 하나뿐입니다.

응답이 JSON 이 아니라 HTML 입니다
---------------------------------
JSON 이 아니라 화면에 그대로 꽂을 <li> 조각을 돌려줍니다.
그래서 HTML 을 파싱합니다. 화면 개편에 약하므로, 공고를 하나도
찾지 못하면 조용히 0건이 되지 않고 무엇을 받았는지 남깁니다.

한 항목의 생김새 (2026-09-03 확인)
  <button class="btnShare" data-value="22,945">      ← 공고 번호(쉼표 포함)
  <p class="company">  삼성전기</p>
  <h3 class="title">경력사원 채용(인덕터ㆍ탄탈ㆍSi-Cap 개발) </h3>
  <span> 경력 </span>
  <span class="period">2026.09.03 ~ 2026.09.07</span>
  <span class="flag blue">D- 4</span>
  <span class="flag grey">인덕터 제품 개발</span>  ← 직무 태그. 여러 개

계열사를 골라 담습니다
----------------------
삼성은 전자·반도체·바이오·금융·서비스까지 걸쳐 있습니다. 전부 받으면
사이트 성격이 흐려집니다. companies.json 의 "affiliates" 에 회사명을
적으면 그 계열사만 담습니다.

  "affiliates": ["삼성전기", "삼성SDI", "삼성디스플레이"]

부분 일치로 견줍니다. "삼성" 이라고만 적으면 전부 걸리니 계열사명을
끝까지 적으세요. HD현대·한화 어댑터에서 같은 함정을 겪었습니다.

한계
----
- 상세 페이지도 자바스크립트로 그려 본문을 읽을 수 없습니다.
  description 을 비우고 원문 링크로 보냅니다. 잘못된 본문을
  지어내느니 원문으로 보내는 편이 낫다는 판단입니다.
- 삼성전자·삼성SDS 등은 자체 채용 경로를 따로 쓰기도 합니다.
  여기서 안 잡히는 계열사가 있을 수 있습니다.
"""
import re
import html as html_mod
import urllib.parse
import urllib.request

LIST_URL = "https://www.samsungcareers.com/hr/list.data"
DETAIL = "https://www.samsungcareers.com/hr/?no={}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

PAGE_MAX = 20      # 안전장치. 페이지가 이보다 많을 리 없습니다.

# 한 공고 덩어리. <li> 단위로 자릅니다.
ITEM = re.compile(r"<li>(.*?)</li>", re.S)
NUM = re.compile(r'class="btnShare"[^>]*data-value="([\d,]+)"')
COMPANY = re.compile(r'class="company"[^>]*>(.*?)</p>', re.S)
TITLE = re.compile(r'class="title"[^>]*>(.*?)</h3>', re.S)
PERIOD = re.compile(r'class="period"[^>]*>(.*?)</span>', re.S)
DDAY = re.compile(r'class="flag blue"[^>]*>\s*D-\s*(\d+)', re.S)
TAG = re.compile(r'class="flag grey"[^>]*>(.*?)</span>', re.S)
MAXPAGE = re.compile(r'class="divCnt"[^>]*data-max="(\d+)"')

CAREER = {"경력": "경력", "신입": "신입", "인턴": "무관", "신입/경력": "신입/경력"}


def _post(page):
    body = urllib.parse.urlencode({
        "currentPageNo": str(page), "intNo": "0", "strVal": "", "strTxt": "",
        "strKey": "", "strCompany": "", "strType": "", "strOrderBy": "",
        "strEntity": "",
    }).encode()
    req = urllib.request.Request(LIST_URL, method="POST", data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "*/*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.samsungcareers.com/hr/",
        "User-Agent": UA,
    })
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def _txt(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html_mod.unescape(s)).strip()


def _one(chunk):
    """<li> 하나에서 필요한 값을 꺼냅니다. 공고가 아니면 None."""
    m = NUM.search(chunk)
    co = COMPANY.search(chunk)
    ti = TITLE.search(chunk)
    if not (m and co and ti):
        return None
    no = m.group(1).replace(",", "")      # 22,945 → 22945
    period = _txt(PERIOD.search(chunk).group(1)) if PERIOD.search(chunk) else ""
    dates = re.findall(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", period)
    fmt = lambda t: f"{t[0]}-{int(t[1]):02d}-{int(t[2]):02d}"
    dd = DDAY.search(chunk)
    # 경력 구분은 period 앞의 <span> 에 있습니다. 태그를 걷어내고 찾습니다.
    plain = _txt(chunk)
    career = next((v for k, v in CAREER.items() if k in plain), "무관")
    return {
        "no": no,
        "company": _txt(co.group(1)),
        "title": _txt(ti.group(1)),
        "start": fmt(dates[0]) if len(dates) > 0 else "",
        "end": fmt(dates[1]) if len(dates) > 1 else "",
        "dday": int(dd.group(1)) if dd else None,
        "career": career,
        "tags": [_txt(t) for t in TAG.findall(chunk)],
    }


def list_open(affiliates=()):
    """접수중 공고 목록. probe 용으로 밖에서도 씁니다."""
    rows, page, last = [], 1, ""
    while page <= PAGE_MAX:
        raw = _post(page)
        last = raw
        got = [x for x in (_one(c) for c in ITEM.findall(raw)) if x]
        rows += got
        mx = MAXPAGE.search(raw)
        if not got or not mx or page >= int(mx.group(1)):
            break
        page += 1

    if not rows:
        # HTML 파싱이라 화면이 바뀌면 조용히 0건이 됩니다.
        # "구조가 바뀌었다" 는 말만으로는 무엇을 고칠지 알 수 없습니다.
        print("      ! 삼성: 공고를 하나도 찾지 못했습니다.")
        print(f"        받은 HTML {len(last)}자 · "
              f"company {last.count('class=\"company\"')}회 · "
              f"title {last.count('class=\"title\"')}회")
        print("        앞부분: " + last[:220].replace("\n", " "))
        return []

    if not affiliates:
        return rows

    def norm(v):
        return re.sub(r"[\s\.,()/]", "", str(v or "")).lower()

    wanted = [norm(a) for a in affiliates]
    keep = [x for x in rows if any(w and w in norm(x["company"]) for w in wanted)]
    if not keep:
        seen = sorted({x["company"] for x in rows})
        print(f"      ! 삼성: 지정한 계열사 공고가 없습니다. "
              f"받은 회사 {len(seen)}개: " + ", ".join(seen))
    return keep


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    slug = company["slug"]
    rows = list_open(company.get("affiliates") or [])

    jobs = []
    for x in rows:
        jobs.append({
            "id": f"samsung-{x['no']}",
            "unit": "공고",
            # 계열사명을 그대로 씁니다. "삼성" 으로 뭉치면 어느 회사인지 모릅니다.
            "company": x["company"] or company["name"],
            "companySlug": slug,
            "title": x["title"],
            # 근무지가 목록에 없습니다. 지어내지 않습니다.
            "location": "",
            "career": x["career"],
            "postedAt": x["start"],
            "closesAt": x["end"],
            "dday": x["dday"],
            # 직무 태그가 여럿이면 여러 직무를 묶은 공고입니다.
            "multiRole": len(x["tags"]) > 3,
            "sourceTitle": "",
            "sourceUrl": DETAIL.format(x["no"]),
            # 상세도 자바스크립트로 그려 본문을 읽을 수 없습니다. 원문으로 보냅니다.
            "description": "",
        })
    return jobs
