# -*- coding: utf-8 -*-
"""
새로 붙일 기업을 공고갱신 전에 미리 돌려 보는 시험 도구입니다 (2026-11-26).
공고 데이터를 건드리지 않고 저장소에 아무것도 커밋하지 않습니다. 로그만 봅니다.

  python scripts/try_adapters.py                       후보 파일 전체
  python scripts/try_adapters.py --only hana-bank,kb-sec
  python scripts/try_adapters.py --dump "GET https://..." --dump "POST https://... {json}"

왜 필요한가
-----------
공고갱신은 한 시간 반이 걸립니다. 회사를 넣고 갱신을 돌린 뒤에야 0건인 걸
알면 또 한 번 돌려야 합니다. 개발 컨테이너는 외부 사이트에 접속할 수 없어
여기서 미리 확인할 방법이 없었습니다.

후보는 scripts/candidates.json 에 companies.json 과 같은 모양으로 적습니다.
여기서 공고가 실제로 잡히는 것을 본 뒤에 companies.json 으로 옮깁니다.
"""
import collections
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adapters  # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def dump(spec):
    # 「GET 주소 ~~ 정규식」 이면 응답 전체 대신 맞는 곳 앞뒤 200자만 보여 줍니다.
    # 깃허브 로그는 아주 긴 한 줄을 잘라 버려서, 압축된 자바스크립트는 통째로 못 봅니다.
    pat = None
    if " ~~ " in spec:
        spec, pat = spec.split(" ~~ ", 1)
    parts = spec.strip().split(" ", 2)
    method, url = parts[0].upper(), parts[1]
    body = parts[2].encode("utf-8") if len(parts) > 2 else None
    head = {"User-Agent": UA, "Accept": "application/json, text/html, */*"}
    if body is not None:
        head["Content-Type"] = "application/json" if body[:1] in (b"{", b"[") else "application/x-www-form-urlencoded"
    print(f"=== DUMP {method} {url}")
    try:
        import http.cookiejar, ssl
        # 오래된 은행 서버는 예전 방식 TLS 재협상을 요구합니다(우리금융그룹 등).
        # 쿠키를 받아야 넘어가는 곳도 있습니다(IBK 채용 페이지의 302 반복).
        ctx = ssl.create_default_context()
        ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
            urllib.request.HTTPSHandler(context=ctx))
        req = urllib.request.Request(url, data=body, headers=head, method=method)
        with opener.open(req, timeout=30) as r:
            raw = r.read()
            enc = r.headers.get_content_charset() or "utf-8"
            txt = raw.decode(enc, "replace")
            print(f"status {r.status} · {len(raw)} bytes · {r.headers.get('content-type')}")
            if pat:
                import re
                for k, m in enumerate(re.finditer(pat, txt)):
                    if k >= 60:
                        break
                    print("  ~ " + txt[max(0, m.start() - 200):m.end() + 200].replace("\n", " "))
            else:
                for i in range(0, min(len(txt), 3000000), 3000):
                    print(txt[i:i + 3000])
    except Exception as e:
        print(f"오류 {type(e).__name__}: {str(e)[:300]}")


def main():
    args = sys.argv[1:]
    dumps = [args[i + 1] for i, a in enumerate(args) if a == "--dump"]
    for d in dumps:
        dump(d)
    if dumps and "--cands" not in args and "--only" not in args:
        return
    only = None
    if "--only" in args:
        only = {s.strip() for s in args[args.index("--only") + 1].split(",") if s.strip()}
    src = Path(__file__).resolve().parent / "candidates.json"
    cands = json.loads(src.read_text(encoding="utf-8"))["companies"]
    total = 0
    for c in cands:
        if only and c["slug"] not in only:
            continue
        print(f"=== TRY {c['name']} ({c['ats']} · {c['code']})")
        try:
            got = adapters.load(c["ats"]).fetch(c)
        except Exception as e:
            print(f"  ! 실패 {type(e).__name__}: {str(e)[:400]}")
            continue
        total += len(got)
        cnt = collections.Counter(str(j.get("company")) for j in got)
        print(f"  → {len(got)}건 · 회사 {dict(cnt.most_common(12))}")
        if "--full" in args or only:
            # 요약용: --only 로 몇 곳만 돌릴 때는 공고 하나를 한 줄 JSON 으로 모두 찍습니다.
            for j in got:
                print("JOBJSON " + json.dumps({k: j.get(k) for k in ("id", "company", "title", "closesAt", "multiRole", "location", "description")}, ensure_ascii=False))
        for j in got[:4]:
            print(f"    - {str(j.get('title'))[:60]} | {j.get('closesAt')} | {j.get('career')} | {str(j.get('sourceUrl'))[:110]} | 본문 {len(str(j.get('description') or ''))}자")
    print(f"=== 합계 {total}건")


if __name__ == "__main__":
    main()
