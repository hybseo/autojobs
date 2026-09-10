# -*- coding: utf-8 -*-
"""
시프트업(shiftup.co.kr) 채용 수집기.

목록  GET https://shiftup.co.kr/recruit/recruit.php

요청 한 번이면 끝납니다. 서버가 내려주는 HTML 안에 제목·직군·경력·
고용형태·본문이 전부 들어 있습니다. 상세 페이지를 따로 읽지 않습니다.

브라우저 화면을 보고 짜면 안 됩니다 — 실제로 그래서 0건이 났습니다
------------------------------------------------------------------
처음에는 지원 버튼의 그리팅 주소(/ko/o/{번호})에서 공고 번호를 뽑아
쓰도록 짰습니다. 개발자도구로 보면 분명히 그 링크가 있었습니다.

그런데 2026-09-10 수집에서 0건이 나왔습니다. 서버가 내려주는 원본
HTML 을 그대로 받아 보니 "/o/" 가 한 번도 나오지 않았습니다.
그 링크는 자바스크립트가 나중에 만들어 넣는 것이었습니다.

개발자도구에 보이는 것은 자바스크립트가 다 돌고 난 뒤의 모습입니다.
수집기는 그 전 상태를 받습니다. 서버 응답을 직접 확인하고 짜세요.

다행히 원본 HTML 에 본문까지 다 들어 있어 그리팅에 갈 이유가 없습니다.
공고 51건이면 51번 왕복할 것을 한 번으로 끝냅니다.

함정 — 마감된 공고가 같이 옵니다
--------------------------------
2026-09-10 기준 recruit_list 블록이 185개인데 화면에는 51건만 보입니다.
서버가 지난 공고까지 전부 보내고 자바스크립트가 걸러내기 때문입니다.

구분은 블록 첫머리의 상태 표시입니다.

    <span class='status ing'>진행중</span>    ← 51건
    <span class='status'>마감</span>          ← 134건

주의: class 가 홑따옴표(')이고 뒤에 ing 가 더 붙습니다. 겹따옴표로만
찾으면 하나도 못 잡습니다. 아래 정규식이 둘 다 받습니다.

이걸 안 거르면 마감된 공고 134건이 진행중으로 올라갑니다.

블록 구조 (2026-09-10 확인)
---------------------------
    <div class="recruit_list">
      <div class="recruit_title">
        <div class="tit">
          <span class='status ing'>진행중</span>
          <h4>3D 캐릭터 모델러</h4>
        </div>
        <ul>
          <li>3D 캐릭터 모델러</li>   세부 직무
          <li>3년 이상</li>          경력 요건
          <li>정규직</li>            고용형태
        </ul>
      </div>
      <div class="recruit_desc">
        <div class="recruit_content"> ... 본문 ... </div>
      </div>
    </div>

원문 주소에 대하여
------------------
공고마다 고유 주소가 없습니다. 지원 버튼의 그리팅 주소는 자바스크립트가
만들고, 목록 페이지 자체에는 개별 주소가 없습니다. 그래서 모두 목록
페이지로 보냅니다. 본문은 우리 상세 페이지에서 볼 수 있으니 구직자가
헤매지는 않습니다.

없는 주소를 지어내지 않습니다. 그리팅 번호를 추측해 붙이면 엉뚱한 회사
공고로 보내게 됩니다.

id 에 대하여
------------
공고 번호가 없어 제목으로 만듭니다. 같은 제목이 여럿이면 뒤에 순번을
붙입니다. 파이썬 hash() 는 실행마다 값이 바뀌므로 쓰면 안 됩니다.
매번 다른 id 가 나오면 어제 공고와 오늘 공고를 다른 것으로 봅니다.

경력 표기에 대하여
------------------
"3년 이상", "0~3년", "무관", "5년 이하" 처럼 연차로 적습니다.
신입/경력 구분이 아닙니다. 0년부터 시작하면 신입도 받는다는 뜻으로
읽고, 숫자가 있으면 경력, "무관" 이면 무관으로 봅니다.
"""
import hashlib
import html
import re
import time
import urllib.error
import urllib.request

LIST_URL = "https://shiftup.co.kr/recruit/recruit.php"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# 상태 표시. class 가 홑따옴표이고 'status ing' 처럼 뒤에 더 붙습니다.
STATUS = re.compile(r"""class=['"]status[^'"]*['"][^>]*>([^<]{0,12})<""", re.I)
TITLE = re.compile(r"<h4[^>]*>(.*?)</h4>", re.S | re.I)
LI = re.compile(r"<li[^>]*>(.*?)</li>", re.S | re.I)
# 본문. recruit_content 안쪽입니다.
BODY = re.compile(
    r'<div[^>]+class="[^"]*recruit_content[^"]*"[^>]*>(.*?)</div>\s*</div>',
    re.S | re.I)


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


def _career(v):
    """연차 요건을 사이트 표기로 옮깁니다.

    "3년 이상" → 경력      "무관" → 무관
    "0~3년"   → 신입/경력  그 외 → 무관
    """
    t = str(v or "").strip()
    if not t or "무관" in t:
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


def _slug(title):
    """제목으로 안정된 id 조각을 만듭니다.

    hash() 는 실행마다 값이 달라 쓰면 안 됩니다. md5 는 언제나 같습니다.
    """
    return hashlib.md5(title.encode("utf-8")).hexdigest()[:10]


def list_open():
    """진행중 공고만 골라 돌려줍니다. probe 용으로 밖에서도 씁니다."""
    page = _get(LIST_URL)
    blocks = page.split('class="recruit_list"')[1:]

    if not blocks:
        # HTML 파싱이라 화면이 바뀌면 조용히 0건이 됩니다.
        print(f"  ! 시프트업: 공고 블록을 찾지 못했습니다. ({LIST_URL})")
        print(f"    받은 HTML {len(page)}자 · "
              f"'recruit_list' {page.count('recruit_list')}회 · "
              f"'<h4' {page.count('<h4')}회")
        return []

    rows, closed = [], 0
    for b in blocks:
        st = STATUS.search(b)
        state = _text(st.group(1)) if st else ""
        # 마감된 공고가 함께 옵니다. 진행중만 담습니다.
        if state != "진행중":
            closed += 1
            continue

        t = TITLE.search(b)
        if not t:
            continue
        title = _text(t.group(1))
        if not title:
            continue

        lis = [_text(x) for x in LI.findall(b)]
        m = BODY.search(b)

        rows.append({
            "title": title,
            "role": lis[0] if len(lis) > 0 else "",
            "career": lis[1] if len(lis) > 1 else "",
            "employment": lis[2] if len(lis) > 2 else "",
            "body": m.group(1) if m else "",
        })

    if not rows:
        print(f"  ! 시프트업: 진행중 공고가 없습니다. "
              f"(블록 {len(blocks)}개 중 마감 {closed}개) "
              f"상태 표시가 바뀌었는지 확인하세요.")
    else:
        print(f"  · 시프트업: 블록 {len(blocks)}개 중 진행중 {len(rows)}건")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]

    rows = list_open()

    jobs, seen = [], {}
    for x in rows:
        raw = x["body"]
        text = strip_html(raw)
        # 본문이 이미지뿐이면 세부 직무를 읽을 수 없습니다.
        image_only = len(text) < 50 and "<img" in raw.lower()

        # 정규직이 아니면 제목에 표시합니다.
        title = x["title"]
        emp = x["employment"]
        if emp and emp != "정규직" and emp not in title:
            title = f"{title} ({emp})"

        # 공고 번호가 없어 제목으로 만듭니다. 같은 제목이 여럿이면 순번을 붙입니다.
        base = _slug(x["title"])
        seen[base] = seen.get(base, 0) + 1
        jid = base if seen[base] == 1 else f"{base}-{seen[base]}"

        jobs.append({
            "id": f"shiftup-{jid}",
            "unit": "공고",
            "company": name,
            "companySlug": slug,
            "title": title,
            # 근무지를 주지 않습니다. 지어내지 않습니다.
            "location": "",
            "career": _career(x["career"]),
            # 게시일·마감일을 주지 않습니다. 상시채용으로 표시됩니다.
            "postedAt": "",
            "closesAt": "",
            "dday": None,
            "multiRole": image_only,
            "sourceTitle": "",
            # 공고마다 고유 주소가 없습니다. 목록으로 보냅니다.
            "sourceUrl": LIST_URL,
            "description": raw if not image_only else "",
        })

    return jobs
