# -*- coding: utf-8 -*-
"""
등록된 모든 기업의 접수중 공고를 수집해 src/data/jobs.json 을 갱신합니다.

  python scripts/fetch_jobs.py                 전체 수집
  python scripts/fetch_jobs.py --ats recruiter  특정 ATS 만
  python scripts/fetch_jobs.py --dry-run        파일을 쓰지 않고 건수만 확인

이 파일은 지휘만 합니다. 실제 수집은 scripts/adapters/ 안의 어댑터가 합니다.
기업을 추가할 때는 src/data/companies.json 만 고치면 됩니다. 이 파일은 건드리지 마세요.
새 채용 시스템을 붙일 때만 scripts/adapters/ 에 파일을 하나 추가하면 됩니다.
자세한 규약은 scripts/adapters/__init__.py 를 보세요.
"""
import json
import sys
from pathlib import Path
from datetime import date, datetime, timedelta, timezone

# 수집 날짜는 반드시 한국 시간 기준이어야 합니다.
#
# 깃허브 Actions 서버는 UTC 로 돕니다. date.today() 를 그냥 쓰면
# KST 오전 9시 이전 실행에서 하루 전 날짜가 찍힙니다.
# 실제로 KST 06:00 예약 실행이 UTC 로는 전날 21:00 이라, 공고는 새로
# 모였는데 collectedAt 만 어제로 남아 화면에 "1일 전 정보" 경고가 떴습니다.
KST = timezone(timedelta(hours=9))


def today_kst():
    return datetime.now(KST).date().isoformat()


# 마감 공고 보관 기간.
#
# 60일로 잡은 근거
#   구글은 404 를 한 번 보고 바로 지우지 않고 몇 차례 재확인합니다.
#   색인에서 빠지기까지 대개 1~2개월 걸립니다. 실제로 이 사이트의
#   404 14건은 2026-07-16 에 처음 감지됐는데 8-29 에도 재크롤링
#   되고 있었습니다.
#   30일이면 보관이 끝나는 시점에 구글이 아직 재방문 중이라 404 가
#   다시 생깁니다. 60일이면 대체로 정리됩니다.
#
#   90일로 두면 마감 공고로도 검색 유입을 받을 수 있지만, 데이터가
#   1,318건에서 2,334건으로 커집니다. 지금은 가볍게 두고, 마감
#   페이지로도 유입이 생기는 게 확인되면 그때 늘리세요.
KEEP_DAYS = 60


def keep_recently_closed(fresh):
    """마감돼 사라진 공고를 90일간 데이터에 남깁니다.

    왜 필요한가
    -----------
    수집기는 매번 새로 받은 것으로 jobs.json 을 통째로 덮어씁니다.
    공고가 마감되면 다음 실행 때 데이터에서 빠지고, /job/{id}/ 페이지도
    사라져 404 가 됩니다.

    구글은 한 번 색인한 주소를 한동안 계속 방문합니다. 그때마다 404 를
    만나면 사이트 품질을 낮게 봅니다. 실제로 2026-09 초 색인된 32개 중
    14개가 404 였고, 전부 마감된 공고였습니다.

    그래서 마감 뒤에도 90일간 데이터에 남겨 페이지를 유지합니다.
    화면에서는 "마감되었습니다" 를 보여주고 다른 공고로 안내합니다.
    사이트맵에는 진행중인 것만 넣으므로 크롤링 우선순위는 낮습니다.

    본문이 없는 공고는 상세 페이지를 만들지 않으므로 보관하지 않습니다.
    보관해봐야 404 를 막지 못하고 파일만 커집니다.
    """
    if not OUT.exists():
        return fresh

    try:
        old = json.loads(OUT.read_text(encoding="utf-8")).get("jobs") or []
    except Exception as e:
        print(f"      ! 기존 jobs.json 을 읽지 못했습니다: {e}")
        return fresh

    have = {j.get("id") for j in fresh}
    today = datetime.now(KST).date()
    kept = []
    for j in old:
        if j.get("id") in have:
            continue
        # 본문이 있어야 상세 페이지가 있고, 그래야 404 를 막는 뜻이 있습니다.
        if len((j.get("description") or "").strip()) < 50:
            continue
        end = (j.get("closesAt") or "").strip()
        if not end:
            continue      # 상시채용은 마감이 없습니다. 사라졌으면 그대로 둡니다.
        try:
            gone = (today - date.fromisoformat(end)).days
        except ValueError:
            continue
        if 0 < gone <= KEEP_DAYS:
            kept.append(j)

    if kept:
        print(f"  · 마감 공고 {len(kept)}건을 보관합니다 (최대 {KEEP_DAYS}일)")
    return fresh + kept

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adapters  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "src" / "data" / "companies.json"
OUT = ROOT / "src" / "data" / "jobs.json"

# ── 2026-08-24 브라우저 확인 기준 접수중 건수 ──────────────
# 한국타이어 16 · HL그룹 13 · 한온시스템 7 · 유라 5 · 현대트랜시스 4
# 현대모비스 1 · 현대케피코 1 · 현대위아 1 · 에스엘 1 · 티에이치엔 2
# 넥센타이어 2 · 세방전지 1 · 삼보모터스 1 · LS일렉트릭 1 · 그 외 소수
# 합계 75건 안팎. 실행 결과가 이와 크게 다르면 API 사양 변경을 의심할 것.

REQUIRED = ("name", "slug", "ats", "code")


def load_companies(only_ats=None):
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    out, slugs = [], set()
    for i, c in enumerate(data.get("companies", [])):
        missing = [k for k in REQUIRED if not c.get(k)]
        if missing:
            raise SystemExit(f"companies.json {i}번째 항목에 {missing} 이(가) 없습니다.")
        if c["slug"] in slugs:
            raise SystemExit(f"companies.json 에 slug '{c['slug']}' 가 중복입니다.")
        slugs.add(c["slug"])
        if c.get("enabled") is False:
            continue
        if only_ats and c["ats"] != only_ats:
            continue
        out.append(c)
    return out


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    only_ats = None
    if "--ats" in args:
        only_ats = args[args.index("--ats") + 1]

    companies = load_companies(only_ats)
    print(f"대상 {len(companies)}개사" + (f" (ats={only_ats})" if only_ats else ""))

    jobs, failed = [], []
    for c in companies:
        try:
            got = adapters.load(c["ats"]).fetch(c)
        except Exception as e:
            print(f"  ! {c['name']}: {e}")
            failed.append(c["name"])
            continue
        jobs += got
        print(f"  {c['name']}: {len(got)}건")

    # 어댑터가 잘못 만든 중복 ID 를 여기서 한 번 더 막습니다.
    # ID 가 겹치면 사이트에서 공고 하나가 통째로 사라집니다.
    seen = set()
    for j in jobs:
        if j["id"] in seen:
            n = 2
            while f"{j['id']}-{n}" in seen:
                n += 1
            j["id"] = f"{j['id']}-{n}"
        seen.add(j["id"])

    print(f"\n총 {len(jobs)}건" + (f" · 실패 {len(failed)}개사 {failed}" if failed else ""))

    if dry:
        print("--dry-run 이라 파일을 쓰지 않았습니다.")
        return

    # 전부 실패하면 기존 jobs.json 을 살립니다.
    # 빈 목록으로 덮어쓰면 사이트가 통째로 비어버립니다.
    if not jobs and OUT.exists():
        raise SystemExit("수집 결과가 0건입니다. 기존 파일을 보존하고 중단합니다.")

    jobs = keep_recently_closed(jobs)

    OUT.write_text(json.dumps(
        {"collectedAt": today_kst(), "jobs": jobs},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
