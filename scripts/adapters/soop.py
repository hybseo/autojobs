# -*- coding: utf-8 -*-
"""
SOOP(구 아프리카TV) 채용 수집기.

목록  GET https://recruit.sooplive.com/recruit_list.php
상세  GET https://recruit.sooplive.com/recruit_list_sub.php?division=..&sub_idx=..&e_idx=..

공개 API 가 없습니다. 서버가 HTML 을 완성해서 보냅니다.
그래서 HTML 을 읽습니다. 화면 개편에 약하므로 공고를 하나도 찾지 못하면
조용히 0건이 되지 않고 무엇을 받았는지 남깁니다.

목록 구조 (2026-09-09 확인)
---------------------------
    <div class="recruitList_box">
      <ul>
        <li>
          <a href="recruit_list_sub.php?division=..&sub_idx=..&e_idx=..">
            <div class="title"><strong>AI Serving Engineer</strong></div>
            <dl class="info">
              <dt>직군</dt><dd>Tech</dd>
              <dt>채용 유형</dt><dd>경력</dd>
              <dt>근무지 정보</dt><dd>판교</dd>
              <dt>채용 기간</dt><dd>채용완료시</dd>
              <dt>회사정보</dt><dd>SOOP</dd>
              <dt>직원유형</dt><dd>정규직</dd>
            </dl>
          </a>
        </li>

27건 모두 dt 가 정확히 6개였고 순서도 같았습니다. 다만 순서에 기대지
않고 dt 이름으로 값을 찾습니다. 항목이 하나 늘거나 빠져도 견딥니다.

값의 종류 (2026-09-09 기준)
    직군       Tech / Business / Service / Corporate
    채용 유형   경력 / 경력무관 / 신입
    근무지     판교 / 서울
    채용 기간   채용완료시   (날짜가 아닙니다)
    회사정보    SOOP / 숲이스포츠
    직원유형    정규직 / 계약직

계열사에 대하여
--------------
"회사정보" 에 SOOP 과 숲이스포츠가 섞여 옵니다. 이 값을 그대로 회사명으로
씁니다. 넷마블·NC 와 같은 방식입니다. 한 회사로 뭉치면 숲이스포츠 공고를
SOOP 이 뽑는 것으로 잘못 보이게 됩니다.

마감일에 대하여
--------------
"채용 기간" 이 전부 "채용완료시" 입니다. 날짜가 아닙니다.
closesAt 을 비우면 사이트가 상시채용으로 표시합니다.
"채용완료시" 를 날짜 자리에 넣으면 화면이 깨집니다.

본문에 대하여
------------
상세 페이지의 class="board_detail" 안에 본문이 텍스트로 들어 있습니다.
담당업무·자격요건·우대사항이 제대로 적혀 있어 자체 상세 페이지와
JobPosting 스키마를 만들 수 있습니다.
"""
import html
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://recruit.sooplive.com"
LIST_URL = BASE + "/recruit_list.php"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# 공고 한 덩어리. <li> 안에 <a> 가 하나씩 들어 있습니다.
ITEM = re.compile(
    r'<a[^>]+href="([^"]*recruit_list_sub\.php[^"]*)"[^>]*>(.*?)</a>',
    re.S | re.I)
TITLE = re.compile(r'class="[^"]*title[^"]*"[^>]*>\s*<strong[^>]*>(.*?)</strong>',
                   re.S | re.I)
TITLE_ALT = re.compile(r'<strong[^>]*>(.*?)</strong>', re.S | re.I)
PAIR = re.compile(r'<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>', re.S | re.I)

# 상세 본문 영역. 화면이 바뀌면 여기부터 확인하세요.
BODY = re.compile(
    r'class="[^"]*board_detail[^"]*"[^>]*>(.*?)(?=<[^>]+class="[^"]*foot)',
    re.S | re.I)

# "채용 유형" 값 → 사이트 표기.
CAREER = {"경력": "경력", "신입": "신입", "경력무관": "무관",
          "무관": "무관", "신입/경력": "신입/경력", "인턴": "무관"}


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


def _job_id(href):
    """상세 주소의 파라미터로 공고 ID 를 만듭니다.

    파이썬 hash() 는 실행마다 값이 바뀌므로 쓰면 안 됩니다.
    division/sub_idx/e_idx 조합이 공고를 고유하게 가리킵니다.
    """
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
    parts = [q.get(k, [""])[0] for k in ("division", "sub_idx", "e_idx")]
    return "-".join(p for p in parts if p)


def list_open():
    """공고 목록. probe 용으로 밖에서도 씁니다."""
    page = _get(LIST_URL)

    rows = []
    for href, chunk in ITEM.findall(page):
        t = TITLE.search(chunk) or TITLE_ALT.search(chunk)
        if not t:
            continue
        # dt 이름으로 값을 찾습니다. 순서가 바뀌어도 견딥니다.
        info = {_text(k): _text(v) for k, v in PAIR.findall(chunk)}
        rows.append({
            "href": urllib.parse.urljoin(LIST_URL, html.unescape(href)),
            "title": _text(t.group(1)),
            "group": info.get("직군", ""),
            "career": info.get("채용 유형", ""),
            "location": info.get("근무지 정보", ""),
            "period": info.get("채용 기간", ""),
            "corp": info.get("회사정보", ""),
            "employment": info.get("직원유형", ""),
        })

    if not rows:
        # HTML 파싱이라 화면이 바뀌면 조용히 0건이 됩니다.
        # 무엇을 받았는지 남겨야 다음에 정확히 손볼 수 있습니다.
        print(f"  ! SOOP: 공고를 하나도 찾지 못했습니다. ({LIST_URL})")
        print(f"    받은 HTML {len(page)}자 · "
              f"'recruitList_box' {page.count('recruitList_box')}회 · "
              f"'recruit_list_sub' {page.count('recruit_list_sub')}회 · "
              f"'<dt' {page.count('<dt')}회")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]

    rows = list_open()

    jobs = []
    for x in rows:
        jid = _job_id(x["href"])
        if not jid:
            continue

        raw = ""
        try:
            m = BODY.search(_get(x["href"]))
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
            "id": f"soop-{jid}",
            "unit": "공고",
            # 회사정보를 그대로 씁니다. 숲이스포츠 공고가 섞여 있습니다.
            "company": x["corp"] or name,
            "companySlug": slug,
            "title": title,
            "location": x["location"],
            "career": CAREER.get(x["career"], "무관"),
            # 게시일을 주지 않습니다.
            "postedAt": "",
            # "채용 기간" 이 "채용완료시" 라 날짜가 아닙니다.
            # 비우면 상시채용으로 표시됩니다.
            "closesAt": "",
            "dday": None,
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": x["href"],
            "description": raw if not image_only else "",
        })

    return jobs
