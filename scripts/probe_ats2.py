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

PAUSE = 0.25        # 후보 하나 두드릴 때마다 쉬는 시간
TIMEOUT = 8         # 없는 주소가 대부분이라 짧게 끊습니다

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
        for c in (s,                    # neuromeka
                  s + "1",              # neuromeka1
                  s + "hr",             # classyshr
                  s + "_hr",            # pharmaresearch_hr
                  s + "-hr",
                  s + "recruit",
                  s + "recruiter",      # robotisrecruiter
                  s + "career",
                  s + "careers",
                  s + "corp"):
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
    for wd in ("wd1", "wd3", "wd5", "wd102", "wd103"):
        html, final = _get(f"https://{sub}.{wd}.myworkdayjobs.com/", timeout=6)
        if html:
            return {"ats": "workday", "code": f"{sub}.{wd}.myworkdayjobs.com/사이트이름",
                    "n": "", "url": final,
                    "title": _title(html) + " (사이트 이름을 직접 확인하세요)"}
        time.sleep(0.1)
    return None


CHECKS = [try_greeting, try_recruiter, try_ninehire, try_workday]


def probe(korean, english, extra):
    """한 회사를 모든 ATS 에서 찾아봅니다. 처음 찾은 것을 돌려줍니다."""
    subs = name_guesses(korean, english, extra)
    tried = 0
    for sub in subs:
        for check in CHECKS:
            tried += 1
            try:
                hit = check(sub)
            except Exception:
                hit = None
            time.sleep(PAUSE)
            if hit:
                hit["name"] = korean
                hit["status"] = "발견"
                hit["tried"] = tried
                return hit
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
    out, found = [], 0
    for i, (ko, en, extra) in enumerate(rows, 1):
        r = probe(ko, en, extra)
        out.append(r)
        if r["status"] == "발견":
            found += 1
            n = r["n"]
            print(f"  [{i}/{len(rows)}] {ko} → {r['ats']} "
                  f"({r['code']}) {n if n != '' else '?'}건")
            if r.get("title"):
                print(f"          {r['title']}")
        else:
            print(f"  [{i}/{len(rows)}] {ko} → 못찾음")

    cols = ["name", "status", "ats", "code", "n", "url", "title", "tried", "note"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, cols)
        w.writeheader()
        for r in sorted(out, key=lambda x: (x["status"] != "발견", x["name"])):
            w.writerow({k: r.get(k, "") for k in cols})

    print(f"\n{len(rows)}개사 중 {found}곳 발견")
    print(f"→ {OUT}")
    print("결과를 확인하고 src/data/companies.json 에 직접 옮겨 적으세요.")
    print("이름이 비슷한 다른 회사가 잡혔을 수 있으니 title 칸을 보세요.")


if __name__ == "__main__":
    main()
