# -*- coding: utf-8 -*-
"""
Workday 수집기. 외국계 기업 한국법인이 많이 씁니다.

  목록  POST https://{회사}.{서버}.myworkdayjobs.com/wday/cxs/{회사}/{사이트}/jobs
  상세  GET  https://{회사}.{서버}.myworkdayjobs.com/wday/cxs/{회사}/{사이트}/job/{경로}

채용 사이트가 화면을 그릴 때 쓰는 것과 같은 경로입니다. 인증은 필요 없습니다.

code 는 무엇인가
----------------
채용 사이트 주소에서 도메인과 사이트 이름을 그대로 적습니다.

  https://valeo.wd3.myworkdayjobs.com/Valeo_Careers
  → "code": "valeo.wd3.myworkdayjobs.com/Valeo_Careers"

앞의 valeo 가 회사, wd3 이 서버, 뒤가 사이트 이름입니다. 셋 다 있어야
API 주소를 만들 수 있어 통째로 받습니다.

한국 공고만 담습니다
--------------------
Workday 는 전 세계 공고를 한 사이트에 올립니다. 그대로 받으면 수백 건이
쏟아지고 대부분 해외입니다. 국내 구직자용 사이트이므로 한국 근무지만
남깁니다. 해외까지 원하면 companies.json 에 "overseas": true 를 넣으세요.

한국을 거르는 방법을 바꿨습니다 (2026-10-06)
--------------------------------------------
예전에는 공고를 전부 받아 근무지 글자에서 지명을 찾아 걸렀습니다.
두 가지가 문제였습니다.

1. 지명으로는 못 걸러냅니다
   어플라이드 머티어리얼즈의 한국 근무지 표기는 'Hwaseong-Lucestar(KOR)',
   'Pyeongtaek-Mokok(KOR)' 입니다. 'korea' 도 '화성' 도 들어 있지 않아
   한국 공고 87건이 전부 해외로 걸러집니다. 공장 이름을 지명 자리에 쓰는
   회사는 지명 목록을 아무리 늘려도 따라갈 수 없습니다.

2. 전부 받는 것이 너무 비쌉니다
   어플라이드는 전 세계 공고가 2,000건, KLA 는 1,072건입니다. 20건씩
   받으면 회사 하나에 요청이 100번입니다. 갱신이 끝나지 않습니다.

그래서 서버에 "한국만 주세요" 라고 요청합니다. 목록 API 는 응답에
facets(검색 조건) 목록을 함께 주고, 그 안에 나라별 항목과 id 가 있습니다.

    "facets": [{"facetParameter": "Country",
                "values": [{"id": "7a5a...28da",
                            "descriptor": "Korea, Republic of",
                            "count": 87}, ...]}]

이 id 를 appliedFacets 에 넣어 다시 부르면 한국 공고만 옵니다.
어플라이드는 요청이 100번에서 5번으로 줄고, 근무지 표기와 무관하게
정확합니다.

id 를 코드에 적어두지 않습니다
    나라 id 는 테넌트마다 같아 보이지만 확인한 바가 없습니다. 그래서 첫
    응답의 facets 에서 그 테넌트가 알려준 값을 그대로 꺼내 씁니다.
    추측한 값을 넣지 않습니다.

facets 에 한국이 없으면
    그 회사는 지금 한국 공고가 없다는 뜻입니다(2026-10-06 KLA 가 그랬습니다).
    조건 없이 전부 받아 예전 방식으로 거르는 쪽으로 넘어가되, 전 세계
    공고가 SAFE_TOTAL 보다 많으면 요청을 쏟지 않고 멈추고 로그에 남깁니다.
    일진·야놀자·동화기업처럼 한국 기업 테넌트는 공고가 적어 이 길로 갑니다.
"""
import json
import re
import html
import time
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

PAGE = 20          # Workday 는 한 번에 20건씩 줍니다
MAX_PAGES = 25     # 안전장치. 500건이면 충분합니다

# 한국 조건을 못 찾았을 때, 전부 받아도 되는 전 세계 공고 수의 한도.
#
# 400건이면 요청 20번입니다. 그 이상이면 받지 않고 멈춥니다. 외국계
# 대형 테넌트(어플라이드 2,000건·KLA 1,072건)를 조건 없이 받으면 요청이
# 100번씩 들어가 갱신 전체가 제한 시간에 걸립니다. 한국 공고가 없어서
# 조건이 안 나온 것이므로, 멈춰도 잃는 것이 없습니다.
SAFE_TOTAL = 400

# facets 의 나라 항목에서 한국을 찾는 말.
# 'Korea, Republic of', 'South Korea', '대한민국' 모두 걸립니다.
KOREA_NAME = re.compile(r"korea|대한민국|한국", re.I)

# en-EN, ko-KR, de-DE 같은 언어 코드. 사이트 이름이 아닙니다.
LANG = re.compile(r"[a-z]{2}-[A-Za-z]{2}")

# 한국 근무지 판별.
#
# Workday 는 근무지를 자유 문자열로 줍니다. 회사마다 표기가 제각각이라
# 목록에 없는 지명이 나오면 해외로 잘못 걸러집니다.
# 그래서 아래 목록을 넉넉히 두고, 그래도 전부 걸러지면 실제로 어떤 문자열이
# 왔는지 로그에 남깁니다. 추측으로 늘리지 말고 그 로그를 보고 추가하세요.
KOREA = re.compile(
    r"korea|대한민국|한국"
    r"|서울|seoul|부산|busan|대구|daegu|인천|incheon|광주|gwangju"
    r"|대전|daejeon|울산|ulsan|세종|sejong"
    r"|경기|gyeonggi|강원|충북|충남|전북|전남|경북|경남|제주|jeju"
    r"|수원|suwon|성남|판교|pangyo|용인|안양|부천|안산|시흥|화성|평택|김포|파주|이천|광명"
    r"|천안|cheonan|아산|asan|당진|서산|충주|청주|cheongju"
    r"|전주|jeonju|완주|익산|군산|여수|순천|목포"
    r"|포항|pohang|구미|gumi|경주|안동|김천|창원|changwon|김해|양산|거제|진주"
    r"|원주|춘천|강릉", re.I)


def _parts(code):
    """code 를 (호스트, 테넌트, 사이트) 로 나눕니다."""
    c = (code or "").strip().replace("https://", "").replace("http://", "").strip("/")
    if "/" not in c:
        raise ValueError(
            f"code 형식이 잘못됐습니다: {code!r}\n"
            "  '회사.wd3.myworkdayjobs.com/사이트이름' 형태여야 합니다.")
    host, rest = c.split("/", 1)
    tenant = host.split(".")[0]
    parts = [x for x in rest.split("/") if x]
    # 주소에 언어 코드가 끼는 경우가 있습니다. en-EN, ko-KR, de-DE 같은 것들입니다.
    # 이걸 사이트 이름으로 쓰면 API 주소가 틀립니다.
    parts = [x for x in parts if not LANG.fullmatch(x)]
    if not parts:
        raise ValueError(
            f"code 에 사이트 이름이 없습니다: {code!r}\n"
            "  언어 코드만 있습니다. 채용 사이트 주소에서 언어 코드 뒤에 오는\n"
            "  이름까지 넣어주세요. 예: valeo.wd3.myworkdayjobs.com/en-EN/Valeo_Careers")
    return host, tenant, parts[0]


def _post(url, body):
    req = urllib.request.Request(
        url, method="POST", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def _get(url):
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def _date(s):
    """'2026-08-31T...' 또는 'Posted Today' 등이 옵니다. 날짜만 뽑습니다."""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(s or ""))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def _korea_facet(j):
    """첫 응답의 facets 에서 한국을 고르는 조건을 찾습니다.

    (조건이름, id, 표기, 건수) 를 돌려주고, 없으면 None 입니다.
    나라 조건(Country 등)을 먼저 보고, 없으면 다른 조건에서도 찾습니다.
    회사마다 조건 이름이 Country 일 수도, locationCountry 일 수도 있어
    이름을 하나로 못 박습니다.
    """
    facets = j.get("facets") or []

    def pick(only_country):
        for f in facets:
            param = str(f.get("facetParameter") or "")
            if only_country and not re.search(r"country", param, re.I):
                continue
            for v in (f.get("values") or []):
                desc = str(v.get("descriptor") or "")
                if v.get("id") and KOREA_NAME.search(desc):
                    return param, v["id"], desc, v.get("count")
        return None

    return pick(True) or pick(False)


def _page_through(base, facets, label):
    """조건을 걸어 공고를 끝까지 받습니다."""
    out, offset = [], 0
    for _ in range(MAX_PAGES):
        j = _post(f"{base}/jobs", {
            "appliedFacets": facets, "limit": PAGE,
            "offset": offset, "searchText": ""})
        posts = j.get("jobPostings") or []
        if not posts:
            break
        out += posts
        offset += PAGE
        if offset >= (j.get("total") or 0):
            break
        time.sleep(0.4)
    else:
        print(f"      ! {label}: {MAX_PAGES * PAGE}건에서 멈췄습니다. "
              f"더 있을 수 있으니 MAX_PAGES 를 확인하세요.")
    return out


def list_open(code, overseas=False):
    """접수중 공고 목록. probe 용으로 밖에서도 씁니다."""
    host, tenant, site = _parts(code)
    base = f"https://{host}/wday/cxs/{tenant}/{site}"
    label = f"workday({tenant}/{site})"

    # 첫 한 번은 조건 없이 불러 전체 건수와 검색 조건 목록을 받습니다.
    first = _post(f"{base}/jobs", {
        "appliedFacets": {}, "limit": PAGE, "offset": 0, "searchText": ""})
    total = first.get("total") or 0

    if overseas:
        return _page_through(base, {}, label)

    found = _korea_facet(first)

    def by_facet():
        param, fid, desc, cnt = found
        print(f"      · {label}: 전체 {total}건 중 한국 조건 적용"
              f"({param}={desc}, {cnt}건)")
        # 서버가 이미 한국만 걸러 주므로 근무지 글자로 다시 거르지 않습니다.
        # 'Hwaseong-Lucestar(KOR)' 처럼 지명이 없는 표기를 떨어뜨리지 않기
        # 위해서입니다.
        return _page_through(base, {param: [fid]}, label)

    # 공고가 많은 테넌트(외국계 대형)는 조건을 걸어야만 받을 수 있습니다.
    if total > SAFE_TOTAL:
        if found:
            return by_facet()
        print(f"      · {label}: 전체 {total}건인데 한국 조건이 없습니다. "
              f"지금 한국 공고가 없는 것으로 보고 넘어갑니다"
              f"(전부 받으면 요청이 {-(-total // PAGE)}번이라 받지 않습니다).")
        return []

    # 공고가 적은 테넌트는 예전 방식을 그대로 둡니다.
    #
    # 일진·야놀자·동화기업처럼 한국 기업 테넌트가 여기 해당합니다. 이들은
    # 이미 잘 수집되고 있고, 나라 정보가 비어 있는 공고가 조건 때문에
    # 빠지는 일을 피하려고 건드리지 않습니다. 요청도 어차피 몇 번뿐입니다.
    out = _page_through(base, {}, label)
    before = out
    out = [x for x in out if KOREA.search(
        f"{x.get('locationsText','')} {x.get('title','')}")]

    # 다 걸러졌는데 한국 조건은 있는 경우. 근무지 표기가 지명이 아니라
    # 공장 이름인 작은 테넌트입니다. 조건을 걸어 다시 받습니다.
    if before and not out and found:
        print(f"      · {label}: 근무지 글자로는 한국을 찾지 못해 "
              f"한국 조건으로 다시 받습니다.")
        return by_facet()

    if before and not out:
        seen = sorted({(x.get("locationsText") or "?") for x in before})[:6]
        print(f"      ! 한국 근무지로 인식된 공고가 없습니다. "
              f"받은 근무지 표기: {seen}")
    return out


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    code = company["code"]
    host, tenant, site = _parts(code)
    base = f"https://{host}/wday/cxs/{tenant}/{site}"

    rows = list_open(code, overseas=bool(company.get("overseas")))

    # 구조가 다르면 조용히 0건이 됩니다. 그러면 원인을 알 수 없습니다.
    if not rows:
        # 공고가 없는 것과 구조가 바뀐 것을 구분해서 알립니다.
        # 앞 문구는 "구조가 바뀌었을 수 있습니다" 뿐이라, 단순히 채용을
        # 안 하는 회사인데도 오류로 읽혀 원인을 엉뚱한 데서 찾은 적이 있습니다.
        print(f"      · {name}: 접수중 공고 없음. "
              f"채용을 안 하는 중이면 정상입니다. "
              f"공고가 있는데도 0건이면 {base}/jobs 를 확인하세요.")
        return []

    jobs = []
    for x in rows:
        path = x.get("externalPath") or ""
        if not path:
            continue
        jid = path.rstrip("/").split("/")[-1]

        body = ""
        try:
            d = _get(base + "/job" + path)
            info = d.get("jobPostingInfo") or {}
            body = info.get("jobDescription") or ""
        except Exception:
            body = ""
        time.sleep(0.3)

        text = strip_html(body)
        image_only = len(text) < 50 and "<img" in body.lower()

        jobs.append({
            "id": f"workday-{tenant}-{jid}",
            "unit": "공고",
            "company": name, "companySlug": slug,
            "title": x.get("title") or "",
            "location": x.get("locationsText") or "",
            # Workday 는 신입/경력을 구분해 주지 않습니다. 지어내지 않습니다.
            "career": "무관",
            "postedAt": _date(x.get("postedOn") or x.get("startDate")),
            # 마감일을 주지 않습니다. 상시채용으로 표시됩니다.
            "closesAt": "",
            "dday": None,
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": f"https://{host}/{site}{path}",
            "description": body if not image_only else "",
        })

    return jobs
