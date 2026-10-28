#!/usr/bin/env python3
"""
수집처 robots.txt 점검
=====================================================================
우리가 공고를 가져오는 모든 사이트가 "가져가도 된다" 고 하고 있는지
확인합니다. 네트워크가 되는 곳에서 돌리세요.

    python3 scripts/check_robots.py              전체 점검
    python3 scripts/check_robots.py --min 10     공고 10건 이상인 곳만

왜 필요한가 (2026-10-14)
------------------------
나인하이어(9개사)가 2026-10-02 새벽에 갑자기 막혔습니다. 알아보니
robots.txt 에 이렇게 적혀 있었습니다.

    User-agent: *
    Disallow: /*?*page=

우리가 쓰던 주소가 정확히 이 모양이었습니다. 우회하지 않기로 하고 9개사를
비활성으로 돌렸습니다.

문제는 그때 "나머지 플랫폼은 확인한 적이 없다" 는 사실이 드러난 것입니다.
그리팅 한 곳에만 공고 3,500건 넘게 달려 있는데, 거기가 같은 결정을 하면
그만큼이 한꺼번에 사라집니다. 그런데 우리는 모르고 계속 긁고 있게 됩니다.

robots.txt 는 사이트가 언제든 바꿀 수 있습니다. 한 번 확인하고 끝낼 일이
아니라 가끔 다시 봐야 하는 일입니다. 그래서 스크립트로 만들었습니다.

무엇을 보는가
-------------
도메인만 보지 않고 **우리가 실제로 가져오는 주소 그대로** 판정합니다.
도메인은 허용인데 특정 주소 모양만 막아둔 경우(나인하이어가 그랬습니다)를
놓치지 않기 위해서입니다.

판정은 파이썬 표준 robotparser 를 씁니다. 직접 해석하면 틀립니다.

결과 보는 법
------------
    허용      상대가 수집해도 된다고 밝힌 상태입니다
    비허용    상대가 수집하지 말라고 밝힌 상태입니다
    robots없음  robots.txt 가 없는 것은 "전부 허용" 과 같습니다 (표준)
    오류      robots.txt 파일을 못 받았다는 뜻입니다. 공고 수집과는
              상관없습니다. 판정이 아니므로 다시 돌려보세요

이 스크립트는 아무것도 바꾸지 않습니다. 보고만 합니다.

"비허용" 이 나오면 어떻게 하나 (2026-10-15 결정)
-------------------------------------------------
robots.txt 는 기술적으로 아무것도 막지 않습니다. 법적 의무도 아니고
업계 관행입니다. 그래서 "비허용" 이 떠도 수집은 그대로 됩니다.

2026-10-15 에 10곳·104건이 비허용으로 나왔을 때, 수집을 계속하기로
정했습니다. 그러니 이 보고서를 보고 기업을 끌 필요는 없습니다.

그래도 계속 점검하는 이유는 두 가지입니다.
  1. 어딘가 상태가 바뀌면 알아야 합니다. 특히 robots.txt 에서 그치지
     않고 실제로 막아버리는 경우(나인하이어가 그랬습니다)는 수집이
     깨지므로 손을 써야 합니다.
  2. 나중에 방침을 바꾸게 되면 그때 판단할 근거가 남아 있어야 합니다.

판단이 필요할 만큼 상황이 달라지면 사람이 결정합니다.

요청을 늘릴 때는 어떻게 하나 (2026-10-28 결정)
----------------------------------------------
2026-10-28 에 본문이 비어 있던 공고를 메우려고 여러 수집기에 "공고마다
상세를 한 번 더 받는" 처리를 넣었습니다. 그러면 요청 수가 크게 늘어납니다.
오늘의집은 홈페이지 한 번 읽던 것이 공고 67건을 각각 읽는 것으로 바뀌었고,
그 호스트는 비허용으로 기록된 곳이었습니다.

"하던 수집을 계속한다"(2026-10-15)와 "요청을 크게 늘린다"는 다른 일이라
따로 물어보고 정했습니다.

  비허용 12곳         그대로 둡니다. 요청이 늘어나도 유지합니다.
  robots.txt 못 받음  허용으로 봅니다. 규칙을 받지 못한 것이지 금지가
  (401·403·오류) 3곳  아니기 때문입니다. 카카오(401)에 상세 API 를 붙인
                      근거가 이것입니다.

어느 쪽이든 쉬는 시간(공고당 0.3초)은 반드시 둡니다.
"""
import argparse
import collections
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
JOBS = ROOT / "src" / "data" / "jobs.json"
COMPANIES = ROOT / "src" / "data" / "companies.json"

# 판정에 쓰는 User-Agent
# ----------------------
# 반드시 수집기가 실제로 보내는 것과 같아야 합니다. robots.txt 는
# User-Agent 별로 규칙이 갈리기 때문에, 다른 이름으로 물어보면 우리 요청과
# 상관없는 답을 받습니다.
#
# 2026-10-15 에 이걸로 한 번 틀렸습니다. 점검용으로 따로 만든 이름
# ("searchjob.co.kr robots-check …") 으로 돌려서 273건이 비허용으로 나왔는데,
# 수집기는 그 이름을 쓰지 않으니 그 결과는 우리 요청에 적용되는 값이
# 아니었습니다.
#
# 파이썬 robotparser 는 User-Agent 에서 첫 "/" 앞까지만 떼어 소문자로 바꾼 뒤,
# robots.txt 의 User-agent 줄이 거기에 들어있는지로 판단합니다. 아래 둘은
# 모두 "mozilla" 가 되어 같은 그룹에 걸립니다.
#
# 어댑터의 UA 를 바꾸면 여기도 같이 바꾸세요. 안 그러면 점검 결과가
# 조용히 어긋납니다. (scripts/adapters/*.py 의 UA 상수)
UA_LIST = [
    # 어댑터 52개가 쓰는 것
    ("브라우저형",
     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
     "(+https://searchjob.co.kr job aggregator)"),
    # greeting.py 가 쓰는 것
    ("수집기형", "Mozilla/5.0 (compatible; searchjob.co.kr job aggregator)"),
]
# robots.txt 를 받아올 때 쓸 이름 (받는 것 자체는 어느 쪽이든 같습니다)
UA = UA_LIST[0][1]
TIMEOUT = 15


def _fetch_once(host):
    url = f"https://{host}/robots.txt"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read().decode("utf-8", "replace")
            if r.status != 200:
                return None, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        # 404 는 robots.txt 가 없다는 뜻이고, 표준상 전부 허용입니다.
        return (None, "robots없음") if e.code in (404, 410) else (None, f"HTTP {e.code}")
    except Exception as e:
        return None, f"오류 {type(e).__name__}"

    p = RobotFileParser()
    p.parse(body.splitlines())
    return p, body


def fetch_robots(host):
    """robots.txt 를 받아 (파서, 받아온 내용 또는 상태) 를 돌려줍니다.

    한 번 실패하면 잠깐 쉬었다 한 번 더 해봅니다. 일시적인 끊김이나
    순간적인 거절 때문에 "확인 실패" 로 남는 호스트를 줄이기 위해서입니다.
    robots.txt 가 없는 것(404)은 확정된 답이므로 다시 시도하지 않습니다.
    """
    parser, info = _fetch_once(host)
    if parser is not None or info == "robots없음":
        return parser, info
    time.sleep(2)
    return _fetch_once(host)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=1,
                    help="공고가 이 수 이상인 호스트만 점검 (기본 1)")
    args = ap.parse_args()

    jobs = json.loads(JOBS.read_text(encoding="utf-8"))["jobs"]
    companies = json.loads(COMPANIES.read_text(encoding="utf-8"))
    if isinstance(companies, dict):
        companies = companies.get("companies", companies)
    ats_of = {c["slug"]: c.get("ats", "?") for c in companies}

    # 호스트별로 공고 수와, 판정에 쓸 실제 주소 표본을 모읍니다.
    counts = collections.Counter()
    samples = collections.defaultdict(list)
    ats_seen = collections.defaultdict(set)
    for j in jobs:
        u = j.get("sourceUrl") or ""
        host = urlparse(u).hostname
        if not host:
            continue
        counts[host] += 1
        if len(samples[host]) < 5:
            samples[host].append(u)
        a = ats_of.get(j.get("companySlug")) or ats_of.get(j.get("slug"))
        if a:
            ats_seen[host].add(a)

    # 파이썬 3.13 미만은 robots 규칙을 잘못 읽습니다. 규칙 끝의 물음표를
    # 떼어버려서, 넥슨의 "Disallow: /recruit?" 를 "Disallow: /recruit" 로
    # 보고 멀쩡한 공고 180건을 막힌 것으로 판정했습니다. 틀린 답을 내놓느니
    # 돌지 않는 편이 낫습니다. (2026-10-15)
    if sys.version_info < (3, 13):
        print(f"파이썬 {sys.version.split()[0]} 에서는 돌릴 수 없습니다.\n"
              f"3.13 이상이 필요합니다. 그 아래 버전은 robots 규칙 끝의\n"
              f"물음표를 떼어버려 멀쩡한 주소를 막힌 것으로 판정합니다.")
        return 2

    targets = [(h, n) for h, n in counts.most_common() if n >= args.min]
    rows = []
    rows.append(f"{'공고':>6}  {'판정':<14}{'ATS':<16}호스트")
    rows.append("-" * 82)

    blocked, errors = [], []
    for host, n in targets:
        parser, info = fetch_robots(host)
        if parser is None:
            verdict = info
            if info != "robots없음":
                errors.append((host, n, info))
        else:
            # 수집기가 실제로 쓰는 User-Agent 전부로 재봅니다. 하나라도
            # 막히면 막힌 것으로 봅니다.
            bad = None
            for label, ua in UA_LIST:
                hit = [u for u in samples[host] if not parser.can_fetch(ua, u)]
                if hit:
                    bad = (label, hit[0])
                    break
            if bad:
                verdict = "비허용"
                # 받아온 robots.txt 를 같이 남깁니다. 판정만 적어두면
                # 나중에 맞는지 확인할 방법이 없습니다. 2026-10-15 에
                # 넥슨이 비허용으로 나왔는데 같은 robots.txt 를 손으로
                # 돌리니 허용이 나왔고, 근거가 없어 어느 쪽이 맞는지
                # 가릴 수 없었습니다.
                blocked.append((host, n, bad[1], bad[0], info))
            else:
                verdict = "허용"
        ats = ",".join(sorted(ats_seen[host])) or "?"
        rows.append(f"{n:>6}  {verdict:<14}{ats:<16}{host}")

    # 결론을 맨 위에 적습니다. 호스트가 360개라 끝까지 내려가야 결과를
    # 알 수 있으면 아무도 안 봅니다.
    blocked_n = sum(n for _, n, _, _, _ in blocked)
    if blocked:
        head = (f"상대가 수집을 원하지 않는다고 밝힌 곳 {len(blocked)}곳 · 공고 {blocked_n:,}건 "
                f"(수집은 계속합니다 — 맨 위 주석의 2026-10-15 결정)")
    else:
        head = "모두 허용입니다. 멈춰야 할 곳이 없습니다"
    if errors:
        head += f"\n확인하지 못한 곳 {len(errors)}곳 (판정 아님)"
    print(head)
    print(f"\n호스트 {len(targets)}개 점검 (공고 {sum(n for _, n in targets):,}건) "
          f"· 파이썬 {sys.version.split()[0]}\n")
    print("\n".join(rows))

    print("\n" + "=" * 82)
    if blocked:
        total = sum(n for _, n, _, _, _ in blocked)
        print(f"\n비허용 {len(blocked)}곳 · 공고 {total:,}건\n")
        for host, n, u, label, body in blocked:
            print(f"  {n:>6}건  {host}   ({label} User-Agent 기준)")
            print(f"          막힌 주소 예: {u}")
            print(f"          받아온 robots.txt:")
            for line in body.strip().splitlines()[:25]:
                print(f"            | {line}")
            if len(body.strip().splitlines()) > 25:
                print(f"            | … (이하 생략)")
            print()
        print("\n  수집을 멈추지는 않습니다(2026-10-15 결정). 이 목록은 상대가")
        print("  무엇이라고 밝혀두었는지 기록해 두기 위한 것입니다.")
    else:
        print("\n비허용으로 판정된 곳이 없습니다.")

    if errors:
        print(f"\n robots.txt 를 못 받은 곳 {len(errors)}곳 — 판정이 아닙니다.\n 그 파일을 못 받았다는 뜻일 뿐, 공고 수집과는 상관없습니다.")
        for host, n, why in errors:
            print(f"  {n:>6}건  {host:<45}{why}")

    # 비허용이 있으면 0이 아닌 값으로 끝냅니다. 자동화에서 걸러내기 쉽게.
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
