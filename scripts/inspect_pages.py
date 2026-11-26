# -*- coding: utf-8 -*-
"""
채용 페이지를 실제 브라우저로 열어 보고 무엇이 오가는지 남기는 조사 도구입니다.
공고를 수집하지 않고, 저장소에 아무것도 커밋하지 않습니다.

  python scripts/inspect_pages.py https://a.com/recruit https://b.com/careers

왜 필요한가 (2026-11-26)
------------------------
코스피 상위 100곳 중 금융·소비재·건설 회사를 새로 넣기로 했습니다(대표님 지시).
이 회사들은 대부분 자체 채용 사이트를 쓰고, 공고 목록을 화면이 뜬 뒤
자바스크립트로 따로 받아옵니다. 그 「따로 받아오는 주소」를 알아야 수집기를
붙일 수 있습니다.

개발 컨테이너에서는 외부 사이트에 접속할 수 없습니다. 깃허브 러너는 실제
수집이 도는 환경이라, 여기서 열리면 수집도 됩니다.

남기는 것 (inspect_out/ 폴더, 첨부파일로 올라감)
  <번호>.txt      화면에 보이는 글자 (앞 6,000자)
  <번호>.html     화면이 다 그려진 뒤의 HTML (앞 300,000자)
  <번호>.net.txt  페이지가 보낸 요청 중 문서·XHR·fetch (주소·방식·보낸 값·응답 앞부분)
  summary.txt     주소별 최종 주소·제목·글자 수·요청 수
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

OUT = "inspect_out"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def main(urls):
    os.makedirs(OUT, exist_ok=True)
    summary = []
    with sync_playwright() as p:
        br = p.chromium.launch()
        for i, url in enumerate(urls, 1):
            ctx = br.new_context(user_agent=UA, locale="ko-KR", viewport={"width": 1280, "height": 900})
            page = ctx.new_page()
            reqs = []

            def on_resp(resp, reqs=reqs):
                try:
                    rq = resp.request
                    if rq.resource_type not in ("document", "xhr", "fetch"):
                        return
                    body = ""
                    try:
                        ct = (resp.headers or {}).get("content-type", "")
                        if any(k in ct for k in ("json", "text", "xml", "javascript")):
                            body = resp.text()[:1500]
                    except Exception as e:
                        body = f"(본문 못 읽음: {type(e).__name__})"
                    reqs.append({
                        "type": rq.resource_type, "method": rq.method, "url": rq.url,
                        "status": resp.status, "post": (rq.post_data or "")[:800],
                        "ctype": (resp.headers or {}).get("content-type", ""), "body": body,
                    })
                except Exception:
                    pass

            page.on("response", on_resp)
            final, title, text, html, err = url, "", "", "", ""
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:
                    page.wait_for_load_state("networkidle", timeout=20000)
                except Exception:
                    pass
                time.sleep(2)
                final, title = page.url, page.title()
                text = page.inner_text("body")[:6000]
                html = page.content()[:300000]
            except Exception as e:
                err = f"{type(e).__name__}: {str(e)[:300]}"
            with open(f"{OUT}/{i:02d}.txt", "w", encoding="utf-8") as f:
                f.write(f"요청 주소: {url}\n최종 주소: {final}\n제목: {title}\n오류: {err}\n\n{text}")
            with open(f"{OUT}/{i:02d}.html", "w", encoding="utf-8") as f:
                f.write(html)
            with open(f"{OUT}/{i:02d}.net.txt", "w", encoding="utf-8") as f:
                for r in reqs:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            line = f"{i:02d} {url} -> {final} | 제목={title!r} | 글자={len(text)} | 요청={len(reqs)} | {err}"
            print(line, flush=True)
            summary.append(line)
            ctx.close()
        br.close()
    with open(f"{OUT}/summary.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(summary) + "\n")


if __name__ == "__main__":
    main([u for u in sys.argv[1:] if u.startswith("http")])
