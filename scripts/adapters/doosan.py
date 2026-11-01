# -*- coding: utf-8 -*-
"""
두산그룹 통합 채용(career.doosan.com) 수집기.

  목록  GET https://career.doosan.com/dsp/sa/RecList.jsp

다른 그룹과 달리 서버가 HTML 을 완성해서 보냅니다. 별도 API 호출이 없어
개발자도구 Network 탭에 아무것도 안 잡힙니다. 그래서 HTML 을 읽습니다.

HTML 파싱이라 화면 개편에 약합니다. 그래서 공고를 하나도 못 찾으면
조용히 0건이 되지 않고 경고를 남깁니다. 첫 실행 로그를 확인하세요.

목록 한 줄의 생김새 (2026-09-01 확인)
-------------------------------------
  두산로보틱스 경력 로봇연구소 안전 보건 담당자 D-29 2026-08-31 ~ 2026-09-30

  계열사   두산로보틱스 / (주)두산-전자 / 두산에너빌리티 ...
  구분     경력 / 신입/인턴십 / 전문/생산/계약직
  제목     로봇연구소 안전 보건 담당자
  남은일수  D-29 / 금일마감
  접수기간  2026-08-31 ~ 2026-09-30

계열사를 골라 담습니다
----------------------
두산은 에너지·건설기계·반도체까지 폭이 넓습니다. 전부 받으면 사이트
성격이 흐려집니다. companies.json 의 "affiliates" 에 회사명을 적으면
그 계열사만 담습니다.

  "affiliates": ["두산로보틱스", "두산밥캣"]

부분 일치로 견줍니다. "두산" 이라고만 적으면 전부 걸리니 계열사명을
끝까지 적으세요.

상세 주소를 만들 수 있습니다 (2026-11-01 고침)
---------------------------------------------
예전에는 "상세가 자바스크립트로 열려 주소를 만들 수 없다"고 적어두고
목록 페이지로만 링크했습니다. 틀린 판단이었습니다.

목록의 공고 링크는 이렇게 생겼습니다.

  <a href="javascript:void(0);"
     onclick="goDetail('1000363504', 'C_REC_MGT_04', 'C_REC_TYPE_02', 'CK000000');"
     class="list-tit">
    <div class="company">두산로보틱스<span class="badge-type">경력</span></div>
    <strong>Physical AI Engineer</strong>
    <div class="deadline"><span class="badge-day">D-60</span>2026-10-08 ~ 2026-12-31</div>
  </a>

goDetail 은 저 네 값을 폼에 담아 같은 주소로 POST 할 뿐입니다. CSRF
토큰이 없어서 **GET 으로 붙여도 똑같은 HTML 이 그대로 옵니다.**

  RecList.jsp?mode=goDetail&REC_ID=..&REC_MGT_CD=..&REC_TYPE_CD=..&q_COMP_CD=..

본문 구조 (2026-11-01 실제 HTML 확인)
-------------------------------------
  <div class="view-list-wrap"><ul class="tb-list">
    <li><ul class="tb-con-res ...">
      <li class="tb1"><dl><dt>자회사/BG</dt><dd>..</dd></dl></li>
      <li class="tb2"> 인원
      <li class="tb3"> 모집분야
      <li class="tb4"> 수행업무/전공/자격요건   ← 본문. 여기가 전부입니다
      <li class="tb5"> 지역
    </ul></li>
    <li> ... 모집분야마다 하나씩 반복 ...
  </ul></div>

표(table)가 아니라 ul/li/dl 입니다. 그리고 수행업무·전공·자격요건·
우대사항에 각각의 태그가 없습니다. 전부 tb4 의 <dd> 안에 <br> 로
이어진 평문이고 `[수행 업무]` `[자격요건]` 같은 대괄호 머리글로만
갈립니다. 머리글 표기는 공고마다 흔들립니다. 그래서 여기서는 나누려
하지 않고 <dd> 를 통째로 본문에 담습니다.

조심할 것 두 가지
  1. goDetail 문자열은 공고 하나당 세 번 나옵니다(a 1 + button 2).
     class="list-tit" 가 붙은 <a> 로 한정해야 45건이 45건으로 잡힙니다.
  2. **tb3(모집분야)이 빈 블록은 앞 블록의 이어짐입니다.** 모집분야
     하나의 본문을 여러 토막으로 끊어 넣은 것입니다. 블록 수를
     모집분야 수로 세면 틀립니다. 실제로 두산로보틱스 Physical AI
     Engineer 는 블록이 3개인데 모집분야는 하나입니다.

근무지는 tb5(지역)뿐입니다. 공고 전체를 대표하는 근무지 칸은 HTML
어디에도 없습니다. 모집분야마다 다를 수 있어(분당/창원 혼재) 중복을
없앤 목록으로 모으고, 셋을 넘으면 비워둡니다.

한계
----
- 공고 번호를 주지 않아 ID 는 계열사+제목+마감일의 해시입니다.
  **이 방식을 바꾸면 이미 써둔 요약이 전부 끊어집니다.** 건드리지 마세요.
"""
import re
import html
import time
import urllib.request

LIST_URL = "https://career.doosan.com/dsp/sa/RecList.jsp"
DETAIL_URL = (LIST_URL + "?mode=goDetail&REC_ID={}&REC_MGT_CD={}"
              "&REC_TYPE_CD={}&q_COMP_CD={}")

# 공고마다 상세를 한 번 더 받습니다. 사이에 쉬는 시간입니다.
DETAIL_GAP = 0.3

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

CAREER = {"경력": "경력", "신입/인턴십": "신입",
          "전문/생산/계약직": "무관", "신입": "신입"}

# 한 공고 줄에서 필요한 조각을 뽑습니다.
#   <계열사> <구분> <제목> <D-29|금일마감> <YYYY-MM-DD> ~ <YYYY-MM-DD>
# 목록 한 항목이 여러 줄로 나뉘어 옵니다. 실제로 이렇게 옵니다.
#
#   두산그룹 ⏎ 신입 ⏎ 2026 두산그룹 신입사원 채용 ⏎ D-20 ⏎ 2026-09-01 ~ 2026-09-21
#
# 처음에는 한 줄인 줄 알고 줄바꿈을 막아뒀다가 하나도 못 잡았습니다.
# 이제 조각 사이에 줄바꿈을 허용합니다. 다만 각 조각 안에는 줄바꿈이
# 없어야 하므로 [^\n]+ 를 씁니다.
SEP = r"[\s\u3000]+"
ROW = re.compile(
    r"(?P<co>[가-힣A-Za-z(][^\n]{0,28}?)" + SEP +
    r"(?P<cls>경력|신입/인턴십|전문/생산/계약직|신입)" + SEP +
    r"(?P<title>[^\n]{2,120}?)" + SEP +
    r"(?P<dday>금일마감|마감|D-\d+)" + SEP +
    r"(?P<start>\d{4}-\d{2}-\d{2})[\s\u3000]*~[\s\u3000]*"
    r"(?P<end>\d{4}-\d{2}-\d{2})")


def _get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


# ── 목록의 공고 링크. class="list-tit" 가 붙은 <a> 만 잡습니다. ──
LINK = re.compile(
    r"<a\b[^>]*onclick\s*=\s*\"goDetail\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,"
    r"\s*'([^']*)'\s*,\s*'([^']*)'\s*\)[^\"]*\"[^>]*class=\"[^\"]*list-tit"
    r"[^\"]*\"[^>]*>(.*?)</a>", re.S | re.I)
# 닫는 태그를 여는 태그와 맞춰야 합니다. div 를 찾는데 </span> 에서
# 끊으면 <div class="deadline"> 안의 날짜가 통째로 빠집니다. 실제로
# 그렇게 짰다가 공고를 하나도 못 잡았습니다.
def _in(tag, cls):
    return re.compile(
        r"<" + tag + r"\b[^>]*class=\"[^\"]*" + cls + r"[^\"]*\"[^>]*>(.*?)</"
        + tag + ">", re.S | re.I)


COMPANY = _in("div", "company")
BADGE_TYPE = _in("span", "badge-type")
BADGE_DAY = _in("span", "badge-day")
DEADLINE = _in("div", "deadline")
STRONG = re.compile(r"<strong\b[^>]*>(.*?)</strong>", re.S | re.I)
PERIOD = re.compile(r"(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})")

# ── 상세의 모집분야 블록. tb1~tb5 의 <dd> 를 꺼냅니다. ──
BLOCK = re.compile(r"<ul\b[^>]*class=\"[^\"]*tb-con-res[^\"]*\"[^>]*>(.*?)</ul>",
                   re.S | re.I)
CELL = re.compile(r"<li\b[^>]*class=\"[^\"]*\btb([1-5])\b[^\"]*\"[^>]*>(.*?)</li>",
                  re.S | re.I)
DD = re.compile(r"<dd\b[^>]*>(.*?)</dd>", re.S | re.I)


def _flat(s):
    """태그를 떼고 공백을 하나로 줄입니다. 값 비교·표시에 씁니다."""
    s = re.sub(r"<!--.*?-->", " ", str(s or ""), flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _dd(chunk):
    """<li class=tbN> 조각에서 <dd> 안쪽 HTML 을 꺼냅니다."""
    m = DD.search(chunk or "")
    return m.group(1) if m else ""


def _text(raw):
    """HTML 을 줄 단위 텍스트로 폅니다."""
    s = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.S | re.I)
    s = re.sub(r"<style[^>]*>.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"</(li|tr|div|p)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "\n", s)
    s = html.unescape(s)
    # 빈 줄이 잔뜩 생깁니다. 줄마다 다듬고 빈 줄은 버립니다.
    lines = [ln.strip() for ln in s.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def _detail(params):
    """상세 HTML 에서 본문과 지역을 꺼냅니다. (본문HTML, 지역) 을 돌려줍니다.

    실패하면 ("", "") 입니다. 한 건이 실패해도 그 공고만 본문 없이
    두고 넘어갑니다. 전체가 멈추는 편이 훨씬 나쁩니다.
    """
    try:
        raw = _get(DETAIL_URL.format(*params))
    except Exception:
        return "", ""
    return _parse_detail(raw)


def _parse_detail(raw):
    """상세 HTML 을 (본문HTML, 지역) 으로 바꿉니다. 시험할 수 있게 뗐습니다."""
    parts, places = [], []
    for bm in BLOCK.finditer(raw):
        cells = {n: c for n, c in CELL.findall(bm.group(1))}
        field = _flat(_dd(cells.get("3", "")))
        body = _dd(cells.get("4", ""))
        place = _flat(_dd(cells.get("5", "")))
        if not re.sub(r"<[^>]+>", "", body).strip():
            continue
        if field:
            # 새 모집분야입니다.
            cur = field
            head = field + (f" ({place})" if place else "")
            parts.append(f"<h3>{html.escape(head)}</h3>")
        # 모집분야 칸이 비면 앞 분야의 본문이 이어지는 것입니다.
        # 머리글을 새로 달지 않고 그대로 이어 붙입니다.
        parts.append(body)
        if place:
            for p in re.split(r"\s*/\s*", place):
                p = p.strip()
                if p and p not in places:
                    places.append(p)

    # 근무지가 넷을 넘으면 "분당 / 창원 / 서울 / 익산" 이 되어 뜻이 없습니다.
    loc = " / ".join(places) if 0 < len(places) <= 3 else ""
    return ("\n".join(parts) if parts else ""), loc


def _rows_from_links(raw):
    """목록 HTML 에서 공고 줄을 꺼냅니다. 상세 주소 파라미터까지 함께."""
    rows = []
    for m in LINK.finditer(raw):
        params = (m.group(1), m.group(2), m.group(3), m.group(4))
        inner = m.group(5)
        co_m = COMPANY.search(inner)
        co_html = co_m.group(1) if co_m else ""
        # 회사명 뒤에 <span class="badge-type">경력</span> 이 붙어 옵니다.
        bt = BADGE_TYPE.search(co_html) or BADGE_TYPE.search(inner)
        cls = _flat(bt.group(1)) if bt else ""
        co = _flat(BADGE_TYPE.sub(" ", co_html))
        st = STRONG.search(inner)
        title = _flat(st.group(1)) if st else ""
        dl = DEADLINE.search(inner)
        dl_html = dl.group(1) if dl else inner
        bd = BADGE_DAY.search(dl_html)
        dday = _flat(bd.group(1)) if bd else ""
        pm = PERIOD.search(_flat(dl_html))
        if not co or not title or not pm:
            continue
        rows.append({
            "company": co, "career": cls, "title": title,
            "dday": dday, "start": pm.group(1), "end": pm.group(2),
            "params": params,
        })
    return rows


def _dday(v):
    """'D-29' → 29, '금일마감' → 0. 부호를 그대로 읽으면 음수가 됩니다."""
    t = str(v or "")
    if "금일" in t or t == "마감":
        return 0
    m = re.search(r"\d+", t)
    return int(m.group(0)) if m else None


def list_open(affiliates=()):
    """접수중 공고 목록. probe 용으로 밖에서도 씁니다."""
    raw = _get(LIST_URL)

    # 링크 태그에서 바로 읽습니다. 상세 주소 파라미터까지 함께 나옵니다.
    rows = _rows_from_links(raw)
    if rows:
        return _only(rows, affiliates)

    # 화면이 바뀌어 링크를 못 읽으면 예전 방식(평문 정규식)으로 한 번 더
    # 시도합니다. 상세 주소는 못 얻지만 공고를 통째로 놓치지는 않습니다.
    print("      ! 두산: 공고 링크를 읽지 못해 예전 방식으로 다시 시도합니다.")
    text = _text(raw)
    rows = []
    for m in ROW.finditer(text):
        d = m.groupdict()
        # 줄 앞에 남은 버튼 글자나 목록 기호를 떼어냅니다.
        co = re.sub(r"^[\s\-·•]*(입사지원|바로가기)?\s*", "", d["co"]).strip()
        title = d["title"].strip()
        # 제목에 '입사지원' 같은 버튼 글자가 딸려오면 잘라냅니다.
        title = re.sub(r"\s*(입사지원|바로가기)\s*$", "", title)
        if not co or not title:
            continue
        rows.append({
            "company": co, "career": d["cls"], "title": title,
            "dday": d["dday"], "start": d["start"], "end": d["end"],
            "params": None,
        })

    if not rows:
        # HTML 파싱이라 화면이 바뀌면 조용히 0건이 됩니다.
        # "구조가 바뀌었다" 는 말만으로는 무엇을 고칠지 알 수 없습니다.
        # 실제로 받은 내용을 남겨야 다음에 정확히 손볼 수 있습니다.
        print(f"      ! 두산: 공고를 하나도 찾지 못했습니다. ({LIST_URL})")
        print(f"        받은 HTML {len(text)}자 · 날짜패턴 "
              f"{len(re.findall(r'\d{4}-\d{2}-\d{2}', text))}개 · "
              f"'경력' {text.count('경력')}회 · 'D-' {text.count('D-')}회")
        # 날짜가 보이면 그 주변을 보여줍니다. 어긋난 지점이 드러납니다.
        m = re.search(r"\d{4}-\d{2}-\d{2}", text)
        if m:
            print("        날짜 주변: "
                  + text[max(0, m.start() - 120):m.start() + 60].replace("\n", "⏎"))
        else:
            print("        앞부분: " + text[:200].replace("\n", "⏎"))
        return []

    return _only(rows, affiliates)


def _only(rows, affiliates):
    """계열사로 걸러냅니다. 두 가지 읽기 방식이 함께 씁니다."""
    if not affiliates:
        return rows

    def norm(v):
        return re.sub(r"[\s\.,()\-]", "", str(v or "")).lower()

    wanted = [norm(a) for a in affiliates]
    keep = [x for x in rows if any(w and w in norm(x["company"]) for w in wanted)]
    if not keep:
        seen = sorted({x["company"] for x in rows})
        print(f"      ! 두산: 지정한 계열사 공고가 없습니다. "
              f"받은 회사 {len(seen)}개:")
        print("        " + ", ".join(seen))
    return keep


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    slug = company["slug"]
    rows = list_open(company.get("affiliates") or [])

    jobs = []
    for x in rows:
        # 공고 번호를 주지 않아 계열사+제목+마감일로 ID 를 만듭니다.
        # 파이썬 hash() 는 실행마다 값이 바뀌므로 쓰면 안 됩니다.
        import hashlib
        key = f"{x['company']}|{x['title']}|{x['end']}"
        jid = hashlib.md5(key.encode()).hexdigest()[:12]

        # 상세를 한 번 더 받아 본문과 지역을 채웁니다.
        body, place = ("", "")
        if x.get("params"):
            body, place = _detail(x["params"])
            time.sleep(DETAIL_GAP)

        jobs.append({
            "id": f"doosan-{jid}",
            "unit": "공고",
            # 계열사명을 그대로 씁니다. "두산" 으로 뭉치면 어느 회사인지 모릅니다.
            "company": x["company"],
            "companySlug": slug,
            "title": x["title"],
            # 모집분야별 '지역' 칸을 모은 값입니다. 공고가 준 값이라
            # 추측이 아닙니다. 넷을 넘게 갈리면 비워둡니다.
            "location": place,
            "career": CAREER.get(x["career"], "무관"),
            "postedAt": x["start"],
            "closesAt": x["end"],
            "dday": _dday(x["dday"]),
            "multiRole": False,
            "sourceTitle": "",
            # 공고별 상세 주소입니다. 파라미터를 못 읽었을 때만 목록으로.
            "sourceUrl": (DETAIL_URL.format(*x["params"])
                          if x.get("params") else LIST_URL),
            # 상세에서 받은 본문입니다. 못 받으면 빈 문자열이고 그때는
            # 예전처럼 원문 링크로만 보냅니다.
            "description": body,
        })

    got = sum(1 for j in jobs if j["description"])
    if jobs:
        print(f"      · 두산: {len(jobs)}건 중 본문 {got}건")
    return jobs
