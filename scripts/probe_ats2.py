# -*- coding: utf-8 -*-
"""
회사 이름으로 ATS 주소를 직접 두드려 찾습니다.

  python scripts/probe_ats2.py --names scripts/names_pharma.txt
  python scripts/probe_ats2.py --names list.txt --limit 20     앞 20개만
  python scripts/probe_ats2.py --names list.txt --all          이미 등록된 곳도

결과는 화면과 scripts/probe_ats2_result.csv 에 남습니다. 아무것도 자동으로
등록하지 않습니다. 결과를 보고 사람이 companies.json 에 옮겨 적으세요.

probe_ats1.py 와 무엇이 다른가
------------------------------
1번은 회사 홈페이지를 열고 채용 링크를 따라갑니다. 그래서 홈페이지에 링크가
없으면 놓칩니다.

    뉴로메카  홈페이지의 "수시채용 공고보기" → 사람인
              그런데 neuromeka1.career.greetinghr.com 에 9건이 따로 있었습니다

2026-09-11 작업에서 이렇게 놓친 곳이 여럿이었습니다. 사람이 하나씩 찾아
알려줘야 했습니다.

이 스크립트는 반대로 갑니다. 회사 이름에서 주소 후보를 만들어 ATS 를 직접
두드립니다. 홈페이지를 보지 않으므로 링크가 없어도 찾습니다.

둘은 서로를 대신하지 않습니다
    1번이 잘하는 것   자체 도메인(career.hyundai-autoever.com 같은)
    2번이 잘하는 것   홈페이지에 링크가 없는 경우
둘 다 돌리고 합치는 것이 가장 확실합니다.

이름 후보를 어떻게 만드는가
---------------------------
2026-09-11 에 실제로 만난 사례에서 규칙을 뽑았습니다.

    뉴로메카      neuromeka1         숫자를 붙입니다
    파마리서치     pharmaresearch_hr  밑줄과 hr
    클래시스      classyshr          hr 를 붙입니다
    씨메스       cmesairobotics     사업 이름을 씁니다
    로보티즈      robotisrecruiter   recruiter 를 붙입니다

앞의 넷은 규칙으로 만들 수 있습니다. 마지막처럼 회사명과 아예 다른 경우는
규칙으로 못 만드니, 목록 파일에 별칭을 적어 주세요(아래 형식 참고).

목록 파일 형식
--------------
    회사명,영문이름[,별칭1,별칭2...]

    뉴로메카,neuromeka
    씨메스로보틱스,cmes,cmesairobotics
    파마리서치,pharmaresearch

영문이름이 없으면 한글만 적어도 됩니다. 그때는 흔한 로마자 표기를 몇 개
만들어 보지만 정확도가 떨어집니다. 되도록 영문이름을 적어 주세요.

한 회사에 몇 번 두드리는가
--------------------------
후보 10개 안팎 × ATS 4곳 = 40번쯤입니다. 회사당 20초 정도 걸립니다.
50개사면 15분쯤 봅니다.

서버에 부담을 주지 않도록 후보마다 쉽니다. 한 ATS 에서 찾으면 그 회사는
거기서 멈춥니다.

찾은 뒤에 확인할 것
-------------------
공고 수가 0 이면 주소는 맞는데 지금 채용을 안 하는 것입니다. 등록해 두면
나중에 공고가 열릴 때 자동으로 잡힙니다.

간혹 이름이 비슷한 다른 회사가 잡힙니다. CSV 의 title 칸에 사이트 제목을
적어 두니 회사명과 맞는지 보고 옮겨 적으세요.
"""
import argparse
import csv
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "probe_ats2_result.csv"
REGISTRY = ROOT / "src" / "data" / "companies.json"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# 없는 주소가 대부분입니다. 오래 기다려봐야 어차피 실패합니다.
#
# 2026-09-15 로봇 33곳을 돌리는 데 53분이 걸렸습니다. 그중 42분이
# 응답을 기다린 시간이었습니다(타임아웃 8초 × 없는 주소 수백 개).
# 4초로 줄여도 살아 있는 주소는 그 안에 답합니다.
TIMEOUT = 4

# 두드리는 사이 쉬는 시간. 서버에 부담을 주지 않으려는 것인데,
# 후보가 수천 개라 0.25초씩만 쉬어도 10분이 넘습니다.
# 도메인이 제각각이라 한 서버에 몰리지 않습니다.
PAUSE = 0.08

# 흔한 한글 → 로마자. 영문이름을 안 적었을 때만 씁니다.
ROMAN = {
    "로보틱스": "robotics", "테크": "tech", "바이오": "bio", "제약": "pharm",
    "전자": "electronics", "산업": "industry", "정밀": "precision",
    "소재": "materials", "화학": "chem", "시스템": "system",
    "솔루션": "solution", "메디": "medi", "케어": "care", "랩": "lab",
}


def _norm(s):
    return re.sub(r"[\s\-_()㈜\.]|주식회사", "", str(s or "")).lower()


def name_guesses(korean, english, extra):
    """회사 이름에서 하위도메인 후보를 만듭니다.

    실제로 만난 형태만 넣습니다. 후보를 늘릴수록 오래 걸리고 엉뚱한 회사가
    잡힐 확률도 올라갑니다.
    """
    seeds = []
    for x in [english] + list(extra or []):
        x = _norm(x)
        if x and x not in seeds:
            seeds.append(x)

    # 영문이름을 안 적었으면 한글에서 만들어 봅니다. 정확도가 떨어집니다.
    if not seeds and korean:
        k = korean
        for ko, en in ROMAN.items():
            k = k.replace(ko, en)
        k = _norm(k)
        if re.fullmatch(r"[a-z0-9]+", k or ""):
            seeds.append(k)

    out = []
    for s in seeds:
        # 실제로 맞았던 형태만 남깁니다.
        #
        # 후보 하나가 ATS 네 곳에 곱해지므로, 열 개를 여섯 개로 줄이면
        # 두드리는 횟수가 40% 줄어듭니다. 2026-09-15 까지 찾은 회사를
        # 보면 아래 여섯 가지 안에 다 들어갑니다.
        #
        # -hr, career, careers, corp 는 한 번도 맞은 적이 없어 뺐습니다.
        # 특이한 주소를 쓰는 곳은 목록 파일에 별칭으로 적으세요.
        for c in (s,                    # neuromeka
                  s + "1",              # neuromeka1
                  s + "hr",             # classyshr
                  s + "_hr",            # pharmaresearch_hr
                  s + "recruit",
                  s + "recruiter"):     # robotisrecruiter
            if c not in out:
                out.append(c)
    return out


def _get(url, timeout=TIMEOUT):
    """열리면 (본문, 최종주소), 아니면 (None, 사유)."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json",
        "Accept-Language": "ko-KR,ko;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace"), r.geturl()
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, str(e)[:40]


def _is_closed(sub):
    """채용 사이트를 닫은 곳인지 봅니다.

    리크루터는 회사가 계약을 끝내도 주소를 지우지 않습니다. 그래서 주소는
    응답하는데 안에는 아무것도 없습니다. list.json 도 빈 목록을 200 으로
    돌려주기 때문에 "찾았다" 로 잘못 세게 됩니다.

    2026-09-12 전기전자 탐지에서 이런 곳이 열넷이었습니다. LX세미콘·대덕전자·
    유진테크·파크시스템스처럼 예전에 쓰다가 그만둔 흔적만 남은 주소들입니다.
    하나씩 열어 확인하느라 시간을 썼습니다.

    닫힌 곳은 목록 화면을 열면 /appsite/company/error 로 넘깁니다.
    그것만 보면 구분됩니다.
    """
    try:
        req = urllib.request.Request(
            f"https://{sub}.recruiter.co.kr/app/jobnotice/list",
            headers={"User-Agent": UA, "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return "/error" in r.geturl()
    except Exception:
        # 확인 자체가 안 되면 닫혔다고 단정하지 않습니다. 살아 있는데
        # 일시적으로 응답이 늦은 것일 수 있습니다.
        return False


def _title(html):
    m = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.S | re.I)
    if not m:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip()[:60]


# ── ATS 별 확인 방법 ───────────────────────────────────────────────
# 각 함수는 (찾았는가, 공고수, 사이트제목) 을 돌려줍니다.
# 주소가 살아 있어도 빈 껍데기인 경우가 있어 공고 데이터까지 봐야 합니다.

def try_greeting(sub):
    url = f"https://{sub}.career.greetinghr.com/ko"
    html, _ = _get(url)
    if not html or "__NEXT_DATA__" not in html:
        return None
    m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(1))
        qs = (((d.get("props") or {}).get("pageProps") or {})
              .get("dehydratedState") or {}).get("queries") or []
        op = next((q for q in qs if (q.get("queryKey") or [""])[0] == "openings"), None)
        raw = ((op or {}).get("state") or {}).get("data")
        rows = list(raw.values()) if isinstance(raw, dict) else list(raw or [])
    except Exception:
        return None
    return {"ats": "greeting", "code": sub, "n": len(rows),
            "url": f"https://{sub}.career.greetinghr.com", "title": _title(html)}


def try_recruiter(sub):
    """신버전과 구버전을 함께 봅니다. 둘은 code 가 같고 ats 만 다릅니다."""
    body = json.dumps({
        "pageableRq": {"page": 1, "size": 200, "sort": ["END_DATE_TIME"]},
        "filter": {"keyword": "", "tagSnList": [], "jobGroupSnList": [],
                   "careerTypeList": [], "regionSnList": [],
                   "submissionStatusList": [], "openStatusList": [],
                   "resumeLanguageTypeList": []}}).encode()
    req = urllib.request.Request(
        "https://api-recruiter.recruiter.co.kr/position/v1/jobflex",
        method="POST", data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "prefix": f"{sub}.recruiter.co.kr", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            j = json.load(r)
        rows = j.get("list") or []
        live = [x for x in rows if x.get("submissionStatus") == "IN_SUBMISSION"]
        # 공고가 하나도 없으면 사이트를 닫았을 수 있습니다. 그때만 확인합니다.
        # 공고가 있으면 살아 있는 것이 확실하니 요청을 아낍니다.
        if not rows and _is_closed(sub):
            return None
        return {"ats": "recruiter", "code": sub, "n": len(live),
                "url": f"https://{sub}.recruiter.co.kr/career/home", "title": ""}
    except Exception:
        pass

    # 신버전이 400 이면 구버전일 수 있습니다. form 으로 보내야 합니다.
    data = urllib.parse.urlencode({
        "recruitClassSn": "", "recruitClassName": "", "jobnoticeStateCode": "10",
        "pageSize": "100", "searchByNameOnly": "true", "currentPage": "1"}).encode()
    req = urllib.request.Request(
        f"https://{sub}.recruiter.co.kr/app/jobnotice/list.json",
        method="POST", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                 "Accept": "application/json", "X-Requested-With": "XMLHttpRequest",
                 "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            j = json.load(r)
        rows = j.get("list") or []
        live = [x for x in rows if str(x.get("receiptState") or "").strip() == "접수중"]
        if not rows and _is_closed(sub):
            return None
        return {"ats": "recruiter_v1", "code": sub, "n": len(live),
                "url": f"https://{sub}.recruiter.co.kr/app/jobnotice/list", "title": ""}
    except Exception:
        return None


def try_ninehire(sub):
    """companyId 를 알아야 공고를 셀 수 있어 화면에서 먼저 찾습니다."""
    html, _ = _get(f"https://{sub}.ninehire.site/")
    if not html or "ninehire" not in html.lower():
        return None
    m = re.search(r"companyId=([0-9a-f\-]{30,40})", html)
    cid = m.group(1) if m else ""
    n = ""
    if cid:
        j, _ = _get(f"https://{sub}.ninehire.site/_backend/identity-access"
                    f"/homepage/recruitments?companyId={cid}&page=1&countPerPage=100")
        try:
            data = json.loads(j or "{}")
            n = len([x for x in (data.get("results") or [])
                     if x.get("status") == "in_progress"])
        except Exception:
            n = ""
    return {"ats": "ninehire", "code": f"{sub},{cid}" if cid else sub,
            "n": n, "url": f"https://{sub}.ninehire.site/", "title": _title(html)}


def try_workday(sub):
    """서버 번호가 회사마다 달라 흔한 것 몇 개를 봅니다."""
    # 서버 번호를 다 훑으면 후보 하나에 다섯 번씩 걸립니다.
    # 국내 회사는 wd3 와 wd102 가 대부분이라 둘만 봅니다.
    for wd in ("wd3", "wd102"):
        html, final = _get(f"https://{sub}.{wd}.myworkdayjobs.com/", timeout=6)
        if html:
            return {"ats": "workday", "code": f"{sub}.{wd}.myworkdayjobs.com/사이트이름",
                    "n": "", "url": final,
                    "title": _title(html) + " (사이트 이름을 직접 확인하세요)"}
        time.sleep(0.1)
    return None


CHECKS = [try_greeting, try_recruiter, try_ninehire, try_workday]


def _looks_same(korean, english, extra, title):
    """찾은 사이트가 그 회사가 맞는지 제목으로 가늠합니다.

    이름 후보를 만들어 두드리는 방식이라 다른 회사가 잡힐 수 있습니다.

      2026-09-12  "저스템" 을 찾으려고 jusung → 주성엔지니어링이 잡힘
      2026-09-15  "도구공간" 을 찾으려고 dogu → 사단법인 도구가 잡힘

    둘 다 다른 회사입니다. 뒤엣것은 "도구" 두 글자가 겹쳐 통과했습니다.

    제목을 주지 않는 ATS 도 있어서(리크루터는 빈 문자열) 그때는 판단하지
    않고 통과시킵니다. 애매한 것을 버리기보다 CSV 에 적어 사람이 보게
    합니다.
    """
    if not title:
        return True          # 제목이 없으면 판단하지 않습니다
    t = _norm(title)

    # 네 글자 이상이 통째로 들어 있으면 같은 곳으로 봅니다.
    for cand in [korean, english] + list(extra or []):
        c = _norm(cand)
        if len(c) >= 4 and c in t:
            return True

    # 두세 글자 짧은 이름은 제목 앞쪽에 있을 때만 인정합니다.
    #
    # "도구공간" 을 찾다가 "사단법인 도구" 가 잡힌 적이 있습니다. 여기서
    # "도구" 는 제목 끝에 붙은 남의 이름 조각이었습니다.
    #
    # 반대로 "클로봇" 은 "클로봇 x 로아스 - 채용 홈페이지" 처럼 제목이
    # 길어도 맨 앞에 옵니다. 회사 이름은 대개 제목 앞에 놓입니다.
    #
    # 그래서 길이가 아니라 위치로 봅니다. 앞 여섯 글자 안에 있으면
    # 그 회사 이름으로 시작한다고 보고 인정합니다.
    for cand in [korean, english] + list(extra or []):
        c = _norm(cand)
        if 2 <= len(c) <= 3 and c in t[:6]:
            return True

    # 제목이 영문 이름으로 시작하는 경우(WIRobotics 채용 같은).
    for cand in [english] + list(extra or []):
        c = _norm(cand)
        if len(c) >= 4 and t.startswith(c):
            return True

    return False


def probe(korean, english, extra):
    """한 회사를 모든 ATS 에서 찾아봅니다. 처음 찾은 것을 돌려줍니다.

    바깥이 후보 이름, 안쪽이 ATS 입니다. 회사 하나가 쓰는 ATS 는 하나뿐이니
    맞는 이름을 먼저 찾는 편이 빠릅니다.
    """
    subs = name_guesses(korean, english, extra)
    tried = 0
    doubt = None             # 이름이 안 맞아 보이는 것. 다 못 찾으면 이거라도 보고합니다.
    for sub in subs:
        for check in CHECKS:
            tried += 1
            try:
                hit = check(sub)
            except Exception:
                hit = None
            time.sleep(PAUSE)
            if not hit:
                continue
            hit["name"] = korean
            hit["tried"] = tried
            if _looks_same(korean, english, extra, hit.get("title", "")):
                hit["status"] = "발견"
                return hit
            # 이름이 달라 보입니다. 바로 버리지 않고 기억만 해둡니다.
            if doubt is None:
                hit["status"] = "확인필요"
                hit["note"] = "사이트 제목이 회사명과 다릅니다. 다른 회사일 수 있습니다"
                doubt = hit
    if doubt:
        return doubt
    return {"name": korean, "status": "못찾음", "ats": "", "code": "",
            "n": "", "url": "", "title": "", "tried": tried,
            "note": f"후보 {len(subs)}개 확인"}


def read_names(path):
    """목록 파일을 읽습니다. '회사명,영문이름[,별칭...]' 형식입니다."""
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        rows.append((parts[0], parts[1] if len(parts) > 1 else "", parts[2:]))
    return rows


def known():
    """이미 등록된 회사. 같은 곳을 또 찾지 않게 합니다."""
    try:
        d = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        return set()
    out = set()
    for c in d.get("companies") or []:
        out.add(_norm(c.get("name")))
        for a in (c.get("affiliates") or []):
            out.add(_norm(a))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", required=True, help="회사명 목록 파일")
    ap.add_argument("--limit", type=int, default=0, help="앞 N개만")
    ap.add_argument("--all", action="store_true", help="이미 등록된 곳도 확인")
    args = ap.parse_args()

    rows = read_names(args.names)
    if not args.all:
        have = known()
        before = len(rows)
        rows = [r for r in rows if _norm(r[0]) not in have]
        if before != len(rows):
            print(f"이미 등록된 {before - len(rows)}곳은 건너뜁니다.")
    if args.limit:
        rows = rows[:args.limit]

    print(f"{len(rows)}개사를 확인합니다. 회사당 20초쯤 걸립니다.\n")
    out, found, doubt = [], 0, 0
    for i, (ko, en, extra) in enumerate(rows, 1):
        r = probe(ko, en, extra)
        out.append(r)
        n = r["n"]
        if r["status"] == "발견":
            found += 1
            print(f"  [{i}/{len(rows)}] {ko} → {r['ats']} "
                  f"({r['code']}) {n if n != '' else '?'}건")
            if r.get("title"):
                print(f"          {r['title']}")
        elif r["status"] == "확인필요":
            doubt += 1
            print(f"  [{i}/{len(rows)}] {ko} → ? {r['ats']} ({r['code']}) "
                  f"{n if n != '' else '?'}건")
            print(f"          제목이 다릅니다: {r.get('title', '')}")
        else:
            print(f"  [{i}/{len(rows)}] {ko} → 못찾음")

    cols = ["name", "status", "ats", "code", "n", "url", "title", "tried", "note"]
    order = {"발견": 0, "확인필요": 1}
    with OUT.open("w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, cols)
        w.writeheader()
        for r in sorted(out, key=lambda x: (order.get(x["status"], 2), x["name"])):
            w.writerow({k: r.get(k, "") for k in cols})

    print(f"\n{len(rows)}개사 중 {found}곳 발견"
          + (f", {doubt}곳 확인필요" if doubt else ""))
    print(f"→ {OUT}")
    print("결과를 확인하고 src/data/companies.json 에 직접 옮겨 적으세요.")
    print("'확인필요' 는 이름이 비슷한 다른 회사일 수 있습니다. "
          "url 을 열어 보고 판단하세요.")


if __name__ == "__main__":
    main()
