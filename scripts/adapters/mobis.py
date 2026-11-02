# -*- coding: utf-8 -*-
"""
현대모비스 자체 채용사이트(careers.mobis.com) 수집기.

왜 따로 만들었나
----------------
현대모비스는 리크루터(mobis.recruiter.co.kr)와 자체 사이트를 같이 씁니다.
공고 수는 같은데(2026-11-02 둘 다 3건) 내용이 전혀 다릅니다.

  리크루터가 주는 것          자체 사이트가 주는 것
  ------------------------    ----------------------------------
  공고 제목·접수기간           같음
  본문                        본문 (한글)
    ↳ 25건 전부 영문입니다!
  근무지 없음                 근무장소 (역삼본사·의왕연구소 …)
  세부 직무 없음               세부 직무 (로보틱스 사업/제품 기획 …)
  직무 분류 없음               직무 대·소분류 (기획 / 경영전략·신사업기획)

2026-11-02 에 우리가 가진 모비스 25건의 본문을 세어 보니 한글이 0~168자,
영문이 8,000~15,000자였습니다. 구직자가 읽을 수 없는 본문을 요약하고 있었던
셈입니다. 그래서 담당업무가 0건인 요약이 3건 중 2건이었습니다.

  mobis-131838  담당업무 0건 · 근무지 "서울 본사"
  mobis-132656  담당업무 0건 · 근무지 "서울 (본문에 HQ(Seoul)로 적혀 있습니다)"

이 수집기는 **리크루터를 뼈대로 쓰고 자체 사이트 값을 덮습니다.**
그래서 공고 id(mobis-131838)와 /job/{id}/ 주소가 그대로 유지됩니다.
(2026-11-02 결정: 직무 단위로 쪼개지 않고 공고 단위를 유지한다)

짝짓는 열쇠 — 공고 제목
-----------------------
두 쪽에 공통 번호가 없습니다. 자체 사이트는 jobnoticeSn(269846)을,
리크루터 API 는 positionSn(131838)을 씁니다. 상세 페이지를 열어 봐도
서로의 번호가 안 적혀 있습니다. 확인한 것:

  careers.mobis.com  fnApply(".../login?jobnoticeSn=269846&...")
  mobis.recruiter.co.kr/career/jobs/131838  → 269846 이 없음

대신 **공고 제목이 글자 하나까지 같습니다.** 2026-11-02 기준 3건 모두
완전히 일치했습니다.

  [로보틱스사업실] 26년 10월 관리직 경력채용 (Robotics Business Group, senior-admin.)

그래서 공백만 접은 제목으로 짝짓습니다. 짝을 못 찾은 공고는 **리크루터
값을 그대로 둡니다.** 지어내지 않고, 대신 경고를 찍습니다.

목록 화면 구조 (2026-11-02 확인)
--------------------------------
한 공고가 직무별로 여러 줄로 나뉘어 나옵니다. 4줄이 공고 3건이었습니다.

  <li>
  <a href="/jobs-view?seq=4211" class="job-item">
    <div class="info-wrap01">
      <p class="dday">D-1</p>
      <p class="career">경력-관리직</p>      ← 채용구분
      <p class="integrated">[로보틱스사업실] 26년 10월 …</p>  ← 공고 제목
    </div>
    <p class="tit">로보틱스 사업/제품 기획</p>  ← 세부 직무
    <div class="info-wrap02">
      <p>로보틱스사업실</p>      조직(사업부)
      <p>기획</p>                직무 대분류
      <p>경영전략/신사업기획</p>  직무 소분류
      <p>역삼본사</p>            근무장소
    </div>
    <p class="date">2026-10-22 - 2026-11-03 10:00</p>
  </a>
  …
  <a class="btn-layer btn-collect" onclick="javascript:fnCollectSearch(269846);"></a>
  </li>

함정 1 — <li> 로 자르지 마세요
  공유 버튼이 <li> 를 또 씁니다. jobList 안에 <li> 가 58개인데 공고는
  4개입니다. 반드시 `<a href="/jobs-view?seq=N" class="job-item">` 로 자릅니다.

함정 2 — jobs-view 링크가 9군데 있습니다
  아래쪽 홍보 띠에 절대주소(https://careers.mobis.com/jobs-view?seq=1814)가
  3개, 자바스크립트 템플릿에 2개 더 있습니다. 전부 지난 공고이거나 틀
  입니다. 상대주소 + class="job-item" 을 같이 걸면 정확히 4개만 걸립니다.

함정 3 — 필터 목록은 HTML 에 없습니다
  근무장소 16곳·직무 68종 목록은 자바스크립트가 채웁니다. 원본 HTML 에는
  "전체" 하나뿐입니다. 그래서 아래 PLACES 에 2026-11-02 에 화면에서
  확인한 16곳을 적어 두고 점검에만 씁니다.

상세 화면 구조 (2026-11-02 확인)
--------------------------------
  <div class="paragraph">
    <p class="tit group">조직소개</p>
    <div class="sentence">…</div>
  </div>
  … job(직무상세) / qualify(지원자격) / special(우대사항)
  … step(전형절차) / etc(기타) / keyword(키워드, ul.keyword-wrap)

전형절차와 기타는 담지 않습니다. 안내문이라 요약에 쓸 것이 없고, 넣으면
요약이 "지원서 접수 후 인적성검사" 같은 말로 채워집니다. 키워드는 담습니다
(#사업전략 #제품기획 — 태그 뽑는 데 씁니다).

robots.txt (2026-11-02 확인)
---------------------------
  User-agent: *
  Allow: /
  Disallow: /jobs_private-view
  Disallow: /jobs_private

/jobs 와 /jobs-view 는 허용입니다. 막힌 두 곳은 건드리지 않습니다.
직무마다 상세를 한 번 더 받으므로 0.3초씩 쉽니다.

쪽 나눔에 대하여
----------------
쪽 나눔 흔적이 HTML 에 없습니다(pageIndex·pageNo·btn-more 모두 없음).
서버가 한 번에 전부 그리는 것으로 보이지만, 확인 시점에 공고가 4건뿐이라
많을 때도 그런지는 확인하지 못했습니다. 그래서 화면에 적힌
"N 개의 채용 공고가 현재 진행중입니다" 의 N 과 실제로 읽은 줄 수를 비교해
다르면 경고를 찍습니다. 경고가 보이면 쪽 나눔을 찾아야 합니다.
"""
import html
import re
import time
import urllib.error
import urllib.request

try:
    from . import recruiter
except ImportError:          # 패키지 밖에서 직접 돌릴 때
    import recruiter

BASE = "https://careers.mobis.com"
LIST = BASE + "/jobs"
VIEW = BASE + "/jobs-view?seq={}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

GAP = 0.3                    # 상세를 받을 때마다 쉬는 시간(초)

# 공고 한 줄. 상대주소 + class="job-item" 을 같이 걸어야 홍보 띠의
# 절대주소와 자바스크립트 템플릿이 안 걸립니다. 함정 2 참고.
ITEM = re.compile(
    r'<a\s+href="/jobs-view\?seq=(\d+)"\s+class="job-item">'   # 1 seq
    r'(.*?)</a>'                                               # 2 카드 속
    r'(.*?)'                                                   # 3 카드 뒤(공유·담기)
    r'(?=<a\s+href="/jobs-view\?seq=\d+"\s+class="job-item">|\Z)',
    re.S)

P_DDAY = re.compile(r'<p class="dday">(.*?)</p>', re.S)
P_CAREER = re.compile(r'<p class="career">(.*?)</p>', re.S)
P_TITLE = re.compile(r'<p class="integrated">(.*?)</p>', re.S)
P_ROLE = re.compile(r'<p[^>]*class="tit"[^>]*>(.*?)</p>', re.S)
P_DATE = re.compile(r'<p class="date">(.*?)</p>', re.S)
P_INFO2 = re.compile(r'<div class="(?:info|view)-wrap02">(.*?)</div>', re.S)
P_CELL = re.compile(r'<p[^>]*>(.*?)</p>', re.S)
P_NOTICE = re.compile(r'fnCollectSearch\((\d+)\)')
P_TOTAL = re.compile(r'(\d+)\s*개의\s*채용\s*공고')
DATE = re.compile(r'(\d{4})-(\d{2})-(\d{2})')

# 상세의 칸 제목. class 이름이 열쇠입니다(제목 글자는 바뀔 수 있습니다).
P_TIT = re.compile(r'<p class="tit ([a-z0-9_-]+)">')
P_KEYWORDS = re.compile(r'<ul class="keyword-wrap">(.*?)</ul>', re.S)
P_LI = re.compile(r'<li[^>]*>(.*?)</li>', re.S)
# div 짝을 세기 위한 것. 정규식만으로는 중첩을 셀 수 없습니다.
SENTENCE_OPEN = '<div class="sentence">'
P_DIV_EDGE = re.compile(r'<(/?)div\b')

# 담을 칸과 화면에 쓸 소제목. 순서대로 붙입니다.
# step(전형절차)·etc(기타)는 안내문이라 담지 않습니다.
KEEP = (("group", "조직 소개"),
        ("job", "담당 업무"),
        ("qualify", "지원 자격"),
        ("special", "우대 사항"),
        ("keyword", "키워드"))

# 2026-11-02 에 화면 필터에서 확인한 근무장소 16곳. 점검에만 씁니다.
# 목록이 자바스크립트로 채워져 원본 HTML 에 없기 때문입니다(함정 3).
PLACES = {
    "마북연구소", "의왕연구소", "강남연구소", "서산주행시험장", "진천공장",
    "창원공장", "울산공장", "물류센터", "부품사업소", "김천사무소",
    "역삼본사", "아산사무소", "부품팀", "부천파워모듈랩", "남양연구소",
    "대구공장",
}
# 새 공장·사무소가 생겨도 받아들이되, 직무 이름이 자리를 밀고 들어온 것은
# 거릅니다. 확인한 16곳은 모두 아래 꼬리말로 끝나고, 직무 68종·사업부
# 21종 중에는 이 꼬리말로 끝나는 것이 하나도 없었습니다.
PLACE_TAIL = re.compile(r"(본사|연구소|공장|사무소|센터|사업소|시험장|랩|팀)$")

# 채용구분(p.career) → 고용형태. 고용형태를 말하지 않는 값은 비웁니다.
# 「경력-관리직」은 정규직이라고 쓰여 있지 않으므로 지어내지 않습니다.
# 화면에서 확인한 값: 신입-관리직·신입-연구직·경력-관리직·경력-연구직·
#                     신입-현장직·인턴·장학생·계약직·기타
EMPLOYMENT = ((re.compile(r"계약직"), "계약직"),
              (re.compile(r"인턴"), "인턴"))


def _get(url):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다. 4xx/5xx 는 그대로 올립니다."""
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
    """태그를 떼고 공백을 접습니다."""
    s = re.sub(r"<[^>]+>", " ", str(s or ""))
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def _key(title):
    """짝짓기용 열쇠. 공백만 접고 나머지는 그대로 둡니다.

    대소문자를 접지 않습니다. 모비스 제목에는 senior-admin. / Senior-res.
    처럼 대소문자가 뜻을 가르는 자리가 있어서, 접으면 서로 다른 공고가
    같은 열쇠가 될 위험이 있습니다.
    """
    return re.sub(r"\s+", " ", _text(title)).strip()


def _place(cells):
    """info-wrap02 네 칸에서 근무장소를 꺼냅니다.

    칸 순서는 조직 / 직무 대분류 / 직무 소분류 / 근무장소 입니다.
    네 칸이 아니거나 마지막 칸이 장소 같지 않으면 **비웁니다.**
    근무지를 추측해 채우지 않기로 한 규칙을 따릅니다.
    """
    if len(cells) != 4:
        return "", f"칸이 4개가 아니라 {len(cells)}개입니다"
    v = cells[3]
    if v in PLACES or PLACE_TAIL.search(v):
        return v, ""
    return "", f"근무장소 같지 않은 값 「{v}」"


def _employment(career_label):
    for pat, val in EMPLOYMENT:
        if pat.search(career_label or ""):
            return val
    return ""


def _career(labels):
    """채용구분 모음에서 신입/경력을 읽습니다. 못 읽으면 빈 문자열."""
    t = " ".join(labels or [])
    new = "신입" in t
    exp = "경력" in t
    if new and exp:
        return "신입/경력"
    if exp:
        return "경력"
    if new:
        return "신입"
    return ""


def _date(v):
    m = DATE.search(str(v or ""))
    return m.group(0) if m else ""


def list_roles():
    """자체 사이트 목록에서 직무 한 줄씩을 읽습니다. probe 용으로도 씁니다."""
    page = _get(LIST)
    rows = []
    for seq, inner, tail in ITEM.findall(page):
        m2 = P_INFO2.search(inner)
        cells = [c for c in (_text(x) for x in P_CELL.findall(
            m2.group(1) if m2 else "")) if c]
        place, why = _place(cells)
        if why:
            print(f"      ! 모비스 seq {seq}: 근무장소를 비웁니다 — {why}")
        m = P_TITLE.search(inner)
        mr = P_ROLE.search(inner)
        md = P_DATE.search(inner)
        mc = P_CAREER.search(inner)
        mn = P_NOTICE.search(tail)
        rows.append({
            "seq": seq,
            "noticeSn": mn.group(1) if mn else "",
            "title": _text(m.group(1)) if m else "",
            "role": _text(mr.group(1)) if mr else "",
            "careerLabel": _text(mc.group(1)) if mc else "",
            "org": cells[0] if cells else "",
            "jobGroup": cells[1] if len(cells) > 1 else "",
            "jobName": cells[2] if len(cells) > 2 else "",
            "place": place,
            "dates": _text(md.group(1)) if md else "",
        })

    mt = P_TOTAL.search(_text(page))
    if mt and int(mt.group(1)) != len(rows):
        print(f"      ! 모비스: 화면은 {mt.group(1)}건이라는데 {len(rows)}줄만 "
              f"읽었습니다. 쪽 나눔이 생겼는지 확인이 필요합니다.")
    if not rows:
        print(f"      ! 모비스: 공고를 한 줄도 읽지 못했습니다. {LIST} 를 "
              f"확인하세요. 받은 HTML {len(page)}자.")
    return rows


def _sentence(chunk):
    """<div class="sentence"> 안쪽을 통째로 꺼냅니다.

    이 칸 안에 <div> 가 또 들어 있습니다. 그래서 정규식으로 첫 </div> 까지
    자르면 안 됩니다. 실제로 그렇게 했을 때 직무상세가 이렇게 잘렸습니다.

      자른 결과  "・로보틱스 사업/제품기획"                     13자
      실제 내용  "・로보틱스 사업/제품기획 - 중장기 전략 수립 …"  226자

    담당 업무가 통째로 날아가는 자리입니다. <div> 와 </div> 를 세어
    짝이 맞는 곳에서 끊습니다.
    """
    i = chunk.find(SENTENCE_OPEN)
    if i < 0:
        return ""
    j = i + len(SENTENCE_OPEN)
    depth = 1
    for m in P_DIV_EDGE.finditer(chunk, j):
        if m.group(1):                 # </div
            depth -= 1
            if depth == 0:
                return chunk[j:m.start()].strip()
        else:
            depth += 1
    return ""                          # 짝이 안 맞으면 버립니다


def _detail(seq):
    """직무 하나의 상세에서 칸들을 꺼냅니다. 실패하면 빈 dict.

    칸 제목(<p class="tit job">)부터 다음 칸 제목까지를 한 덩어리로 보고
    그 안에서 내용을 꺼냅니다. 2026-11-02 확인 기준 칸은 group·job·
    qualify·special·step·etc·keyword·result 여덟 가지였습니다
    (result 는 아래쪽 추천공고 제목이고 내용이 없습니다).
    """
    try:
        page = _get(VIEW.format(seq))
    except Exception as e:
        print(f"      ! 모비스 seq {seq}: 상세를 받지 못했습니다 ({e})")
        return {}

    tits = list(P_TIT.finditer(page))
    out = {}
    for n, m in enumerate(tits):
        end = tits[n + 1].start() if n + 1 < len(tits) else len(page)
        chunk = page[m.start():end]
        cls = m.group(1)
        if cls == "keyword":
            mk = P_KEYWORDS.search(chunk)
            words = [_text(x) for x in P_LI.findall(mk.group(1))] if mk else []
            out[cls] = ", ".join(w for w in words if w)
        else:
            out[cls] = _sentence(chunk)
    return out


def _body(roles):
    """공고 하나의 본문 HTML 을 만듭니다.

    직무가 여럿이면 직무 이름을 소제목으로 달아 이어 붙입니다. 리크루터
    본문은 두 직무를 한 덩어리로 줘서 요약이 담당업무를 못 뽑았습니다.
    여기서 직무별로 나눠 주면 그 문제가 사라집니다.
    """
    many = len(roles) > 1
    out = []
    for r in roles:
        parts = []
        for cls, label in KEEP:
            v = (r.get("detail") or {}).get(cls) or ""
            if len(_text(v)) < 2:
                continue
            parts.append(f"<h4>{html.escape(label)}</h4>")
            # sentence 는 이미 HTML 입니다. 키워드는 우리가 만든 글입니다.
            parts.append(v if cls != "keyword" else "<p>" + html.escape(v) + "</p>")
        if not parts:
            continue
        if many and r.get("role"):
            out.append(f"<h3>{html.escape(r['role'])}</h3>")
        out += parts
    return "\n".join(out)


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다.

    리크루터가 뼈대(id·주소·날짜), 자체 사이트가 내용(본문·근무지·고용형태)입니다.
    """
    # 1) 뼈대. id 와 sourceUrl 이 예전과 같아야 하므로 리크루터를 그대로 씁니다.
    jobs = recruiter.fetch(company)
    if not jobs:
        print("      ! 모비스: 리크루터에서 공고를 받지 못했습니다. "
              "자체 사이트 값만으로는 공고 id 를 만들 수 없어 그대로 둡니다.")
        return jobs

    # 2) 자체 사이트에서 직무 줄을 받아 공고별로 묶습니다.
    try:
        rows = list_roles()
    except Exception as e:
        print(f"      ! 모비스: 자체 사이트를 읽지 못했습니다 ({e}). "
              f"리크루터 값만 씁니다.")
        return jobs

    groups = {}
    for r in rows:
        if not r["title"]:
            continue
        groups.setdefault(_key(r["title"]), []).append(r)

    # 3) 직무마다 상세를 받습니다.
    for r in rows:
        r["detail"] = _detail(r["seq"])
        time.sleep(GAP)

    # 4) 제목으로 짝지어 덮습니다.
    matched = set()
    for j in jobs:
        g = groups.get(_key(j["title"]))
        if not g:
            print(f"      ! 모비스: 자체 사이트에서 짝을 못 찾았습니다 — "
                  f"{j['id']} 「{_text(j['title'])[:40]}」. 리크루터 값을 둡니다.")
            continue
        matched.add(_key(j["title"]))

        body = _body(g)
        if len(_text(body)) >= 50:
            j["description"] = body
            j["multiRole"] = False     # 직무를 전부 읽었습니다.
        else:
            print(f"      ! 모비스 {j['id']}: 자체 사이트 본문이 "
                  f"{len(_text(body))}자뿐입니다. 리크루터 본문을 둡니다.")

        # 근무장소. 직무마다 다를 수 있어 중복을 지운 뒤 이어 붙입니다.
        places = []
        for r in g:
            if r["place"] and r["place"] not in places:
                places.append(r["place"])
        if places:
            j["location"] = " · ".join(places)

        emp = ""
        for r in g:
            emp = emp or _employment(r["careerLabel"])
        if emp:
            j["employment"] = emp

        car = _career([r["careerLabel"] for r in g])
        if car:
            j["career"] = car

        # 접수기간이 어긋나면 알려 둡니다. 날짜는 리크루터 값을 씁니다.
        site_close = ""
        for r in g:
            d = DATE.findall(r["dates"])
            if len(d) > 1:
                site_close = "-".join(d[-1])
                break
        if site_close and j.get("closesAt") and site_close != j["closesAt"]:
            print(f"      ! 모비스 {j['id']}: 마감일이 다릅니다 — "
                  f"리크루터 {j['closesAt']} / 자체 사이트 {site_close}")

    left = [k for k in groups if k not in matched]
    if left:
        print(f"      ! 모비스: 자체 사이트에만 있는 공고 {len(left)}건 — "
              f"{[k[:34] for k in left]}. 리크루터에 없어 담지 못했습니다.")

    done = len(matched)
    print(f"      · 모비스: 공고 {len(jobs)}건 중 {done}건에 자체 사이트 "
          f"내용을 덮었습니다(직무 {len(rows)}개).")
    return jobs
