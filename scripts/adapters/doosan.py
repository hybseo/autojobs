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

한계
----
- 목록에 본문이 없습니다. 상세는 자바스크립트로 열려 주소를 만들 수
  없어, 목록 페이지로 링크합니다. 잘못된 본문을 지어내지 않습니다.
- 그래서 자체 상세 페이지도 만들어지지 않습니다.
"""
import re
import html
import urllib.request

LIST_URL = "https://career.doosan.com/dsp/sa/RecList.jsp"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

CAREER = {"경력": "경력", "신입/인턴십": "신입",
          "전문/생산/계약직": "무관", "신입": "신입"}

# 한 공고 줄에서 필요한 조각을 뽑습니다.
#   <계열사> <구분> <제목> <D-29|금일마감> <YYYY-MM-DD> ~ <YYYY-MM-DD>
# 계열사명에 공백은 들어가도 줄바꿈은 안 들어갑니다.
# \s 를 쓰면 앞줄 꼬리("입사지원")까지 먹습니다. 실제로 그랬습니다.
# 그래서 줄바꿈을 뺀 [^\S\n] 를 씁니다.
ROW = re.compile(
    r"(?P<co>[가-힣A-Za-z()\u3000\-·][^\n]{0,28}?)[^\S\n]+"
    r"(?P<cls>경력|신입/인턴십|전문/생산/계약직|신입)[^\S\n]+"
    r"(?P<title>[^\n]+?)[^\S\n]+"
    r"(?P<dday>금일마감|마감|D-\d+)[^\S\n]+"
    r"(?P<start>\d{4}-\d{2}-\d{2})[^\S\n]*~[^\S\n]*(?P<end>\d{4}-\d{2}-\d{2})")


def _get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def _text(raw):
    """HTML 을 줄 단위 텍스트로 폅니다."""
    s = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.S | re.I)
    s = re.sub(r"<style[^>]*>.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"</(li|tr|div|p)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"[ \t\u3000]+", " ", s)


def _dday(v):
    """'D-29' → 29, '금일마감' → 0. 부호를 그대로 읽으면 음수가 됩니다."""
    t = str(v or "")
    if "금일" in t or t == "마감":
        return 0
    m = re.search(r"\d+", t)
    return int(m.group(0)) if m else None


def list_open(affiliates=()):
    """접수중 공고 목록. probe 용으로 밖에서도 씁니다."""
    text = _text(_get(LIST_URL))
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
        })

    if not rows:
        # HTML 파싱이라 화면이 바뀌면 조용히 0건이 됩니다. 그러면 원인을
        # 알 수 없으므로 반드시 알립니다.
        print(f"      ! 두산: 공고를 하나도 찾지 못했습니다. "
              f"화면 구조가 바뀌었을 수 있습니다. {LIST_URL} 를 확인하세요.")
        return []

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

        jobs.append({
            "id": f"doosan-{jid}",
            "unit": "공고",
            # 계열사명을 그대로 씁니다. "두산" 으로 뭉치면 어느 회사인지 모릅니다.
            "company": x["company"],
            "companySlug": slug,
            "title": x["title"],
            "location": "",
            "career": CAREER.get(x["career"], "무관"),
            "postedAt": x["start"],
            "closesAt": x["end"],
            "dday": _dday(x["dday"]),
            "multiRole": False,
            "sourceTitle": "",
            # 상세가 자바스크립트로 열려 개별 주소를 만들 수 없습니다.
            "sourceUrl": LIST_URL,
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })
    return jobs
