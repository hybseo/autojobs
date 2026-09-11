# -*- coding: utf-8 -*-
"""
두들린 '그리팅(greetinghr.com)' ATS 수집기.
리크루터를 안 쓰는 중견기업이 많이 씁니다.

  목록  GET https://{code}.career.greetinghr.com/ko
  상세  GET https://{code}.career.greetinghr.com/ko/o/{openingId}

공고 목록 페이지의 이름은 회사마다 다릅니다. guide, apply, intro, home 등
제각각입니다. 그런데 루트 /ko 로 들어가면 어느 페이지로 넘어가든 공고 목록이
함께 실려 옵니다. 그래서 경로를 추측하지 않고 루트만 씁니다.

자체 도메인을 붙인 회사도 있습니다. 현대오토에버가 career.hyundai-autoever.com
을 쓰는데 속은 그리팅입니다. 이런 곳은 companies.json 에 "domain" 을 적어주면
그 주소를 씁니다. 자체 도메인은 robots.txt 도 따로 있으니 추가 전에 확인하세요.

공개 API 가 따로 없어서 페이지 HTML 을 받아옵니다. 다만 HTML 태그를 파싱하는
것이 아니라, Next.js 가 심어두는 <script id="__NEXT_DATA__"> 안의 JSON 을
꺼내 씁니다. 화면 디자인이 바뀌어도 이 JSON 구조는 잘 안 바뀝니다.

robots.txt (2026-08-25 확인)
---------------------------
  User-agent: *
  Allow: /
  Disallow: /o/*/apply, /ko/o/*/apply, /m/*, /a/*
  Content-Signal: search=yes

공고 목록과 상세는 허용, 지원서 경로만 금지입니다. 이 수집기는 /ko/guide 와
/ko/o/{id} 만 읽습니다. 지원 경로(/apply)는 절대 요청하지 마세요.

주의
----
- status 가 "OPEN" 인 것만 접수중입니다.
- dueDate 가 null 인 상시채용 공고가 많습니다. 마감일 없이 그대로 둡니다.
- 한 공고에 여러 직무(openingJobPositions)가 붙을 수 있습니다.
  경력 조건이 서로 다르면 "분야별상이" 로 표시합니다.

인재풀 공고는 담지 않습니다
---------------------------
"인재풀 등록", "Talent Pool", "상시 인재채용" 같은 공고가 섞여 옵니다.
지금 자리가 난 것이 아니라 이력서를 미리 받아두는 창구입니다.

구직자가 목록에서 보고 "채용 중이구나" 하고 들어갔다가 이력서만 넣고
나오게 됩니다. 지원할 수 있는 자리를 찾으러 온 사람에게는 헛걸음입니다.
그래서 Ashby·Workable·네오위즈 어댑터와 같은 기준으로 뺍니다.

2026-09-11 기준 그리팅 888건 중 39건이 여기 해당했습니다. 회사 이름만
다를 뿐 전부 같은 성격이었고, 실제 공고를 잘못 거르는 경우는 없었습니다.

표기가 회사마다 다릅니다. "인재풀 등록", "Talent Pool", "인재 Pool",
"상시 인재채용", "인재DB 등록", "People Database" 를 모두 잡습니다.
다만 "지역우수인재 채용" 처럼 실제 공고에도 '인재' 가 들어가므로,
뒤에 상시·풀·pool·db 가 따라올 때만 거릅니다. 그냥 '인재' 로 거르면
멀쩡한 공고가 사라집니다.

담고 싶으면 companies.json 에 "includePool": true 를 넣으세요.
"""
import json
import re
import time
import html
import ssl
import urllib.request

UA = "Mozilla/5.0 (compatible; searchjob.co.kr job aggregator)"

# 그리팅 careerType → 사이트 표기
CAREER = {"EXPERIENCED": "경력", "NEW_COMER": "신입", "NOT_MATTER": "무관"}

# 이력서만 받아두는 창구. 실제 자리가 아닙니다.
# "인재풀 등록", "Talent Pool", "상시 인재채용", "인재 Pool" 을 모두 잡습니다.
POOL = re.compile(
    r"인재\s*(?:상시|풀|pool|db)|talent\s*pool|상시\s*인재|people\s*database", re.I)

NEXT_DATA = re.compile(
    r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def _html(url, _tries=3):
    """페이지를 받아옵니다. 실패하면 잠시 쉬었다 다시 시도합니다.

    왜 재시도가 필요한가
    --------------------
    2026-09-08 갱신에서 8개사가 실패했는데 대부분 일시적인 것이었습니다.
    한화는 timed out, 카카오게임즈·니어스랩은 SSL 핸드셰이크 실패였습니다.
    같은 주소를 브라우저로 열면 정상이었습니다.

    한 번 실패하면 그 회사 공고가 통째로 빠집니다. 실제로 한화 17건이
    하루 사라졌습니다. 몇 초 기다렸다 다시 걸어보는 편이 낫습니다.

    SSL 핸드셰이크 실패에 대하여
    ----------------------------
    자체 도메인을 쓰는 그리팅 사이트에서 나옵니다
    (recruit.kakaogames.com, career.nearthlab.com).
    서버가 오래된 TLS 설정을 쓰거나 중간 인증서를 빠뜨린 경우입니다.
    브라우저는 관대하게 넘어가지만 파이썬 기본 설정은 거부합니다.

    마지막 시도에서만 검증을 완화합니다. 우리는 공개된 채용 공고를
    읽을 뿐이고, 그마저 못 읽으면 그 회사가 통째로 빠지기 때문입니다.
    """
    last = None
    for i in range(_tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            ctx = None
            if i == _tries - 1:
                # SECLEVEL=1 로도 안 되는 서버가 있습니다.
                # 카카오게임즈·니어스랩이 그렇습니다. 더 낮추고 옛 TLS 도
                # 허용합니다. 여기까지 왔다는 건 그러지 않으면 그 회사
                # 공고가 통째로 빠진다는 뜻입니다.
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                ctx.minimum_version = ssl.TLSVersion.TLSv1
                try:
                    ctx.set_ciphers("ALL:@SECLEVEL=0")
                except ssl.SSLError:
                    ctx.set_ciphers("DEFAULT@SECLEVEL=1")
            with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            if i < _tries - 1:
                time.sleep(2 + i * 2)
    raise last


def _next_data(url):
    m = NEXT_DATA.search(_html(url))
    if not m:
        raise RuntimeError(f"__NEXT_DATA__ 를 찾지 못했습니다: {url}")
    return json.loads(m.group(1))


def _queries(data):
    return (data.get("props", {}).get("pageProps", {})
                .get("dehydratedState", {}).get("queries", []) or [])


def _pick(queries, first_key=None, second_key=None):
    for q in queries:
        k = q.get("queryKey") or []
        if first_key and k and k[0] == first_key:
            return (q.get("state") or {}).get("data")
        if second_key and len(k) > 1 and k[1] == second_key:
            return (q.get("state") or {}).get("data")
    return None


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def _career_label(positions):
    """직무별 경력 조건을 모아 사이트 표기 한 개로 정리합니다."""
    types = set()
    for p in positions or []:
        c = (p or {}).get("jobPositionCareer") or {}
        if c.get("careerType"):
            types.add(c["careerType"])
    if not types:
        # 직무에 경력 조건이 안 붙은 공고가 있습니다. 빈 값으로 두면
        # 화면에 이름 없는 필터 칩이 생깁니다. "무관" 으로 봅니다.
        return "무관"
    if types == {"EXPERIENCED", "NEW_COMER"}:
        return "신입/경력"
    if len(types) == 1:
        return CAREER.get(next(iter(types)), "무관")
    return "분야별상이"


def _location(positions):
    places = []
    for p in positions or []:
        wp = (p or {}).get("workspacePlace") or {}
        loc = wp.get("location") or wp.get("place")
        if loc and loc not in places:
            places.append(loc)
    if not places:
        return ""
    return places[0] if len(places) == 1 else f"{places[0]} 외 {len(places) - 1}곳"


def base_url(company):
    """회사의 채용 사이트 주소. 자체 도메인이 있으면 그것을 씁니다."""
    dom = (company.get("domain") or "").strip()
    if dom:
        return "https://" + dom.split("://")[-1].rstrip("/")
    return f"https://{company['code']}.career.greetinghr.com"


def list_open(company, path=""):
    """접수중 공고 요약 목록. probe 용으로 밖에서도 씁니다.

    path 를 넘기면 그 페이지를 읽습니다. 보통은 비워두고 루트를 씁니다.
    """
    url = base_url(company) + "/ko"
    if path:
        url += "/" + path.lstrip("/")
    data = _next_data(url)
    raw = _pick(_queries(data), first_key="openings")
    if raw is None:
        return []
    # 배열이 아니라 {"0":{...},"1":{...}} 형태로 실려 옵니다.
    rows = list(raw.values()) if isinstance(raw, dict) else list(raw)
    rows = [r for r in rows if r.get("deploy") is not False]

    if company.get("includePool"):
        return rows

    kept = [r for r in rows if not POOL.search(str(r.get("title") or ""))]
    dropped = len(rows) - len(kept)
    if dropped:
        print(f"      · 인재풀 {dropped}건 제외")
    return kept


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    code = company["code"]
    base = base_url(company)

    rows = list_open(company, company.get("path", ""))

    jobs = []
    for r in rows:
        oid = r.get("openingId")
        if not oid:
            continue
        positions = ((r.get("openingJobPosition") or {})
                     .get("openingJobPositions") or [])

        raw = ""
        try:
            d = _next_data(f"{base}/ko/o/{oid}")
            info = ((_pick(_queries(d), second_key="getOpeningById") or {})
                    .get("data") or {}).get("openingsInfo") or {}
            # status 가 OPEN 이 아니면 마감된 공고입니다.
            if info.get("status") and info["status"] != "OPEN":
                continue
            raw = info.get("detail") or ""
        except Exception:
            raw = ""

        text = strip_html(raw)
        # 본문이 이미지뿐이면 세부 직무를 읽을 수 없습니다. 원문으로 보냅니다.
        image_only = len(text) < 50 and "<img" in raw.lower()

        jobs.append({
            "id": f"greeting-{code}-{oid}",
            "unit": "공고",
            "company": name, "companySlug": slug,
            "title": r.get("title") or "",
            "location": _location(positions),
            "career": _career_label(positions),
            "postedAt": (r.get("openDate") or "")[:10],
            "closesAt": (r.get("dueDate") or "")[:10],
            "dday": r.get("deadlineDDay"),
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": f"{base}/ko/o/{oid}",
            "description": raw if not image_only else "",
        })
        time.sleep(0.3)

    return jobs
