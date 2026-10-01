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
import re
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


# 사라진 공고 보관 기간.
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
#
#   2026-09-10 부터는 마감일이 아니라 "수집 결과에서 사라진 날" 로
#   셉니다. 상시채용 공고도 함께 보관되므로 데이터가 이전보다 늘어납니다.
KEEP_DAYS = 60


def keep_recently_closed(fresh):
    """수집 결과에서 사라진 공고를 KEEP_DAYS 일간 데이터에 남깁니다.

    왜 필요한가
    -----------
    수집기는 매번 새로 받은 것으로 jobs.json 을 통째로 덮어씁니다.
    공고가 사라지면 /job/{id}/ 페이지도 사라져 404 가 됩니다.

    구글은 한 번 색인한 주소를 한동안 계속 방문합니다. 그때마다 404 를
    만나면 사이트 품질을 낮게 봅니다. 실제로 2026-09 초 색인된 32개 중
    14개가 404 였고, 전부 사라진 공고였습니다.

    그래서 사라진 뒤에도 일정 기간 데이터에 남겨 페이지를 유지합니다.
    화면 목록에는 나오지 않고, 상세 페이지가 "마감되었습니다" 를 보여주며
    다른 공고로 안내합니다. 사이트맵에는 진행중인 것만 넣습니다.

    기준은 마감일이 아니라 "사라진 날" 입니다
    -----------------------------------------
    예전에는 closesAt(마감일)로만 보관 여부를 정했습니다. 그래서 세 가지가
    통째로 새어 나갔습니다.

      1. 마감 당일에 사라진 공고
         마감일로부터 0일이라 조건(0 < gone)에 걸리지 않았습니다.
         2026-09-10 현대모비스 공고가 이렇게 사라졌습니다.

      2. 상시채용 공고
         마감일이 없어 계산 자체를 못 했습니다. 그런데 지금 데이터의
         약 65%(1,827건 중 1,188건)가 상시채용입니다. 넥슨·시프트업처럼
         마감일 없이 올리는 회사의 공고가 전부 여기 해당합니다.
         회사가 내리는 순간 흔적 없이 사라졌습니다.

      3. 마감일이 아직 남았는데 사라진 공고
         회사가 조기 마감하거나 공고를 고쳐 올려 id 가 바뀌면 이렇게 됩니다.
         마감일 기준으로는 음수라 걸러졌습니다.

    이제는 마감일을 보지 않고, 수집 결과에서 빠진 날(goneAt)을 적어 두고
    그날로부터 KEEP_DAYS 일을 셉니다. 어떤 이유로 사라졌든 똑같이 남습니다.

    goneAt 은 이 함수가 붙이는 값입니다
    -----------------------------------
    처음 사라진 날 한 번만 적고, 그 뒤로는 건드리지 않습니다. 매번 오늘
    날짜로 덮어쓰면 영원히 지워지지 않습니다.

    공고가 되살아나면(회사가 다시 올리면) 새 수집 결과에 id 가 있으므로
    아래 have 검사에서 걸러지고, goneAt 없는 새 항목으로 교체됩니다.

    본문이 없는 공고는 보관하지 않습니다
    ------------------------------------
    본문이 없으면 애초에 상세 페이지를 만들지 않습니다(lib.js 참고).
    없는 페이지는 404 가 날 일도 없으므로 보관해봐야 파일만 커집니다.
    NC·삼성·한화처럼 원문 링크만 주는 회사가 여기 해당합니다.
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
    today_s = today.isoformat()

    kept, expired = [], 0
    for j in old:
        # 이번에도 잡혔으면 살아 있는 공고입니다. 새 것으로 갱신됩니다.
        if j.get("id") in have:
            continue

        # 본문이 없으면 상세 페이지가 없고, 404 도 나지 않습니다.
        if len((j.get("description") or "").strip()) < 50:
            continue

        # 사라진 날. 이미 적혀 있으면 그대로 두고, 처음이면 오늘로 적습니다.
        gone_at = (j.get("goneAt") or "").strip()
        if not gone_at:
            gone_at = today_s

        try:
            parsed = date.fromisoformat(gone_at)
            # 형식을 YYYY-MM-DD 로 통일해 둡니다. 파이썬 3.11 부터는
            # "20260901" 같은 형태도 받아주지만, 저장은 한 가지로 맞춥니다.
            gone_at = parsed.isoformat()
            days = (today - parsed).days
        except ValueError:
            # 날짜를 읽을 수 없으면 오늘로 고쳐 적고 다시 셉니다.
            # 깨진 값을 그대로 두면 다음에도 또 걸려 영영 정리되지 않습니다.
            gone_at = today_s
            days = 0

        # 미래 날짜가 적혀 있으면(시계 문제 등) 오늘로 되돌립니다.
        if days < 0:
            gone_at, days = today_s, 0

        if days > KEEP_DAYS:
            expired += 1
            continue

        j = dict(j)
        j["goneAt"] = gone_at
        kept.append(j)

    if kept:
        fresh_gone = sum(1 for j in kept if j["goneAt"] == today_s)
        print(f"  · 사라진 공고 {len(kept)}건을 보관합니다 "
              f"(오늘 {fresh_gone}건 신규, 최대 {KEEP_DAYS}일)")
    if expired:
        print(f"  · 보관 기간이 끝난 공고 {expired}건을 내보냅니다")
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

# ── 목록에서 빼는 공고 ──────────────────────────────────
#
# 회사 채용페이지에 올라와 있지만 지원할 자리가 아닌 것들입니다.
# 채용박람회 안내, 행사 공지 같은 것이 여기 해당합니다.
#
# 패턴으로 거르지 않습니다. "박람회" 나 "공지" 로 거르면 정상 공고가
# 함께 빠집니다. 실제로 덴티움의 "마케팅본부 PM팀/디자인팀/세미나팀/
# 임상연구팀 인재 채용" 이 "세미나" 때문에 걸릴 뻔했습니다.
#
# 그래서 회사 이름과 제목이 정확히 맞는 것만 뺍니다. 새로 발견하면
# 여기에 한 줄 추가하세요. 제목은 앞부분만 적어도 됩니다.
DROP = [
    ("티에이치엔", "채용박람회"),
    ("로봇앤드디자인", "[공지] 2026년 「R&D 커리어랩 펠로우십"),
    ("원익", "[원익IPS] 상시 채용 공고"),
    ("토비스", "수시채용"),
    ("LG전자", "[LG전자 VS본부] 채용계약Track 온라인 채용 설명회"),
]


def dropped(job):
    """빼야 할 공고인지 봅니다. 회사와 제목이 모두 맞아야 뺍니다."""
    co = str(job.get("company") or "").strip()
    title = str(job.get("title") or "").strip()
    for d_co, d_title in DROP:
        if co == d_co and title.startswith(d_title):
            return True
    return False


# ─── 근무지 정리 ────────────────────────────────────────────────
#
# 회사가 채용 사이트의 "근무지" 칸에 지역 대신 회사 이름을 적어 두는 일이
# 흔합니다. 2026-10-01 기준으로 이런 공고가 500건이 넘었습니다.
#
#   덴티움        근무지 "덴티움"              85건
#   딥엑스        근무지 "㈜딥엑스"            62건
#   무신사        근무지 "무신사 성수 오피스"   121건
#
# 화면에 "덴티움 · 근무지 덴티움" 으로 나와 아무 정보가 되지 못하고,
# 검색에서도 같은 말이 두 번 걸립니다.
#
# 반대로 지역명이 회사 이름과 겹치는 경우도 있습니다.
#
#   데브캣의 근무지 "삼성"(삼성역 일대) 때문에 "삼성" 을 검색하면
#   게임회사 공고가 나왔습니다.
#
# 그래서 저장하기 전에 한 번 정리합니다. 어댑터마다 고치지 않고 여기서
# 처리하면 앞으로 추가되는 회사에도 그대로 적용됩니다.

# 지역으로 읽히게 다듬을 표기. 왼쪽이 그대로 들어온 값입니다.
LOC_RENAME = {
    "삼성": "삼성역",
}

# 회사 이름 뒤에 흔히 붙는 꼬리말. 비교할 때 떼어냅니다.
CO_TAIL = re.compile(r"(주식회사|\(주\)|㈜|\(유\)|Inc\.?|Co\.?,?\s*Ltd\.?)", re.I)


def _co_key(name):
    """회사 이름 비교용. 괄호·공백·법인 표기를 걷어냅니다."""
    s = CO_TAIL.sub(" ", str(name or ""))
    return re.sub(r"[\s·,\.\-()（）]", "", s).lower()


# 회사 이름을 영문으로만 적어 둔 경우를 위해 몇 곳을 손으로 적어 둡니다.
#
#   니어스랩의 근무지가 "NEARTHLAB(서울)" 로 옵니다. 한글 회사명과 글자가
#   달라 자동으로는 떼어지지 않습니다.
#
# 여기 없는 회사는 한글 이름만 비교합니다. 새로 눈에 띄면 추가하세요.
CO_ALIAS = {
    "니어스랩": ["NEARTHLAB", "Nearthlab"],
    "무신사": ["MUSINSA"],
    "토스": ["Toss", "TOSS"],
    "당근": ["Karrot", "DAANGN"],
    "컬리": ["Kurly", "KURLY"],
}


def clean_location(loc, company):
    """근무지에서 회사 이름을 걷어냅니다.

    세 가지를 합니다.
      1) 근무지가 회사 이름과 같으면 비웁니다("덴티움" → "")
      2) 근무지 안의 회사 이름만 떼어냅니다
         ("무신사 성수 오피스" → "성수 오피스")
      3) 지역으로 읽히게 다듬습니다("삼성" → "삼성역")

    회사 이름을 떼고 남은 게 없으면 비웁니다. 지역이 남으면 그대로 씁니다.
    없는 지역을 지어내지 않습니다.
    """
    loc = re.sub(r"\s+", " ", str(loc or "")).strip()
    if not loc:
        return ""

    co_key = _co_key(company)
    if co_key and _co_key(loc) == co_key:
        return ""

    # 근무지 안에 회사 이름이 통째로 들어 있으면 그 부분만 뺍니다.
    co_name = str(company or "").strip()
    for nm in [co_name] + CO_ALIAS.get(co_name, []):
        if nm and len(nm) >= 2 and nm in loc:
            loc = loc.replace(nm, " ")
    # 법인 표기만 남는 경우를 정리합니다.
    loc = CO_TAIL.sub(" ", loc)
    loc = re.sub(r"\s+", " ", loc).strip(" ,·-")
    # 회사명을 떼고 "(서울)" 처럼 괄호만 남으면 괄호를 벗깁니다.
    m = re.fullmatch(r"[（(]\s*([^)）]+?)\s*[)）]", loc)
    if m:
        loc = m.group(1).strip()

    if not loc or _co_key(loc) == co_key:
        return ""

    return LOC_RENAME.get(loc, loc)


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
        # 지원할 자리가 아닌 공고를 뺍니다(채용박람회 안내, 설명회 등).
        cut = [j for j in got if dropped(j)]
        if cut:
            got = [j for j in got if not dropped(j)]
            for j in cut:
                print(f"      · 제외: {str(j.get('title') or '')[:40]}")
        # 근무지 칸에 회사 이름이 들어온 것을 정리합니다.
        fixed = 0
        for j in got:
            before = str(j.get("location") or "").strip()
            after = clean_location(before, j.get("company") or c["name"])
            if before != after:
                j["location"] = after
                fixed += 1
        if fixed:
            print(f"      · 근무지 정리 {fixed}건")

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
