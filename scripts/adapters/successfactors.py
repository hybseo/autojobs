# -*- coding: utf-8 -*-
"""
SAP SuccessFactors(RMK) 채용 사이트 수집기.

목록  GET https://{domain}/search/?q=&startrow=0
상세  GET https://{domain}/job/{제목슬러그}/{공고번호}/

SAP 의 대형 ATS 라 국내 대기업이 여럿 씁니다. LS전선이 이걸 씁니다.
companies.json 에 "code" 로 도메인만 적으면 다른 회사에도 그대로 씁니다.

    "ats": "successfactors", "code": "careers.lscablebiz.com"

Workday 와 헷갈리지 마세요
--------------------------
이 저장소에는 비슷한 이름이 셋 있습니다. 전부 다른 시스템입니다.

    successfactors  *.com/search/          SAP. 이 파일
    workday         *.myworkdayjobs.com    외국계 대기업
    workable        apply.workable.com     스타트업

공개 API 가 없습니다
--------------------
JSON 을 주는 경로가 따로 없어 검색 화면 HTML 을 읽습니다. 화면이 바뀌면
0건이 되므로, 아무것도 못 찾으면 무엇을 받았는지 남깁니다.

목록 구조 (2026-09-10 LS전선 확인)
----------------------------------
    <li class="job-tile">
      <a class="jobTitle-link" href="/job/{슬러그}/{번호}/">공고 제목</a>
      <span class="section-label">회사</span>
      <span class="section-field">회사 LS전선</span>
      <span class="section-label">부서</span> ...
    </li>

주의 1 — a.jobTitle-link 를 세면 안 됩니다
2026-09-10 기준 공고는 7건인데 이 링크는 21개였습니다. 데스크톱용과
모바일용 마크업이 겹쳐 있어 같은 공고가 여러 번 나옵니다.
li.job-tile 단위로 세야 정확합니다. 그래도 혹시 모르니 아래에서
공고 번호로 한 번 더 걸러냅니다.

주의 2 — section-field 에 항목명이 섞여 옵니다
값만 들어 있지 않고 "회사\n\n LS전선" 처럼 앞에 항목명이 붙어 옵니다.
앞의 라벨을 떼어내야 실제 값이 됩니다.

주의 3 — 항목 이름은 회사마다 다릅니다
LS전선은 회사 / 부서 / 지역 / 직원유형 입니다. 다른 회사는 이름도
개수도 다를 수 있습니다. 순서에 기대지 말고 라벨로 찾습니다.
모르는 라벨은 그냥 버립니다.

날짜에 대하여
------------
목록에도 상세에도 접수 마감일이 없습니다. 지어내지 않고 비웁니다.
비우면 사이트가 상시채용으로 표시합니다.

경력 구분에 대하여
------------------
신입/경력을 따로 주지 않습니다. 다만 제목에 "경력 채용", "신입"
같은 말이 들어가는 경우가 많아 그때만 읽습니다. 없으면 무관입니다.

본문에 대하여
------------
상세 페이지의 class="jobdescription" 안에 본문이 있습니다.
LS전선은 안내문만 짧게 적힌 공고가 섞여 있는데(예: "외부 전용 페이지"),
그런 것도 본문은 본문이라 그대로 싣습니다.
"""
import html
import re
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

PAGE = 25          # SuccessFactors 기본 한 쪽 크기
MAX_PAGES = 40     # 안전장치. 1,000건이면 충분합니다.

# 공고 한 덩어리.
TILE = re.compile(r'<li[^>]+class="[^"]*job-tile[^"]*"[^>]*>(.*?)</li>', re.S | re.I)
LINK = re.compile(r'<a[^>]+class="[^"]*jobTitle-link[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                  re.S | re.I)
# 라벨과 값이 쌍으로 붙어 나옵니다.
PAIR = re.compile(
    r'<span[^>]+class="[^"]*section-label[^"]*"[^>]*>(.*?)</span>\s*'
    r'<span[^>]+class="[^"]*section-field[^"]*"[^>]*>(.*?)</span>', re.S | re.I)
# 상세 본문.
BODY = re.compile(r'<div[^>]+class="[^"]*jobdescription[^"]*"[^>]*>(.*?)</div>\s*</div>',
                  re.S | re.I)
# 상세 주소 끝의 공고 번호.
JOBNO = re.compile(r'/(\d{4,})/?\s*$')

# 라벨 → 우리 필드. 회사마다 이름이 달라 여러 표기를 받아둡니다.
LABEL_CORP = ("회사", "법인", "company", "회사명")
LABEL_DEPT = ("부서", "직군", "department", "job function")
LABEL_LOC = ("지역", "근무지", "location", "근무지역")
LABEL_EMP = ("직원유형", "고용형태", "employment type", "employee type")


def _get(url):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9",
    })
    last = None
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError:
            raise
        except Exception as e:
            last = e
            if i < 2:
                time.sleep(2 + i * 2)
    raise last


def _text(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def _field(label, raw):
    """section-field 값에서 앞에 붙은 라벨을 떼어냅니다.

    "회사\n\n  LS전선" → "LS전선"
    """
    v = _text(raw)
    lab = _text(label)
    if lab and v.startswith(lab):
        v = v[len(lab):].strip()
    return v


def _career(title):
    """제목에서만 읽습니다. 없으면 무관. 지어내지 않습니다."""
    t = title or ""
    has_new = re.search(r"신입", t)
    has_exp = re.search(r"경력", t)
    if has_new and has_exp:
        return "신입/경력"
    if has_exp:
        return "경력"
    if has_new:
        return "신입"
    return "무관"


def _base(code):
    """code 는 도메인입니다. 앞에 스킴이 없으면 붙입니다."""
    c = (code or "").strip().rstrip("/")
    if not c:
        raise RuntimeError(
            "successfactors: code 가 비어 있습니다. "
            "채용 사이트 도메인을 적으세요. 예: careers.lscablebiz.com")
    if not c.startswith("http"):
        c = "https://" + c
    return c


def list_open(code):
    """공고 목록. probe 용으로 밖에서도 씁니다.

    startrow 를 늘려 가며 더 없을 때까지 받습니다.
    """
    base = _base(code)
    seen, rows = set(), []

    for i in range(MAX_PAGES):
        url = f"{base}/search/?q=&startrow={i * PAGE}"
        page = _get(url)
        tiles = TILE.findall(page)
        if not tiles:
            if i == 0:
                print(f"  ! successfactors({code}): 공고를 찾지 못했습니다. ({url})")
                print(f"    받은 HTML {len(page)}자 · "
                      f"'job-tile' {page.count('job-tile')}회 · "
                      f"'jobTitle-link' {page.count('jobTitle-link')}회")
            break

        added = 0
        for chunk in tiles:
            m = LINK.search(chunk)
            if not m:
                continue
            href, title = m.group(1), _text(m.group(2))
            no = JOBNO.search(href.split("?")[0])
            if not no:
                continue
            jid = no.group(1)
            # 데스크톱·모바일 마크업이 겹쳐 같은 공고가 여러 번 나옵니다.
            if jid in seen:
                continue
            seen.add(jid)

            info = {}
            for lab, val in PAIR.findall(chunk):
                key = _text(lab).lower()
                info[key] = _field(lab, val)

            def pick(names):
                for n in names:
                    if n.lower() in info:
                        return info[n.lower()]
                return ""

            rows.append({
                "id": jid,
                "url": urllib.parse.urljoin(base, html.unescape(href)),
                "title": title,
                "corp": pick(LABEL_CORP),
                "dept": pick(LABEL_DEPT),
                "location": pick(LABEL_LOC),
                "employment": pick(LABEL_EMP),
            })
            added += 1

        if added == 0:
            break
        time.sleep(0.3)

    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    code = company["code"]

    rows = list_open(code)

    jobs = []
    for x in rows:
        raw = ""
        try:
            m = BODY.search(_get(x["url"]))
            raw = m.group(1) if m else ""
        except Exception:
            raw = ""
        time.sleep(0.3)

        text = strip_html(raw)
        # 본문이 이미지뿐이면 세부 직무를 읽을 수 없습니다. 원문으로 보냅니다.
        image_only = len(text) < 50 and "<img" in raw.lower()

        # 정규직이 아니면 제목에 표시합니다.
        title = x["title"]
        emp = x["employment"]
        if emp and emp != "정규직" and emp not in title:
            title = f"{title} ({emp})"

        jobs.append({
            "id": f"sf-{slug}-{x['id']}",
            "unit": "공고",
            # 회사 칸이 있으면 그 값을 씁니다. 계열사가 섞여 오는 곳이 있습니다.
            "company": x["corp"] or name,
            "companySlug": slug,
            "title": title,
            "location": x["location"],
            "career": _career(x["title"]),
            # 게시일·마감일을 주지 않습니다. 비우면 상시채용으로 표시됩니다.
            "postedAt": "",
            "closesAt": "",
            "dday": None,
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": x["url"],
            "description": raw if not image_only else "",
        })

    return jobs
