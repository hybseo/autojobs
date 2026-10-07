# -*- coding: utf-8 -*-
"""
막힌 주소의 원인을 가려내는 진단 도구입니다. 공고를 수집하지 않습니다.

  python scripts/probe_block.py
  python scripts/probe_block.py https://careers.dunamu.com/ https://careers.dunamu.com/detail/624

왜 이 도구가 필요한가
---------------------
수집이 막혔을 때 원인은 크게 셋인데, 로그의 "403 Forbidden" 한 줄로는
구분이 안 됩니다.

  1. 우리가 보내는 헤더가 부족해서       → 헤더를 채우면 풀립니다
  2. 우리 User-Agent 가 수집기로 읽혀서  → 꼬리표 문제입니다
  3. 깃허브 액션 아이피를 막아서         → 우리가 할 수 있는 게 없습니다

셋은 대응이 완전히 다릅니다. 그런데 개발 컨테이너에서는 외부 사이트에
접속할 수 없고(패키지 저장소만 열려 있습니다), 브라우저에서는 User-Agent
를 바꿀 수 없습니다. 그래서 둘 다로는 1·2·3 을 구분할 수 없습니다.

깃허브 액션 러너는 실제 수집이 돌아가는 바로 그 환경입니다. 여기서
헤더 조합을 하나씩 바꿔 보면 원인이 특정됩니다. 추측으로 고쳤다가
공고갱신을 한 시간 돌리고 또 실패하는 일을 막습니다.

2026-10-07 두나무 403 때문에 만들었습니다. careers.dunamu.com 은
CloudFront 뒤의 Next.js 앱이고(x-amz-cf-pop=ICN57, x-powered-by=Next.js,
브라우저로 확인), AWS WAF 가 붙어 있을 가능성이 큽니다. 브라우저로
열면 정상이라 사이트 자체가 막는 것은 아닙니다.

조합을 왜 이렇게 짰는가
-----------------------
A 와 D 의 차이가 핵심입니다. 둘 다 집계기 꼬리표가 붙은 같은
User-Agent 인데 D 는 브라우저가 실제로 보내는 헤더를 다 채웁니다.
D 가 통과하면 꼬리표는 죄가 없고 헤더가 부족했던 것입니다.

B·C 는 꼬리표만 뺀 것입니다. B·C 는 되고 D 는 안 되면 꼬리표가
걸린 것입니다. 전부 막히면 아이피 문제라 손쓸 수 없습니다.

하지 않는 것
------------
검색봇(Googlebot 등)을 흉내내는 User-Agent 는 시험하지 않습니다.
그건 사칭이고, 통과한다 해도 쓰면 안 되는 방법입니다. 시험 목록에
올려두면 언젠가 쓰게 됩니다.
"""
import sys
import urllib.request
import urllib.error

TAG = " (+https://searchjob.co.kr job aggregator)"
CHROME = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

# 크롬이 주소창 입력으로 문서를 받을 때 실제로 보내는 헤더입니다.
# 2026-10-07 에 브라우저 개발자도구에서 확인한 것만 적었습니다.
FULL = {
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,image/apng,*/*;q=0.8"),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    # gzip 만 적습니다. br 을 적으면 파이썬이 풀지 못해 본문이 깨집니다.
    "Accept-Encoding": "gzip, deflate",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "close",
}

CASES = [
    ("A 지금 어댑터와 동일 (꼬리표 있는 UA 만)", {"User-Agent": CHROME + TAG}),
    ("B 꼬리표 뺀 UA 만", {"User-Agent": CHROME}),
    ("C 꼬리표 뺀 UA + 브라우저 헤더 전체", dict(FULL, **{"User-Agent": CHROME})),
    ("D 꼬리표 있는 UA + 브라우저 헤더 전체", dict(FULL, **{"User-Agent": CHROME + TAG})),
    ("E 헤더 없음 (파이썬 기본)", {}),
]

# 어느 방어 장비인지 알려주는 헤더들. 있는 것만 찍습니다.
MARKERS = ("server", "via", "x-cache", "x-amz-cf-pop", "x-amz-cf-id",
           "x-powered-by", "cf-ray", "x-vercel-id", "x-amzn-waf-action",
           "x-amzn-requestid", "retry-after")

DEFAULT = ["https://careers.dunamu.com/",
           "https://careers.dunamu.com/detail/624"]


def _show_headers(h):
    out = []
    for k in MARKERS:
        v = h.get(k)
        if v:
            out.append(f"{k}={str(v)[:60]}")
    return " · ".join(out) or "표시 헤더 없음"


def try_one(url, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(400)
            return r.status, _show_headers(r.headers), len(body), ""
    except urllib.error.HTTPError as e:
        body = b""
        try:
            body = e.read(400)
        except Exception:
            pass
        text = body.decode("utf-8", "replace").replace("\n", " ")[:200]
        return e.code, _show_headers(e.headers), len(body), text
    except Exception as e:
        return 0, "", 0, f"{type(e).__name__}: {e}"


def main():
    urls = [a for a in sys.argv[1:] if a.startswith("http")] or DEFAULT

    for url in urls:
        print()
        print("=" * 72)
        print(url)
        print("=" * 72)
        for label, headers in CASES:
            code, marks, size, note = try_one(url, headers)
            mark = "통과" if 200 <= code < 300 else "막힘"
            print(f"  [{mark}] {code:>3}  {label}")
            print(f"         {marks}")
            if note:
                print(f"         응답: {note}")
            elif size:
                print(f"         본문 {size}바이트 이상 받음")

    print()
    print("읽는 법")
    print("  D 가 통과하면  → 헤더가 부족했던 것입니다. 꼬리표는 그대로 둡니다.")
    print("  B·C 만 통과하면 → 집계기 꼬리표가 걸린 것입니다.")
    print("  전부 막히면    → 아이피 차단입니다. 우리가 할 수 있는 게 없습니다.")


if __name__ == "__main__":
    main()
