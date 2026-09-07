#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""브라우저를 띄워 ATS 를 탐지합니다. probe_ats1.py 가 못 찾은 곳 전용입니다.

왜 따로 있는가
--------------
probe_ats1.py 는 서버가 주는 HTML 만 봅니다. 가볍고 안정적이지만,
요즘 사이트는 메뉴를 자바스크립트로 그려서 그 HTML 에 채용 링크가
없습니다. 실제로 삼성SDS 는 서버 HTML 에 채용 링크가 0개인데 브라우저
화면에는 3개가 있었고, IT 231곳 중 93곳(40%)이 이 이유로
"채용링크없음" 이 됐습니다.

이 스크립트는 브라우저를 띄워 화면이 다 그려진 뒤에 링크를 찾습니다.
확실하지만 회사당 5~10초가 걸립니다. probe_ats1.py 는 1~2초입니다.

한 파일로 합치지 않은 이유
  브라우저 설치가 실패하면 기존 탐지까지 못 돌게 됩니다. 분리해두면
  이쪽이 깨져도 probe_ats1.py 는 그대로 돕니다.

쓰는 순서
  1) probe_ats1.py 로 전체를 훑습니다. (가볍고 빠름)
  2) 못 찾은 곳만 목록으로 만들어 이 스크립트를 돌립니다.

사용법
  pip install playwright && playwright install chromium
  python scripts/probe_browser.py --urls scripts/targets_xxx.txt
  python scripts/probe_browser.py --urls ... --limit 30   # 시험용

상대 서버 부담
  브라우저는 HTML 만이 아니라 이미지·폰트·스크립트를 전부 내려받습니다.
  그대로 두면 요청이 수십 배로 늘어납니다. 이미지·폰트·미디어를 막고
  요청 간격도 둡니다. 남의 서버입니다.
"""
import argparse
import csv
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# 지문·판정 규칙은 probe_ats1.py 것을 그대로 씁니다.
# 두 벌로 관리하면 한쪽만 고쳐져 결과가 어긋납니다.
from probe_ats1 import (          # noqa: E402
    SIGNATURES, CAREER_WORD, detect, allowed, from_file,
)

OUT = Path(__file__).resolve().parent / "probe_browser_result.csv"

PAUSE = 1.0        # 회사 사이 간격. 브라우저는 요청이 많으니 넉넉히 둡니다.
NAV_TIMEOUT = 15000   # 한 페이지 최대 15초. 느린 곳을 기다리다 전체가 늘어집니다.
SETTLE = 1200      # 화면이 그려질 시간. 자바스크립트가 메뉴를 채우는 데 필요합니다.
MAX_LINKS = 4      # 따라갈 채용 링크 수. 더 늘리면 회사당 시간이 급격히 늘어납니다.

# 내려받지 않을 자원. 링크만 찾으면 되므로 그림은 필요 없습니다.
BLOCK = ("image", "media", "font", "stylesheet")


def new_page(browser):
    ctx = browser.new_context(
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/128.0.0.0 Safari/537.36 "
                    "(+https://searchjob.co.kr job aggregator)"),
        viewport={"width": 1280, "height": 900},
        ignore_https_errors=True,      # 인증서가 만료된 국내 사이트가 흔합니다.
    )
    ctx.set_default_timeout(NAV_TIMEOUT)
    ctx.route("**/*", lambda route: (
        route.abort() if route.request.resource_type in BLOCK else route.continue_()
    ))
    return ctx


def visit(page, url):
    """페이지를 열고 (HTML, 최종주소) 를 돌려줍니다. 실패하면 (None, 사유)."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
        page.wait_for_timeout(SETTLE)
        return page.content(), page.url
    except Exception as e:
        return None, str(e).split("\n")[0][:60]


def career_links_dom(page, cap=MAX_LINKS):
    """화면에 그려진 뒤의 채용 링크를 찾습니다.

    probe_ats1.py 의 career_links 는 HTML 문자열을 정규식으로 훑지만,
    여기서는 브라우저가 이미 DOM 을 갖고 있으므로 그쪽에서 바로 읽습니다.
    <button onclick> 처럼 <a> 가 아닌 것도 잡히도록 넓게 봅니다.
    """
    try:
        found = page.eval_on_selector_all(
            "a[href]",
            """els => els.map(a => ({h: a.href, t: (a.textContent||'').trim()}))""",
        )
    except Exception:
        return []
    out, seen = [], set()
    for it in found:
        h, t = it.get("h") or "", it.get("t") or ""
        if not h.startswith("http"):
            continue
        if not (CAREER_WORD.search(h) or CAREER_WORD.search(t)):
            continue
        if h in seen:
            continue
        seen.add(h)
        out.append(h)
        if len(out) >= cap:
            break
    return out


def probe_one(browser, name, home):
    rec = {"name": name, "home": home, "ats": "", "code": "",
           "found_at": "", "how": "", "status": "", "note": ""}
    if not home:
        rec["status"] = "홈페이지없음"
        return rec

    ctx = new_page(browser)
    page = ctx.new_page()
    try:
        html, final = visit(page, home)
        if not html:
            rec["status"] = "접속실패"
            rec["note"] = final
            return rec
        rec["home"] = final

        hit = detect(html, final)
        if hit:
            rec.update(ats=hit[0], code=hit[1], found_at=final,
                       how="브라우저", status="발견")
            return rec

        links = career_links_dom(page)
        rec["note"] = f"채용링크 {len(links)}개(화면)"
        for u in links:
            if not allowed(u):
                continue
            h2, f2 = visit(page, u)
            if not h2:
                continue
            hit = detect(h2, f2)
            if hit:
                rec.update(ats=hit[0], code=hit[1], found_at=f2,
                           how="브라우저→링크", status="발견")
                return rec

        rec["status"] = "ATS없음" if links else "채용링크없음"
        return rec
    finally:
        try:
            ctx.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--urls", required=True, help="회사명,홈페이지 목록 파일")
    ap.add_argument("--limit", type=int, default=0, help="앞에서 N개만 (시험용)")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit(
            "playwright 가 없습니다.\n"
            "  pip install playwright\n"
            "  playwright install chromium")

    rows = from_file(args.urls)
    if args.limit:
        rows = rows[:args.limit]
    print(f"대상 {len(rows)}개사 · 브라우저 방식")
    print(f"회사당 5~10초 · 예상 {len(rows) * 8 // 60}분\n")

    out = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            for i, (name, home) in enumerate(rows, 1):
                t0 = time.time()
                try:
                    rec = probe_one(browser, name, home)
                except Exception as e:
                    rec = {"name": name, "home": home, "ats": "", "code": "",
                           "found_at": "", "how": "", "status": "오류",
                           "note": str(e).split("\n")[0][:60]}
                out.append(rec)
                mark = "★" if rec["status"] == "발견" else " "
                print(f"  {mark} [{i:>3}/{len(rows)}] {name[:18]:<18} "
                      f"{rec['status']:<10} {rec['ats']:<12} "
                      f"{time.time() - t0:.1f}s")
                time.sleep(PAUSE)
        finally:
            browser.close()

    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    found = [r for r in out if r["status"] == "발견"]
    print(f"\n발견 {len(found)}곳 / {len(out)}곳")
    for r in found:
        print(f"   {r['name']:<20} {r['ats']:<12} {r['code'][:30]}")
    print(f"\n→ {OUT}")


if __name__ == "__main__":
    main()
