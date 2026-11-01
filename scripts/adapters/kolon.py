# -*- coding: utf-8 -*-
"""
코오롱그룹(dream.kolon.com) 채용 수집기.

목록  POST https://dream.kolon.com/RECRUIT_KOLON/hr/rec/recruit/jobopen/
           controller/candidate/JobOpen310WebController/searchJobOpenByCandidate2018Renew.hr

코오롱인더스트리·코오롱생명과학·코오롱제약·코오롱베니트 등 계열사 공고가
한 곳에 모여 옵니다.

요청
----
본문을 빈 객체({})로 보내도 진행중 공고 전부가 옵니다. 쪽 나눔이 없습니다.
2026-09-22 기준 14건이었고 화면과 같았습니다.

응답
----
    resultData.totalcount   전체 수
    resultData.list         공고 배열

공고 한 건의 칸

    unit_nm            코오롱생명과학(주)          계열사
    jobopen_nm         [코오롱생명과학(주)] 의약QA 신입/경력 채용
    field_nm           품질보증(QA)                직무
    experience         01 신입 / 02 경력 / 03 신입·경력
    receive_start_dt   20260921                  접수 시작(YYYYMMDD)
    receive_end_dt     20260929                  접수 마감
    jobopen_id         KLS202609210002
    difend             -6                        남은 날(음수로 옵니다)

계열사 거르기
-------------
그룹 채용이라 건설·패션·모빌리티 공고도 함께 옵니다. companies.json 의
affiliates 에 적은 계열사만 담습니다. 비워 두면 전부 담습니다.

상세 주소 — 2026-11-02 고침
--------------------------
처음에는 "폼 전송이라 개별 주소가 없다"고 적고 모두 목록으로 보냈습니다.
틀렸습니다. 목록을 누르면 주소창에 아무것도 안 남지만(공고 번호를 POST 로
보내기 때문입니다), 같은 번호를 **주소에 붙여도 똑같이 열립니다.**

    GET .../JobOpen320WebController/view.hr?jobopen_id=KPC202610200001

칸 이름이 목록 API 와 다릅니다. 목록은 jobopen_id 로 주는데 상세는
jobopen_id 만 받습니다. jobopenid(밑줄 없이)로 보내면 200 은 오지만
빈 화면이 옵니다. 2026-11-02 에 6건으로 확인했고 쿠키 없이도 열립니다.

없는 번호를 넣으면 404 입니다. 번호를 추측하지 말고 목록에서 받은 것만
쓰세요.

상세에서 더 얻는 것
-------------------
상세에 모집부문 표가 있습니다. 목록에는 없는 것들이 여기 있습니다.

    <table class="recruit_tb table_pc">
      <thead><tr><th>직무</th><th>경력/신입<br>구분</th><th>근무형태</th>
        <th>주요업무</th><th>모집분야내용</th><th>근무지</th><th>모집인원</th></tr></thead>
      <tbody><tr><td>생산관리</td><td>신입/경력</td><td>정규직</td>
        <td>조직분배은행 조직취급담당자</td>
        <td>[주요업무]<br>- 인체조직의 안전한 취급...</td>
        <td>대전</td><td>0명</td></tr> ... </tbody>
    </table>

본문·근무지·근무형태(고용형태)를 여기서 가져옵니다.

주의: 같은 표가 모바일용(table_mo)으로 한 번 더 나오고 그쪽은 칸이
하나 적습니다(직무 없음). class 에 table_pc 가 있는 것만 씁니다.

한 공고에 포지션이 여럿일 수 있습니다(지원팀 공고는 조직취급담당자·
행정담당자 2줄). 줄마다 <h3> 로 나눠 본문을 만들고 multiRole 을 켭니다.

코오롱제약 공고에도 표가 있습니다. 2026-11-02 에 4건 모두 확인했습니다.
이미지로 올린 공고는 없었습니다.
"""
import html
import json
import re
import time
import urllib.error
import urllib.request

BASE = "https://dream.kolon.com/RECRUIT_KOLON/hr/rec/recruit"
LIST_API = BASE + "/jobopen/controller/candidate/JobOpen310WebController/searchJobOpenByCandidate2018Renew.hr"
LIST_PAGE = BASE + "/main/controller/candidate/MainRecruitWebController/init.hr"
# 공고별 상세. 칸 이름은 jobopen_id 입니다(밑줄 없는 jobopenid 는 빈 화면).
DETAIL_URL = (BASE + "/jobopen/controller/candidate/JobOpen320WebController"
                     "/view.hr?jobopen_id={}")
# 공고당 쉬는 시간. 2026-10-28 결정에 따라 0.3초를 지킵니다.
DETAIL_GAP = 0.3

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# 경력 구분 코드. 화면 표시와 맞춰 확인한 값입니다(2026-09-22).
CAREER = {"01": "신입", "02": "경력", "03": "신입/경력"}

DATE = re.compile(r"^(\d{4})(\d{2})(\d{2})$")

# 상세의 모집부문 표. 모바일용(table_mo)은 칸이 하나 적어 PC용만 씁니다.
TABLE_PC = re.compile(
    r'<table[^>]*class="[^"]*\btable_pc\b[^"]*"[^>]*>(.*?)</table>', re.S | re.I)
TR = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)

# 표의 칸 순서. 2026-11-02 확인.
C_JOB, C_CAREER, C_EMP, C_ROLE, C_BODY, C_PLACE, C_HEAD = range(7)


def _post(body):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다."""
    req = urllib.request.Request(
        LIST_API, method="POST", data=json.dumps(body).encode(),
        headers={
            "User-Agent": UA,
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": LIST_PAGE,
        })
    last = None
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError:
            raise
        except Exception as e:
            last = e
            if i < 2:
                time.sleep(2 + i * 2)
    raise last


def _get(url):
    """상세 페이지를 받습니다. 일시적 실패만 쉬었다 다시 시도합니다."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": LIST_PAGE,
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
    s = re.sub(r"<[^>]+>", " ", str(s or ""))
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _lines(s):
    """<br> 로 끊어 줄 목록으로 만듭니다. 빈 줄은 버립니다."""
    s = re.sub(r"<br\s*/?>", "\n", str(s or ""), flags=re.I)
    s = re.sub(r"</(p|div|li|tr)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    out = []
    for ln in html.unescape(s).split("\n"):
        ln = re.sub(r"\s+", " ", ln).strip()
        if ln:
            out.append(ln)
    return out


def _to_html(lines):
    """줄 목록을 우리 상세 페이지에 넣을 HTML 로 만듭니다.

    '- ' 로 시작하는 줄은 목록으로, 나머지는 문단으로 묶습니다.
    """
    out, bullets = [], []

    def flush():
        if bullets:
            out.append("<ul>" + "".join(f"<li>{html.escape(b)}</li>"
                                        for b in bullets) + "</ul>")
            bullets.clear()

    for ln in lines:
        m = re.match(r"^[-·•‧∙*]\s*(.+)$", ln)
        if m:
            bullets.append(m.group(1).strip())
        else:
            flush()
            out.append(f"<p>{html.escape(ln)}</p>")
    flush()
    return "\n".join(out)


def _detail(no):
    """상세의 모집부문 표를 줄 목록으로 돌려줍니다. 없으면 빈 목록."""
    try:
        page = _get(DETAIL_URL.format(no))
    except Exception as e:
        print(f"      ! 코오롱 {no}: 상세를 받지 못했습니다 ({e})")
        return []
    m = TABLE_PC.search(page)
    if not m:
        return []
    rows = []
    for tr in TR.findall(m.group(1)):
        tds = TD.findall(tr)
        if len(tds) == 7:
            rows.append(tds)
    return rows


def _body(rows):
    """표의 줄마다 <h3>포지션</h3> + 내용으로 본문을 만듭니다."""
    parts = []
    for r in rows:
        head = _text(r[C_ROLE]) or _text(r[C_JOB])
        body = _to_html(_lines(r[C_BODY]))
        if head:
            parts.append(f"<h3>{html.escape(head)}</h3>")
        if body:
            parts.append(body)
    return "\n".join(parts)


def _one(rows, col, cap=3):
    """표의 한 칸을 모아 중복을 없앱니다. 너무 여러 값이면 비웁니다.

    값이 없으면 빈 문자열입니다. 화면에서 「기재되지 않음」으로 보입니다.
    여기서 지어내지 않습니다.
    """
    seen = []
    for r in rows:
        v = _text(r[col])
        if v and v not in seen:
            seen.append(v)
    if not seen or len(seen) > cap:
        return ""
    return ", ".join(seen)


def _date(v):
    """'20260921' → '2026-09-21'. 형식이 다르면 빈 문자열."""
    m = DATE.match(str(v or "").strip())
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def _career(row):
    code = str(row.get("experience") or "").strip()
    if code in CAREER:
        return CAREER[code]
    # 코드가 낯설면 제목에서 읽습니다. 그래도 모르면 무관입니다.
    t = _text(row.get("jobopen_nm"))
    has_new, has_exp = "신입" in t, "경력" in t
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
    """진행중 공고 목록. probe 용으로 밖에서도 씁니다."""
    j = _post({})
    data = j.get("resultData") or {}
    rows = data.get("list") or []
    if not rows:
        print(f"  ! 코오롱: 공고 목록이 비어 있습니다. "
              f"resultCode={j.get('resultCode')!r} {str(j.get('resultMsg') or '')[:40]}")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    rows = list_open(company.get("code"))

    # affiliates 에 적은 계열사만 담습니다.
    want = [_norm(a) for a in (company.get("affiliates") or []) if str(a).strip()]
    if want:
        before = len(rows)
        rows = [x for x in rows
                if any(w in _norm(x.get("unit_nm")) for w in want)]
        if before != len(rows):
            print(f"      · {name}: 계열사 거르기 {before}건 → {len(rows)}건")

    jobs = []
    for x in rows:
        no = str(x.get("jobopen_id") or "").strip()
        title = _text(x.get("jobopen_nm"))
        if not no or not title:
            continue

        # 제목에 직무가 없으면 뒤에 붙입니다. 어떤 자리인지 보이게 합니다.
        field = _text(x.get("field_nm"))
        if field and field not in title:
            title = f"{title} · {field}"

        # 상세를 한 단계 들어갑니다. 본문·근무지·고용형태가 여기 있습니다.
        rows = _detail(no)
        if rows:
            time.sleep(DETAIL_GAP)

        jobs.append({
            "id": f"kolon-{re.sub(r'[^A-Za-z0-9]', '', no)[:24]}",
            "unit": "공고",
            "company": _text(x.get("unit_nm")) or name,
            "companySlug": slug,
            "title": title,
            # 상세 표의 근무지. 없으면 비웁니다(화면에서 「기재되지 않음」).
            "location": _one(rows, C_PLACE),
            "career": _career(x),
            "employment": _one(rows, C_EMP),
            "postedAt": _date(x.get("receive_start_dt")),
            "closesAt": _date(x.get("receive_end_dt")),
            "dday": None,
            # 표가 두 줄 이상이면 한 공고에 포지션이 여럿입니다.
            "multiRole": len(rows) > 1,
            "sourceTitle": "",
            # 공고별 주소. 2026-11-02 부터 목록이 아니라 그 공고로 갑니다.
            "sourceUrl": DETAIL_URL.format(no),
            "description": _body(rows),
        })
    return jobs
