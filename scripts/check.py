# -*- coding: utf-8 -*-
"""
사이트가 제대로 돌고 있는지 스스로 점검합니다.

  python scripts/check.py                 데이터·수집만 (빠름, 5초)
  python scripts/check.py --pages         화면까지 (배포된 사이트를 열어 봄, 2분)
  python scripts/check.py --log run.txt   갱신 로그도 함께

왜 만들었나
-----------
그동안 문제를 사람이 눈으로 찾았습니다. 그래서 늦게 알아챘습니다.

  마감 공고가 사라지던 문제        구글 404 가 쌓인 뒤에야 알았습니다
  같은 공고가 160번 중복되던 문제   건수가 이상해 보여 뒤져 보고 알았습니다
  오늘 마감인데 "마감" 으로 뜨던 문제  구직자가 볼 화면을 눌러 보고 알았습니다
  어댑터가 조용히 0건이 되던 문제    며칠 뒤 숫자를 비교하다 알았습니다

전부 자동으로 잡을 수 있는 것들입니다. 갱신할 때마다 돌리면 그날 바로 압니다.

무엇을 보는가
-------------
  데이터  jobs.json 이 규약을 지키는지, 숫자가 튀지 않는지
  수집    갱신 로그에서 0건·오류가 난 곳
  화면    배포된 사이트의 주요 페이지가 열리는지

판정
----
  통과    이상 없음
  주의    사람이 한 번 봐야 함. 정상일 수도 있습니다
  실패    고쳐야 함

실패가 있으면 종료 코드 1 을 돌려줍니다. 워크플로에서 이것으로 알림을 겁니다.
주의는 0 입니다. 주의로 갱신을 멈추면 늑대 소년이 됩니다.
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOBS = ROOT / "src" / "data" / "jobs.json"
COMPANIES = ROOT / "src" / "data" / "companies.json"
SITE = "https://searchjob.co.kr"

KST = timezone(timedelta(hours=9))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr self-check)")

# jobs.json 의 공고 하나가 가져야 할 칸.
# goneAt 은 사라진 공고에만 붙으므로 따로 둡니다.
REQUIRED = {"id", "unit", "company", "companySlug", "title", "location",
            "career", "postedAt", "closesAt", "dday", "multiRole",
            "sourceTitle", "sourceUrl", "description"}
OPTIONAL = {"goneAt"}

# 한 회사가 이보다 많이 올리면 중복 수집을 의심합니다.
# 2026-09-11 에 JW중외제약이 4건을 160건으로 부풀린 적이 있습니다.
# 넥슨이 140건대라 그보다 넉넉히 잡습니다.
MAX_PER_COMPANY = 200

# 전체 건수가 하루 만에 이만큼 넘게 움직이면 알립니다.
SWING = 0.25

results = []


def ok(area, msg):
    results.append(("통과", area, msg))


def warn(area, msg):
    results.append(("주의", area, msg))


def fail(area, msg):
    results.append(("실패", area, msg))


def _load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        fail("데이터", f"{path.name} 을 읽지 못했습니다: {e}")
        return None


# ── 데이터 검사 ────────────────────────────────────────────────

def check_data():
    """jobs.json 과 companies.json 이 규약을 지키는지 봅니다."""
    d = _load(JOBS)
    c = _load(COMPANIES)
    if not d or not c:
        return

    jobs = d.get("jobs") or []
    cos = c.get("companies") or []
    if not jobs:
        fail("데이터", "공고가 하나도 없습니다")
        return
    ok("데이터", f"공고 {len(jobs)}건 · 등록 기업 {len(cos)}곳")

    # 수집 날짜가 오늘이나 어제여야 합니다.
    today = datetime.now(KST).date()
    got = str(d.get("collectedAt") or "")
    try:
        gap = (today - datetime.strptime(got, "%Y-%m-%d").date()).days
        if gap > 2:
            fail("데이터", f"수집 날짜가 {got} 입니다. {gap}일 전이라 갱신이 멈춘 듯합니다")
        elif gap > 1:
            warn("데이터", f"수집 날짜가 {got} 입니다. 하루 이상 지났습니다")
        else:
            ok("데이터", f"수집 날짜 {got}")
    except ValueError:
        fail("데이터", f"수집 날짜를 읽을 수 없습니다: {got!r}")

    # 칸이 빠지거나 낯선 칸이 생기면 어댑터가 규약을 어긴 것입니다.
    broken = []
    for x in jobs:
        keys = set(x.keys())
        if REQUIRED - keys or keys - REQUIRED - OPTIONAL:
            broken.append(x.get("id") or "(id 없음)")
    if broken:
        fail("데이터", f"칸이 규약과 다른 공고 {len(broken)}건: {broken[:3]}")
    else:
        ok("데이터", "모든 공고가 칸 규약을 지킵니다")

    # id 가 겹치면 상세 페이지가 서로 덮어씁니다.
    ids = [x.get("id") for x in jobs]
    dup = [k for k, n in _count(ids).items() if n > 1]
    if dup:
        fail("데이터", f"id 가 겹치는 공고 {len(dup)}건: {dup[:3]}")
    else:
        ok("데이터", "id 가 모두 다릅니다")

    # 제목이나 원문 주소가 비면 화면에서 빈칸으로 보입니다.
    empty_t = [x["id"] for x in jobs if not str(x.get("title") or "").strip()]
    empty_u = [x["id"] for x in jobs if not str(x.get("sourceUrl") or "").startswith("http")]
    if empty_t:
        fail("데이터", f"제목이 빈 공고 {len(empty_t)}건: {empty_t[:3]}")
    if empty_u:
        fail("데이터", f"원문 주소가 없거나 http 가 아닌 공고 {len(empty_u)}건: {empty_u[:3]}")
    if not empty_t and not empty_u:
        ok("데이터", "제목과 원문 주소가 모두 채워져 있습니다")

    # 날짜 형식과 앞뒤 순서.
    bad_date = []
    for x in jobs:
        for k in ("postedAt", "closesAt", "goneAt"):
            v = str(x.get(k) or "")
            if v and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
                bad_date.append(f"{x['id']}:{k}={v}")
    if bad_date:
        fail("데이터", f"날짜 형식이 어긋난 공고 {len(bad_date)}건: {bad_date[:3]}")
    else:
        ok("데이터", "날짜 형식이 모두 YYYY-MM-DD 입니다")

    # 등록하지 않은 회사의 공고가 섞이면 산업 분류가 비어 화면에서 떠돕니다.
    slugs = {x.get("slug") for x in cos}
    orphan = sorted({x.get("companySlug") for x in jobs} - slugs)
    if orphan:
        fail("데이터", f"companies.json 에 없는 회사의 공고: {orphan[:5]}")
    else:
        ok("데이터", "모든 공고가 등록된 회사의 것입니다")

    # 한 회사가 너무 많으면 중복 수집을 의심합니다.
    per = _count(x.get("companySlug") for x in jobs)
    heavy = {k: n for k, n in per.items() if n > MAX_PER_COMPANY}
    if heavy:
        warn("데이터", f"한 회사에서 {MAX_PER_COMPANY}건을 넘겼습니다(중복 수집 의심): {heavy}")
    else:
        top = max(per.items(), key=lambda kv: kv[1])
        ok("데이터", f"회사별 최다 {top[1]}건({top[0]}) · 기준 {MAX_PER_COMPANY}건 이내")

    # 마감된 공고가 보관되고 있는지.
    # 2026-09-11 에 보관 로직이 고장나 상시채용이 통째로 사라진 적이 있습니다.
    kept = [x for x in jobs if x.get("goneAt")]
    if kept:
        ok("데이터", f"사라진 공고 {len(kept)}건을 보관 중입니다")
    else:
        warn("데이터", "보관 중인 공고가 하나도 없습니다. "
                     "fetch_jobs.py 의 보관 로직을 확인하세요")

    # 활성 등록인데 공고가 하나도 없는 회사.
    got_slugs = {x.get("companySlug") for x in jobs}
    idle = [x["name"] for x in cos
            if x.get("enabled", True) and x.get("slug") not in got_slugs]
    if len(idle) > len(cos) * 0.4:
        warn("데이터", f"공고가 0건인 활성 기업이 {len(idle)}곳입니다(전체의 "
                     f"{len(idle) * 100 // max(len(cos), 1)}%). 어댑터 오류일 수 있습니다")
    else:
        ok("데이터", f"공고 0건인 활성 기업 {len(idle)}곳 (채용을 쉬는 중이면 정상)")


def _count(seq):
    out = {}
    for x in seq:
        out[x] = out.get(x, 0) + 1
    return out


# ── 수집 로그 검사 ─────────────────────────────────────────────

def check_log(path):
    """갱신 로그에서 0건·오류를 추립니다.

    깃허브 Actions 화면에서 로그를 복사해 파일로 넘기면 됩니다.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except Exception as e:
        fail("수집", f"로그를 읽지 못했습니다: {e}")
        return

    zero = re.findall(r"^\s{2}(.+?): 0건\s*$", text, re.M)
    errs = re.findall(r"^\s*!\s*(.+?)$", text, re.M)
    total = re.search(r"총 ([\d,]+)건", text)

    if total:
        ok("수집", f"로그의 총 수집 {total.group(1)}건")

    if errs:
        # 오류는 회사 이름만 추립니다. 뒤의 사유는 길어서 잘라 둡니다.
        names = [e.split(":")[0].strip()[:20] for e in errs][:8]
        warn("수집", f"오류가 난 곳 {len(errs)}곳: {names}")
    else:
        ok("수집", "오류 없이 끝났습니다")

    if len(zero) > 40:
        warn("수집", f"0건인 회사가 {len(zero)}곳입니다. 평소보다 많으면 확인하세요")
    else:
        ok("수집", f"0건인 회사 {len(zero)}곳")

    # 어댑터가 조용히 깨졌을 때 남기는 안내문.
    for pat, msg in [
        (r"어댑터가 없습니다", "어댑터 파일이 없는 회사가 있습니다"),
        (r"공고를 찾지 못했습니다", "화면 구조가 바뀌어 파싱이 실패한 곳이 있습니다"),
        (r"접수중 공고가 없습니다", "접수중이 0건인 곳이 있습니다"),
    ]:
        hits = re.findall(pat, text)
        if hits:
            warn("수집", f"{msg} ({len(hits)}건). 로그에서 '!' 줄을 확인하세요")


# ── 화면 검사 ──────────────────────────────────────────────────

def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def check_pages():
    """배포된 사이트의 주요 페이지를 실제로 열어 봅니다.

    빌드가 성공해도 화면이 깨질 수 있습니다. 2026-09-11 에 제약바이오를
    등록했는데 산업 페이지가 만들어지지 않은 적이 있습니다. 빌드는 통과했고
    공고도 들어왔지만 페이지만 없었습니다.
    """
    d = _load(JOBS)
    if not d:
        return
    jobs = d.get("jobs") or []

    pages = [("/", "홈"), ("/sitemap.xml", "사이트맵"), ("/robots.txt", "robots.txt")]

    # 사이트맵에 적힌 주소 중 몇 개를 골라 실제로 열어 봅니다.
    try:
        _, sm = _get(SITE + "/sitemap.xml")
        locs = re.findall(r"<loc>([^<]+)</loc>", sm)
        ok("화면", f"사이트맵에 주소 {len(locs)}개")
        for i in (1, len(locs) // 3, len(locs) // 2, len(locs) - 1):
            if 0 <= i < len(locs):
                pages.append((locs[i].replace(SITE, ""), "사이트맵 표본"))
    except Exception as e:
        fail("화면", f"사이트맵을 열지 못했습니다: {e}")

    # 오늘 마감인 공고. 상세에서 "마감" 으로 뜨면 안 됩니다.
    # 2026-09-11 에 실제로 그런 적이 있습니다.
    #
    # 본문이 짧은 공고는 상세 페이지를 만들지 않습니다(job/[id].astro 참고).
    # 삼성·현대모비스처럼 목록만 주고 본문을 안 주는 회사가 그렇습니다.
    # 그런 공고를 열면 404 가 나는 것이 정상이므로 검사 대상에서 뺍니다.
    today = datetime.now(KST).strftime("%Y-%m-%d")
    todays = [x for x in jobs
              if x.get("closesAt") == today
              and len(str(x.get("description") or "").strip()) >= 50]
    if todays:
        pages.append((f"/job/{todays[0]['id']}/", "오늘 마감 공고"))
    else:
        ok("화면", "오늘 마감이면서 본문이 있는 공고가 없어 이 검사는 건너뜁니다")

    bad = 0
    for path, label in pages:
        url = SITE + path
        try:
            status, html = _get(url)
            if status != 200:
                fail("화면", f"{label} {path} → HTTP {status}")
                bad += 1
                continue
            # 내용이 제대로 있는지 봅니다. 파일 종류마다 기준이 다릅니다.
            #
            # 처음에는 모든 주소에 "500자 이상" 을 적용했습니다. 빈 화면을
            # 잡으려던 것인데, robots.txt 는 원래 네 줄짜리 짧은 파일입니다.
            # 69자가 정상인데 "내용이 69자뿐" 이라며 실패로 처리했고,
            # 2026-09-16 부터 며칠 동안 거짓 실패 메일이 매일 왔습니다.
            #
            # 그래서 텍스트 파일은 길이 대신 꼭 있어야 할 줄이 있는지 봅니다.
            if path == "/robots.txt":
                if "Sitemap:" not in html:
                    fail("화면", f"robots.txt 에 Sitemap 줄이 없습니다")
                    bad += 1
                    continue
            elif path == "/sitemap.xml":
                if "<urlset" not in html:
                    fail("화면", f"sitemap.xml 형식이 아닙니다 (urlset 없음)")
                    bad += 1
                    continue
            elif len(html) < 500:
                fail("화면", f"{label} {path} → 내용이 {len(html)}자뿐입니다")
                bad += 1
                continue
            if label == "오늘 마감 공고" and "마감되었습니다" in html:
                fail("화면", f"오늘 마감인 공고가 이미 마감으로 표시됩니다: {path}")
                bad += 1
        except Exception as e:
            fail("화면", f"{label} {path} → {str(e)[:50]}")
            bad += 1

    if not bad:
        ok("화면", f"주요 페이지 {len(pages)}개가 모두 정상입니다")

    # 공유 썸네일과 사이트맵 날짜.
    # 둘 다 네이버가 참고하는 값이라 빠지면 노출에 불리합니다.
    try:
        _, home = _get(SITE + "/")
        if 'property="og:image"' in home or "property='og:image'" in home:
            ok("화면", "공유 썸네일(og:image) 설정됨")
            m = re.search(r'og:image"[^>]*content="([^"]+)"', home)
            if m:
                try:
                    st, _ = _get(m.group(1))
                    if st == 200:
                        ok("화면", "썸네일 이미지 파일이 열립니다")
                    else:
                        fail("화면", f"썸네일 이미지가 HTTP {st} 입니다: {m.group(1)}")
                except Exception:
                    fail("화면", f"썸네일 이미지를 열지 못했습니다: {m.group(1)}")
        else:
            warn("화면", "og:image 가 없습니다. 네이버·카카오 공유 시 그림이 안 나옵니다")
    except Exception as e:
        warn("화면", f"홈에서 og:image 를 확인하지 못했습니다: {str(e)[:40]}")

    try:
        _, sm2 = _get(SITE + "/sitemap.xml")
        if "<lastmod>" in sm2:
            ok("화면", "사이트맵에 lastmod 가 있습니다")
        else:
            warn("화면", "사이트맵에 lastmod 가 없습니다. 재방문 주기가 늦어집니다")
    except Exception:
        pass

    # 산업·직무 페이지가 실제로 만들어졌는지.
    for path, label in [("/industry/pharma-bio/", "제약바이오 산업"),
                        ("/industry/it/", "IT 산업"),
                        ("/role/ai/", "AI 직무")]:
        try:
            status, html = _get(SITE + path)
            if status == 200 and len(html) > 500:
                ok("화면", f"{label} 페이지 정상")
            else:
                fail("화면", f"{label} 페이지가 비었습니다 ({status}, {len(html)}자)")
        except Exception as e:
            fail("화면", f"{label} 페이지를 열지 못했습니다: {str(e)[:40]}")


# ── 보고 ──────────────────────────────────────────────────────

def report():
    order = {"실패": 0, "주의": 1, "통과": 2}
    mark = {"실패": "✗", "주의": "!", "통과": "·"}
    for level in ("실패", "주의", "통과"):
        rows = [r for r in results if r[0] == level]
        if not rows:
            continue
        print(f"\n[{level}] {len(rows)}건")
        for _, area, msg in rows:
            print(f"  {mark[level]} {area}  {msg}")

    n_fail = sum(1 for r in results if r[0] == "실패")
    n_warn = sum(1 for r in results if r[0] == "주의")
    print()
    if n_fail:
        print(f"실패 {n_fail}건. 고쳐야 합니다.")
    elif n_warn:
        print(f"실패는 없습니다. 주의 {n_warn}건은 한 번 보세요.")
    else:
        print("모두 정상입니다.")
    return 1 if n_fail else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", action="store_true", help="배포된 사이트도 열어 봄")
    ap.add_argument("--log", help="갱신 로그 파일")
    args = ap.parse_args()

    print("사이트 자가진단")
    check_data()
    if args.log:
        check_log(args.log)
    if args.pages:
        check_pages()
    sys.exit(report())


if __name__ == "__main__":
    main()
