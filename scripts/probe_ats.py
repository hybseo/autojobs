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
    """기업 홈페이지와 흔한 채용 경로를 훑어 ATS 를 찾습니다."""
    if not home:
        return None
    if not home.startswith("http"):
        home = "https://" + home
    base = home.rstrip("/")
    for path in CAREER_PATHS:
        url = base + path
        if not allowed(url):
            continue
        try:
            html = http_get(url)
        except Exception:
            continue
        if not html:
            continue
        hit = detect(html, url)
        if hit:
            return {"name": name, "home": base, "ats": hit[0],
                    "code": hit[1], "found_at": url, "how": hit[2]}
        time.sleep(PAUSE)
    return None


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
                    m = re.search(
                        r'href="(https?://(?!\S*kaica)[^"]+)"', d)
                    home = m.group(1) if m else ""
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
    found, n = [], 0
    for name, home in targets:
        n += 1
        r = probe_company(name, home)
        if r:
            found.append(r)
            print(f"  [{n}/{len(targets)}] ★ {name} → {r['ats']} ({r['code']}) {r['how']}")
        elif n % 25 == 0:
            print(f"  [{n}/{len(targets)}] 진행 중 · 지금까지 {len(found)}곳 발견")
        time.sleep(PAUSE)

    print(f"\n검사 {len(targets)}개사 · 발견 {len(found)}곳")
    by = {}
    for f in found:
        by[f["ats"]] = by.get(f["ats"], 0) + 1
    for k, v in sorted(by.items(), key=lambda x: -x[1]):
        print(f"   {k:<12} {v}곳")

    with OUT.open("w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, ["name", "ats", "code", "home", "found_at", "how"])
        w.writeheader()
        for f in found:
            w.writerow(f)
    print(f"\n→ {OUT}")
    print("결과를 확인하고 src/data/companies.json 에 직접 옮겨 적으세요.")
    print("자체도메인으로 잡힌 그리팅은 code 가 아니라 domain 에 넣어야 합니다.")


if __name__ == "__main__":
    main()
