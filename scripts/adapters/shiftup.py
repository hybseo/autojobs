# -*- coding: utf-8 -*-
"""
시프트업(shiftup.co.kr) 채용 수집기.

목록  GET https://shiftup.co.kr/recruit/recruit.php
상세  GET https://career.shiftup.co.kr/ko/o/{openingId}

왜 greeting 어댑터를 쓰지 않는가
--------------------------------
시프트업은 그리팅(greetinghr)을 자체 도메인(career.shiftup.co.kr)으로
씁니다. 그러면 greeting.py 에 "domain" 만 적으면 될 것 같지만 안 됩니다.

greeting.py 는 루트 /ko 를 읽어 __NEXT_DATA__ 의 openings 배열을 꺼냅니다.
그런데 시프트업은 그리팅 쪽 목록 페이지를 열어두지 않았습니다.

    career.shiftup.co.kr/ko        페이지를 찾을 수 없습니다
    career.shiftup.co.kr/ko/home   페이지를 찾을 수 없습니다
    career.shiftup.co.kr/ko/guide  페이지를 찾을 수 없습니다

개별 공고(/ko/o/{id})만 열립니다. 목록은 자사 홈페이지에서만 보여주고
지원 단계에서 그리팅으로 넘기는 설정입니다.

그래서 목록은 자사 페이지 HTML 에서 읽고, 본문은 그리팅 상세에서
가져옵니다. greeting.py 를 고쳐 이 경우를 지원하게 만들 수도 있지만,
이미 40여 개사가 잘 도는 어댑터를 건드리는 것은 위험이 큽니다.

목록 HTML 구조 (2026-09-09 확인)
--------------------------------
    <div class="recruit_list">
      <div class="recruit_title">
        <div class="tit">
          <span class="status">신규 프로젝트</span>   프로젝트/부문
          <h4>3D 캐릭터 모델러</h4>                    공고 제목
        </div>
        <ul>
          <li>Artist</li>          직군
          <li>3D 캐릭터 모델러</li>  세부 직무
          <li>3년 이상</li>         경력 요건
          <li>정규직</li>           고용형태
        </ul>
      </div>
      <div class="btn"><a href="https://career.shiftup.co.kr/ko/o/235689/apply">
    </div>

51건 모두 li 가 정확히 4개였고 지원 링크에서 공고 번호를 얻을 수 있었습니다.
화면이 바뀌면 0건이 되므로 아래에서 경고를 남깁니다.

경력 표기에 대하여
------------------
사이트가 "3년 이상", "5년 이하", "0~3년", "무관", "경력 3년 이상" 처럼
제각각으로 적습니다. 신입/경력 구분이 아니라 연차 요건입니다.

숫자가 있으면 경력, "무관" 이면 무관으로 봅니다. "0~3년" 은 신입도
지원 가능하다는 뜻이라 신입/경력으로 봅니다. 애매하면 무관으로 접습니다.
지어내지 않습니다.
"""
import html
import json
import re
import ssl
import time
import urllib.error
import urllib.request

LIST_URL = "https://shiftup.co.kr/recruit/recruit.php"
GREETING = "https://career.shiftup.co.kr"
DETAIL = GREETING + "/ko/o/{}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

NEXT_DATA = re.compile(
    r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)

# 공고 한 덩어리. class 에 recruit_list 가 들어간 div 를 통째로 자릅니다.
BLOCK = re.compile(
    r'<div[^>]+class="[^"]*recruit_list[^"]*"[^>]*>(.*?)(?=<div[^>]+class="[^"]*recruit_list[^"]*"|</section>|</main>)',
    re.S | re.I)
TITLE = re.compile(r'<h4[^>]*>(.*?)</h4>', re.S | re.I)
STATUS = re.compile(r'class="[^"]*status[^"]*"[^>]*>(.*?)</span>', re.S | re.I)
LI = re.compile(r'<li[^>]*>(.*?)</li>', re.S | re.I)
OPENING = re.compile(r'/o/(\d+)')


def _text(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def _get(url, _tries=3):
    """페이지를 받아옵니다. 마지막 시도에서만 인증서 검증을 완화합니다.

    그리팅 자체 도메인은 TLS 설정이 낡아 파이썬 기본값으로는 거부되는
    경우가 있습니다(카카오게임즈·니어스랩에서 겪었습니다).
    greeting.py 와 같은 처리입니다.
    """
    last = None
    for i in range(_tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "ko-KR,ko;q=0.9",
            })
            ctx = None
            if i == _tries - 1:
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


def _career(v):
    """연차 요건을 사이트 표기로 옮깁니다.

    "3년 이상" → 경력      "무관" → 무관
    "0~3년"   → 신입/경력  그 외 → 무관
    """
    t = str(v or "").strip()
    if not t:
        return "무관"
    if "무관" in t:
        return "무관"
    # 0년부터 시작하면 신입도 받는다는 뜻입니다.
    if re.match(r"^0\s*[~\-]", t):
        return "신입/경력"
    if "신입" in t and "경력" in t:
        return "신입/경력"
    if "신입" in t:
        return "신입"
    if re.search(r"\d", t):
        return "경력"
    return "무관"


def _opening_info(oid):
    """그리팅 상세에서 본문과 상태를 꺼냅니다. 실패하면 빈 값."""
    try:
        page = _get(DETAIL.format(oid))
    except Exception:
        return "", ""
    m = NEXT_DATA.search(page)
    if not m:
        return "", ""
    try:
        data = json.loads(m.group(1))
    except Exception:
        return "", ""

    queries = (data.get("props", {}).get("pageProps", {})
               .get("dehydratedState", {}).get("queries", []) or [])
    for q in queries:
        key = json.dumps(q.get("queryKey") or [], ensure_ascii=False)
        if "getOpeningById" not in key:
            continue
        d = (q.get("state") or {}).get("data") or {}
        info = (d.get("data") or d).get("openingsInfo") or {}
        return info.get("detail") or "", info.get("status") or ""
    return "", ""


def list_open():
    """공고 목록. probe 용으로 밖에서도 씁니다."""
    page = _get(LIST_URL)
    rows = []
    for m in BLOCK.finditer(page):
        chunk = m.group(1)
        t = TITLE.search(chunk)
        if not t:
            continue
        oid = OPENING.search(chunk)
        lis = [_text(x) for x in LI.findall(chunk)]
        rows.append({
            "openingId": oid.group(1) if oid else "",
            "title": _text(t.group(1)),
            "status": _text(STATUS.search(chunk).group(1)) if STATUS.search(chunk) else "",
            "group": lis[0] if len(lis) > 0 else "",
            "role": lis[1] if len(lis) > 1 else "",
            "career": lis[2] if len(lis) > 2 else "",
            "employment": lis[3] if len(lis) > 3 else "",
        })

    if not rows:
        # HTML 파싱이라 화면이 바뀌면 조용히 0건이 됩니다.
        # 무엇을 받았는지 남겨야 다음에 정확히 손볼 수 있습니다.
        print(f"  ! 시프트업: 공고를 하나도 찾지 못했습니다. ({LIST_URL})")
        print(f"    받은 HTML {len(page)}자 · "
              f"'recruit_list' {page.count('recruit_list')}회 · "
              f"'<h4' {page.count('<h4')}회 · "
              f"'/o/' {page.count('/o/')}회")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]

    rows = list_open()

    jobs = []
    for x in rows:
        oid = x["openingId"]
        if not oid:
            # 지원 링크가 없으면 상세 주소를 만들 수 없습니다.
            continue

        raw, status = _opening_info(oid)
        time.sleep(0.3)

        # 그리팅 쪽에서 마감된 것으로 나오면 담지 않습니다.
        if status and status != "OPEN":
            continue

        text = strip_html(raw)
        # 본문이 이미지뿐이면 세부 직무를 읽을 수 없습니다. 원문으로 보냅니다.
        image_only = len(text) < 50 and "<img" in raw.lower()

        # 프로젝트명을 제목 앞에 붙입니다. 어느 프로젝트인지가 중요한 회사입니다.
        title = x["title"]
        proj = x["status"]
        if proj and proj not in title:
            title = f"[{proj}] {title}"
        # 인턴 등 정규직이 아니면 표시합니다.
        emp = x["employment"]
        if emp and emp != "정규직" and emp not in title:
            title = f"{title} ({emp})"

        jobs.append({
            "id": f"shiftup-{oid}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            # 근무지를 목록에 주지 않습니다. 지어내지 않습니다.
            "location": "",
            "title": title,
            "career": _career(x["career"]),
            # 게시일·마감일을 목록에 주지 않습니다. 상시채용으로 표시됩니다.
            "postedAt": "",
            "closesAt": "",
            "dday": None,
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": DETAIL.format(oid),
            "description": raw if not image_only else "",
        })

    return jobs
