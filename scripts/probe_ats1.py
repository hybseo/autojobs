# -*- coding: utf-8 -*-
"""
기업이 어떤 채용 시스템(ATS)을 쓰는지 일괄 판별합니다.

  python scripts/probe_ats.py                     KAICA 자동차부품 중견이상 전수
  python scripts/probe_ats.py --limit 30          앞 30개사만 (시험용)
  python scripts/probe_ats.py --urls list.txt     "회사명,홈페이지" 목록 파일로
  python scripts/probe_ats.py --new-only          companies.json 에 없는 곳만

결과는 화면과 scripts/probe_result.csv 에 남습니다. 이 스크립트는 아무것도
자동으로 등록하지 않습니다. 결과를 보고 사람이 companies.json 에 옮겨 적으세요.
잘못 판별된 기업이 조용히 들어가는 것보다 낫습니다.

왜 필요한가
-----------
검색으로 찾는 방식은 두 가지를 놓칩니다.
  1. 자체 도메인을 쓰는 회사. 주소만 봐서는 무슨 ATS 인지 알 수 없습니다.
     현대오토에버가 career.hyundai-autoever.com 을 쓰는데 속은 그리팅입니다.
  2. 검색에 색인되지 않은 채용 페이지.
이 스크립트는 기업 홈페이지에서 채용 링크를 따라가 실제로 확인합니다.

다른 산업으로 넓힐 때
---------------------
SOURCE 부분만 바꾸면 됩니다. 판별 로직(detect)은 산업과 무관합니다.
--urls 로 "회사명,홈페이지" 목록을 직접 넣어도 됩니다.
"""
import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "probe_result.csv"
REGISTRY = ROOT / "src" / "data" / "companies.json"

UA = "Mozilla/5.0 (compatible; searchjob.co.kr job aggregator)"
PAUSE = 0.5          # 요청 간격. 남의 서버입니다. 줄이지 마세요.
TIMEOUT = 15

# 기업 홈페이지에서 채용 페이지를 찾을 때 훑어볼 경로
CAREER_PATHS = ["", "/recruit", "/recruit/", "/career", "/careers",
                "/jobs", "/ko/recruit", "/company/recruit", "/recruit.html"]

# ATS 지문. 페이지 HTML 안에 이 흔적이 있으면 그 ATS 를 씁니다.
SIGNATURES = [
    ("greeting",  r"([a-z0-9\-]+)\.career\.greetinghr\.com"),
    ("recruiter", r"([a-z0-9\-]+)\.recruiter\.co\.kr"),
    ("jobda",     r"([a-z0-9\-]+)\.jobda\.im"),
    ("workday",   r"([a-z0-9\-]+)\.myworkdayjobs\.com"),
    ("greenhouse", r"boards\.greenhouse\.io/([a-z0-9\-]+)"),
    ("lever",     r"jobs\.lever\.co/([a-z0-9\-]+)"),
]

# 자체 도메인이라 주소로는 알 수 없는 경우, 페이지 내용으로 판별합니다.
GREETING_MARKER = re.compile(
    r"__NEXT_DATA__|careerBootInfo|greetinghr", re.I)

# 홈페이지에서 "채용" 으로 보이는 링크를 찾아냅니다.
# 경로를 찍어 맞히는 것보다 이쪽이 훨씬 잘 맞습니다. 회사마다 주소가 제각각이라
# /recruit 을 안 쓰고 /kor/sub05/03.php 같은 주소를 쓰는 곳이 많습니다.
LINK = re.compile(r"""<a[^>]+href=["']([^"']+)["'][^>]*>(.*?)</a>""", re.I | re.S)
CAREER_WORD = re.compile(
    r"채\s*용|인재\s*채용|리크루|recruit|career|jobs?\b|인재영입|입사지원|talent", re.I)


def career_links(html, page_url, cap=6):
    """홈페이지 HTML 에서 채용 페이지로 보이는 링크를 뽑습니다."""
    out, seen = [], set()
    for m in LINK.finditer(html or ""):
        href, text = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
        if not CAREER_WORD.search(href) and not CAREER_WORD.search(text):
            continue
        if href.startswith(("javascript:", "mailto:", "#")):
            continue
        try:
            u = urllib.parse.urljoin(page_url, href)
        except Exception:
            continue
        if not u.startswith("http") or u in seen:
            continue
        seen.add(u)
        out.append(u)
        if len(out) >= cap:
            break
    return out


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        ct = (r.headers.get("Content-Type") or "").lower()
        if "html" not in ct and "json" not in ct and "text" not in ct:
            return ""
        return r.read(400_000).decode("utf-8", "replace")


_robots = {}


def allowed(url):
    """robots.txt 를 존중합니다. 읽을 수 없으면 허용으로 봅니다."""
    try:
        p = urllib.parse.urlsplit(url)
        base = f"{p.scheme}://{p.netloc}"
        rp = _robots.get(base)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(base + "/robots.txt")
            try:
                rp.read()
            except Exception:
                rp = True          # robots 를 못 읽으면 허용
            _robots[base] = rp
        if rp is True:
            return True
        return rp.can_fetch(UA, url)
    except Exception:
        return True


def detect(html, page_url):
    """HTML 한 장에서 ATS 를 판별합니다. (ats, code, 근거) 또는 None."""
    for ats, pat in SIGNATURES:
        m = re.search(pat, html, re.I)
        if m:
            return ats, m.group(1), "링크"
    # 자체 도메인 그리팅. 채용 페이지 자체가 그리팅으로 만들어진 경우입니다.
    if GREETING_MARKER.search(html) and re.search(
            r"openings|openingJobPosition", html):
        host = urllib.parse.urlsplit(page_url).netloc
        return "greeting", host, "자체도메인"
    return None


def probe_company(name, home):
    """기업 홈페이지를 열고, 채용 링크를 따라가며 ATS 를 찾습니다.

    항상 dict 를 돌려줍니다. 못 찾아도 왜 못 찾았는지 status 에 남깁니다.
    이게 있어야 "ATS 를 안 쓰는 것" 과 "접속이 안 된 것" 을 구분할 수 있습니다.
    """
    rec = {"name": name, "home": home, "ats": "", "code": "",
           "found_at": "", "how": "", "status": "", "note": ""}
    if not home:
        rec["status"] = "홈페이지없음"
        return rec
    if not home.startswith("http"):
        home = "https://" + home
    base = home.rstrip("/")
    rec["home"] = base

    # 1단계: 홈페이지
    html = ""
    for cand in (base, base.replace("https://", "http://")):
        try:
            html = http_get(cand)
            if html:
                base = cand
                break
        except Exception as e:
            rec["note"] = type(e).__name__
    if not html:
        rec["status"] = "접속실패"
        return rec

    hit = detect(html, base)
    if hit:
        rec.update(ats=hit[0], code=hit[1], found_at=base,
                   how=hit[2], status="발견")
        return rec

    # 2단계: 홈페이지에 있는 채용 링크를 따라갑니다.
    links = career_links(html, base)
    rec["note"] = f"채용링크 {len(links)}개"
    for u in links:
        if not allowed(u):
            continue
        try:
            h = http_get(u)
        except Exception:
            continue
        time.sleep(PAUSE)
        if not h:
            continue
        hit = detect(h, u)
        if hit:
            rec.update(ats=hit[0], code=hit[1], found_at=u,
                       how=hit[2], status="발견")
            return rec

    # 3단계: 도메인 이름으로 그리팅 주소를 찍어봅니다. (kyungshin.co.kr → kyungshin)
    label = urllib.parse.urlsplit(base).netloc.replace("www.", "").split(".")[0]
    if len(label) >= 3:
        guess = f"https://{label}.career.greetinghr.com/ko"
        try:
            h = http_get(guess)
            if h and re.search(r"openings|openingJobPosition", h):
                rec.update(ats="greeting", code=label, found_at=guess,
                           how="주소추정", status="발견")
                return rec
        except Exception:
            pass
        time.sleep(PAUSE)

    rec["status"] = "ATS없음" if links else "채용링크없음"
    return rec


# KAICA 상세 페이지에서 기업 홈페이지 주소만 골라냅니다.
#
# 주의: href= 를 통째로 찾으면 안 됩니다. HTML 맨 위 <link> 태그의
# fonts.googleapis.com 같은 주소가 먼저 걸립니다. 실제로 그래서 30개사가
# 전부 구글 폰트 주소로 잡힌 적이 있습니다. <a> 태그만, 그리고 아래
# 잡음 도메인을 뺀 것만 씁니다.
ANCHOR = re.compile(r"""<a[^>]+href=["'](https?://[^"']+)["']""", re.I)
NOISE = ("kaica", "google", "gstatic", "facebook", "youtube", "instagram",
         "twitter", "naver.com", "daum.net", "kakao", "linkedin", "adobe",
         "microsoft", "w3.org", "jquery", "bootstrapcdn", "cloudflare")


def pick_homepage(html):
    for m in ANCHOR.finditer(html or ""):
        u = m.group(1)
        if any(n in u.lower() for n in NOISE):
            continue
        return u
    return ""


# ── 대상 목록 만들기 ─────────────────────────────────────────
KAICA_LIST = "https://kaica.or.kr/business/company.php?page={}"


def from_kaica(pages=38):
    """KAICA 자동차부품기업 현황에서 중견기업 이상을 뽑고 홈페이지를 얻습니다."""
    from html.parser import HTMLParser

    class Rows(HTMLParser):
        def __init__(self):
            super().__init__()
            self.rows, self.cur, self.cell, self.href, self.grab = [], [], "", "", False

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == "tr":
                self.cur, self.href = [], ""
            elif tag == "td":
                self.cell, self.grab = "", True
            elif tag == "a" and a.get("href") and not self.href:
                self.href = a["href"]

        def handle_data(self, d):
            if self.grab:
                self.cell += d

        def handle_endtag(self, tag):
            if tag == "td":
                self.cur.append(self.cell.strip())
                self.grab = False
            elif tag == "tr" and len(self.cur) >= 5:
                self.rows.append((self.cur, self.href))

    out = []
    for p in range(1, pages + 1):
        try:
            html = http_get(KAICA_LIST.format(p))
        except Exception as e:
            print(f"  ! 목록 {p}쪽 실패: {e}")
            continue
        pr = Rows()
        pr.feed(html)
        for cells, href in pr.rows:
            size = cells[4]
            if size != "대기업" and not size.startswith("중견"):
                continue
            name = re.sub(r"㈜|\(주\)|\(유\)|주식회사", "", cells[1]).strip()
            home = ""
            if href:
                try:
                    d = http_get(urllib.parse.urljoin(
                        "https://kaica.or.kr/business/", href))
                    home = pick_homepage(d)
                except Exception:
                    pass
                time.sleep(PAUSE)
            out.append((name, home))
        print(f"  목록 {p}/{pages}쪽 · 누적 {len(out)}개사")
    return out


def from_file(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [x.strip() for x in re.split(r"[,\t|]", line, 1)]
        rows.append((parts[0], parts[1] if len(parts) > 1 else ""))
    return rows


def known_names():
    if not REGISTRY.exists():
        return set()
    d = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {c["name"] for c in d.get("companies", [])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--urls")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--pages", type=int, default=38)
    ap.add_argument("--new-only", action="store_true")
    a = ap.parse_args()

    print("대상 목록을 만드는 중입니다. 몇 분 걸립니다.")
    targets = from_file(a.urls) if a.urls else from_kaica(a.pages)

    if a.new_only:
        known = known_names()
        before = len(targets)
        targets = [t for t in targets if t[0] not in known]
        print(f"이미 등록된 {before - len(targets)}개사를 뺐습니다.")
    if a.limit:
        targets = targets[:a.limit]

    print(f"\n{len(targets)}개사를 검사합니다.\n")
    rows, found, n = [], [], 0
    for name, home in targets:
        n += 1
        r = probe_company(name, home)
        rows.append(r)
        if r["status"] == "발견":
            found.append(r)
            print(f"  [{n}/{len(targets)}] ★ {name} → {r['ats']} ({r['code']}) {r['how']}")
        elif n % 25 == 0:
            print(f"  [{n}/{len(targets)}] 진행 중 · 지금까지 {len(found)}곳 발견")
        time.sleep(PAUSE)

    print(f"\n검사 {len(rows)}개사 · 발견 {len(found)}곳\n")

    # 못 찾은 이유를 반드시 남깁니다.
    # 0곳이 나왔을 때 이 숫자가 없으면 무엇을 고쳐야 할지 알 수 없습니다.
    st = {}
    for r in rows:
        st[r["status"]] = st.get(r["status"], 0) + 1
    print("결과 내역")
    for k, v in sorted(st.items(), key=lambda x: -x[1]):
        print(f"   {k:<12} {v}개사")
    if found:
        print("\nATS 별")
        by = {}
        for f in found:
            by[f["ats"]] = by.get(f["ats"], 0) + 1
        for k, v in sorted(by.items(), key=lambda x: -x[1]):
            print(f"   {k:<12} {v}곳")

    cols = ["name", "status", "ats", "code", "home", "found_at", "how", "note"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, cols)
        w.writeheader()
        for r in sorted(rows, key=lambda x: (x["status"] != "발견", x["name"])):
            w.writerow({k: r.get(k, "") for k in cols})
    print(f"\n→ {OUT}  (발견된 곳이 맨 위에 옵니다)")
    print("결과를 확인하고 src/data/companies.json 에 직접 옮겨 적으세요.")
    print("자체도메인으로 잡힌 그리팅은 code 가 아니라 domain 에 넣어야 합니다.")


if __name__ == "__main__":
    main()
