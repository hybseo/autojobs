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
from datetime import datetime, timedelta, timezone

# 수집 날짜는 반드시 한국 시간 기준이어야 합니다.
#
# 깃허브 Actions 서버는 UTC 로 돕니다. date.today() 를 그냥 쓰면
# KST 오전 9시 이전 실행에서 하루 전 날짜가 찍힙니다.
# 실제로 KST 06:00 예약 실행이 UTC 로는 전날 21:00 이라, 공고는 새로
# 모였는데 collectedAt 만 어제로 남아 화면에 "1일 전 정보" 경고가 떴습니다.
KST = timezone(timedelta(hours=9))


def today_kst():
    return datetime.now(KST).date().isoformat()

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

    OUT.write_text(json.dumps(
        {"collectedAt": today_kst(), "jobs": jobs},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
