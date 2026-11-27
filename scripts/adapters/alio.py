# -*- coding: utf-8 -*-
"""
잡알리오(공공기관 채용정보시스템) 수집기.

  목록  GET https://job.alio.go.kr/recruit.do?org_name={기관코드}&ing=2&...
  상세  GET https://job.alio.go.kr/recruitview.do?idx={번호}

왜 잡알리오인가
---------------
한전·한수원·발전사·가스공사·공항공사·코레일·산업은행·기업은행 같은
공공기관은 저마다 채용 대행사를 바꿔 가며 씁니다. 기관마다 수집기를
만들면 대행사가 바뀔 때마다 깨집니다.

공공기관은 채용공고를 잡알리오에 올려야 합니다(기획재정부 운영).
그래서 잡알리오 한 곳만 보면 기관 사이트가 바뀌어도 계속 모입니다.
로그인 없이 누구나 보는 공개 페이지입니다. 2026-11-27 확인했습니다.

code 는 무엇인가
----------------
잡알리오의 기관 코드를 쉼표로 이어 적습니다. 예: "C0247,C0220"
기관 코드는 목록 화면의 기관명 선택 상자에 들어 있는 값입니다
(C0247 = 한국전력공사). 병원·대학·연구원까지 300곳이 넘게 섞여 있어
전부 받지 않고, 등록한 기관만 받습니다.

한 항목에 여러 기관이 들어 있으므로 그룹 어댑터처럼 공고마다 기관명을
회사명으로 씁니다. 산업은 companies.json 의 industry 를 따릅니다.

주의
----
- 목록은 10건씩 나옵니다. 넘치면 다음 쪽을 봅니다.
- 등록일 검색 기본값이 최근 두 달이라, 오래 열려 있는 공고가 빠지지
  않게 1년 전부터 찾습니다. ing=2 는 "진행중"입니다.
- 정규직 공고만 담습니다 (2026-11-27 대표님 지시). 기간제·대체인력·
  무기계약직·청년인턴은 뺍니다. 목록의 고용형태 칸이 "정규직, 비정규직"
  처럼 여럿이면 정규직이 들어 있으니 담습니다. 검색 조건(work_type=R1010)
  으로 먼저 거르고, 받은 뒤 고용형태 칸을 한 번 더 확인합니다.
- 본문은 상세 페이지의 응시자격·우대내용·전형절차와 첨부 공고문
  링크로 만듭니다. 공고문 자체는 한글(hwp) 파일이라 열지 않습니다.
"""
import html
import http.cookiejar
import re
import ssl
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://job.alio.go.kr"
KST = timezone(timedelta(hours=9))
MAX_PAGES = 20

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

_ctx = ssl.create_default_context()
_ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
_opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    urllib.request.HTTPSHandler(context=_ctx))


def _get(url):
    last = None
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": "text/html",
                "Accept-Language": "ko-KR,ko;q=0.9"})
            with _opener.open(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(2 + i * 2)
    raise last


def _text(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"[ \t\r\f\v]+", " ", html.unescape(s)).strip()


def _clean_org(name):
    """(주)·주식회사·(재) 같은 꼬리를 뗍니다. 한전KPS(주) → 한전KPS"""
    n = re.sub(r"\((주|재)\)|주식회사|재단법인", "", name or "")
    return re.sub(r"\s+", " ", n).strip()


ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
IDX = re.compile(r"recruitview\.do\?idx=(\d+)")


def _list_org(org, today):
    """기관 하나의 진행중 공고 목록."""
    s_date = (today - timedelta(days=365)).strftime("%Y.%m.%d")
    e_date = today.strftime("%Y.%m.%d")
    out, seen = [], set()
    for p in range(1, MAX_PAGES + 1):
        q = urllib.parse.urlencode({
            "org_name": org, "ing": "2", "pageNo": str(p),
            "work_type": "R1010",   # 정규직
            "s_date": s_date, "e_date": e_date})
        page = _get(f"{BASE}/recruit.do?{q}")
        # 목록 표만 봅니다. 검색 상자에도 <tr> 이 많습니다.
        i = page.find("<th scope=\"col\">채용제목</th>")
        body = page[i:] if i >= 0 else ""
        added = 0
        for row in ROW.findall(body):
            m = IDX.search(row)
            if not m or m.group(1) in seen:
                continue
            cells = [_text(c) for c in TD.findall(row)]
            # 체크칸, 번호, 제목, 기관명, 근무지, 고용형태, 등록일, 마감일, 상태
            if len(cells) < 9:
                continue
            seen.add(m.group(1))
            added += 1
            out.append({
                "idx": m.group(1), "title": cells[2], "org": cells[3],
                "location": cells[4], "type": cells[5],
                "posted": cells[6], "closes": cells[7], "state": cells[8]})
        if added < 10:
            break
        time.sleep(0.3)
    return out


def _is_regular(kind):
    """고용형태 칸에 '정규직'이 따로 들어 있는지. '비정규직'은 아닙니다."""
    return "정규직" in [t.strip() for t in re.split(r"[,/·\s]+", kind or "")]


def _ymd(s, short=False):
    """2026.11.27 / 26.12.04 → 2026-11-27"""
    m = re.search(r"(\d{2,4})\.(\d{1,2})\.(\d{1,2})", s or "")
    if not m:
        return ""
    y = int(m.group(1))
    if y < 100:
        y += 2000
    try:
        return datetime(y, int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return ""


CAREER = {"신입": "신입", "경력": "경력", "신입+경력": "신입/경력",
          "경력+신입": "신입/경력"}

SECTION = re.compile(r"<h4>(.*?)</h4>\s*<p>(.*?)</p>", re.S)
FIELD = re.compile(r"<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>", re.S)
FILE = re.compile(r'<a href="(https://www\.alio\.go\.kr/download/[^"]+)"[^>]*>(.*?)</a>', re.S)


def _detail(idx):
    """상세 페이지에서 항목표와 본문을 꺼냅니다."""
    page = _get(f"{BASE}/recruitview.do?idx={idx}")
    page = re.sub(r"<script[\s\S]*?</script>", "", page)
    fields = {}
    i, j = page.find('class="infoLink"'), page.find('id="contentTab"')
    if i >= 0 and j > i:
        for k, v in FIELD.findall(page[i:j]):
            fields[_text(k)] = _text(v)
    parts = []
    keep = [k for k in ("표준직무(NCS)", "채용구분", "고용형태", "근무지",
                        "채용인원", "채용기간") if fields.get(k)]
    if keep:
        parts.append("<ul>" + "".join(
            f"<li>{html.escape(k)}: {html.escape(fields[k])}</li>" for k in keep)
            + "</ul>")
    t1 = page.find('id="tab-1"')
    t2 = page.find('id="tab-2"')
    if t1 >= 0:
        for h, p in SECTION.findall(page[t1:t2 if t2 > t1 else None]):
            txt = _text(p)
            if not txt:
                continue
            lines = "<br>".join(html.escape(x) for x in txt.split("\n") if x.strip())
            parts.append(f"<h3>{html.escape(_text(h))}</h3><p>{lines}</p>")
    t3 = page.find('id="tab-3"')
    if t3 >= 0:
        files = FILE.findall(page[t3:])
        if files:
            parts.append("<h3>첨부파일</h3><ul>" + "".join(
                f'<li><a href="{html.escape(u)}">{html.escape(_text(n))}</a></li>'
                for u, n in files) + "</ul>")
    return fields, "\n".join(parts)


def fetch(company):
    slug = company["slug"]
    orgs = [c.strip() for c in str(company["code"]).split(",") if c.strip()]
    today = datetime.now(KST).replace(tzinfo=None)
    rows, failed = [], []
    for org in orgs:
        try:
            got = _list_org(org, today)
        except Exception as e:
            failed.append(f"{org}({type(e).__name__})")
            continue
        rows.extend(got)
        time.sleep(0.3)
    total = len(rows)
    rows = [x for x in rows if _is_regular(x["type"])]
    print(f"  · alio: 기관 {len(orgs)}곳에서 진행중 정규직 {len(rows)}건 "
          f"(받은 {total}건 중 정규직 아닌 {total - len(rows)}건 제외)"
          + (f" · 실패 {', '.join(failed)}" if failed else ""))

    jobs = []
    for x in rows:
        try:
            fields, body = _detail(x["idx"])
        except Exception:
            fields, body = {}, ""
        period = fields.get("채용기간", "")
        closes = _ymd(period.split("~")[-1]) if "~" in period else _ymd(x["closes"])
        dday = None
        if closes:
            dday = (datetime.strptime(closes, "%Y-%m-%d") - today.replace(
                hour=0, minute=0, second=0, microsecond=0)).days
            if dday < 0:
                continue
        jobs.append({
            "id": f"alio-{x['idx']}",
            "unit": "공고",
            "company": _clean_org(x["org"]),
            "companySlug": slug,
            "title": x["title"],
            "location": fields.get("근무지") or x["location"],
            "career": CAREER.get(fields.get("채용구분", "").replace(" ", ""), "무관"),
            "postedAt": _ymd(fields.get("등록일") or x["posted"]),
            "closesAt": closes,
            "dday": dday,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": f"{BASE}/recruitview.do?idx={x['idx']}",
            "description": body if len(_text(body)) >= 50 else "",
        })
        time.sleep(0.3)
    return jobs
