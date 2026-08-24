# -*- coding: utf-8 -*-
"""
리크루터(recruiter.co.kr) ATS 를 쓰는 기업의 접수중 공고를 수집해
src/data/jobs.json 을 갱신합니다.

  python scripts/fetch_jobs.py

주의
- submissionStatus 가 IN_SUBMISSION 인 것만 접수중입니다.
  openStatus 는 접수중을 뜻하지 않습니다. 마감된 지 수백 일 지난 공고도 OPEN 입니다.
- prefix 헤더가 없으면 500 이 떨어집니다. 기업 식별자 역할입니다.
- 인증 토큰은 필요 없습니다.
"""
import json, time, html, re, urllib.request
from pathlib import Path
from datetime import date

API = "https://api-recruiter.recruiter.co.kr"
OUT = Path(__file__).resolve().parent.parent / "src" / "data" / "jobs.json"

# 기업 추가는 여기에 한 줄씩. prefix 는 채용사이트 도메인의 맨 앞부분입니다.
COMPANIES = [
    # ── 완성차 부품 계열 ──────────────────────────────
    ("현대모비스", "hyundai-mobis", "mobis"),
    ("HL그룹", "hl-group", "hlcompany"),          # 만도·클레무브·로보틱스·디앤아이한라·만도브로제
    ("현대케피코", "hyundai-kefico", "hyundai-kefico"),
    ("현대트랜시스", "hyundai-transys", "hyundai-transys"),
    ("현대위아", "hyundai-wia", "hyundai-wia"),
    ("현대글로비스", "hyundai-glovis", "glovis"),
    # ── 전장·공조·전원 ───────────────────────────────
    ("한온시스템", "hanon-systems", "hanonsystems"),
    ("에스엘", "sl", "slworld"),                   # 에스엘미러텍·SHB 포함
    ("유라코퍼레이션", "yura", "yura"),             # 유라테크 포함
    ("LS오토모티브", "ls-automotive", "lsat"),
    ("LS일렉트릭", "ls-electric", "lselectric"),
    ("LS엠트론", "ls-mtron", "lsmtron"),
    ("티에이치엔", "thn", "thn"),
    ("경신", "kyungshin", "kyungshin"),
    ("세방전지", "sebang", "sebang"),              # 세방리튬배터리 포함
    # ── 차체·소재·타이어 ─────────────────────────────
    ("성우하이텍", "sungwoo-hitech", "swhitech"),
    ("삼보모터스", "sambo-motors", "sambomotors"),
    ("NVH코리아", "nvh-korea", "nvhkorea"),
    ("화승", "hwaseung", "hwaseung"),
    ("한국타이어", "hankook-tire", "hankooktire"),
    ("넥센타이어", "nexen-tire", "nexentire"),
    ("금호타이어", "kumho-tire", "kumhotire"),
    # ── 인접 산업 (로보틱스·장비) ─────────────────────
    ("원익", "wonik", "wonik"),                    # 원익로보틱스 포함
]

# ── 2026-08-24 브라우저 확인 기준 접수중 건수 ──────────────
# 한국타이어 16 · HL그룹 13 · 한온시스템 7 · 유라 5 · 현대트랜시스 4
# 현대모비스 1 · 현대케피코 1 · 현대위아 1 · 에스엘 1 · 티에이치엔 2
# 넥센타이어 2 · 세방전지 1 · 삼보모터스 1 · LS일렉트릭 1 · 그 외 소수
# 합계 75건 안팎. 실행 결과가 이와 크게 다르면 API 사양 변경을 의심할 것.

CAREER = {"CAREER": "경력", "NEW": "신입", "NEW_CAREER": "신입/경력",
          "ANY": "무관", "FIELD_DIFFERENCE": "분야별상이"}


def post(path, prefix, body):
    req = urllib.request.Request(
        API + path, method="POST",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "prefix": f"{prefix}.recruiter.co.kr"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def get(path, prefix):
    req = urllib.request.Request(
        API + path, headers={"prefix": f"{prefix}.recruiter.co.kr"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def list_open(prefix):
    out, page = [], 1
    while page <= 10:
        j = post("/position/v1/jobflex", prefix, {
            "pageableRq": {"page": page, "size": 100, "sort": ["END_DATE_TIME"]},
            "filter": {"keyword": "", "tagSnList": [], "jobGroupSnList": [],
                       "careerTypeList": [], "regionSnList": [],
                       "submissionStatusList": ["IN_SUBMISSION"],
                       "openStatusList": [], "resumeLanguageTypeList": []}})
        out += [x for x in j.get("list", []) if x.get("submissionStatus") == "IN_SUBMISSION"]
        pg = j.get("pagination") or {}
        if page >= pg.get("totalPages", 1):
            break
        page += 1
        time.sleep(0.3)
    return out


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def main():
    jobs, seen = [], {}
    for name, slug, prefix in COMPANIES:
        try:
            rows = list_open(prefix)
        except Exception as e:
            print(f"  ! {name}: {e}")
            continue
        for x in rows:
            sn = x["positionSn"]
            key = f"{prefix}-{sn}"
            seen[key] = seen.get(key, 0) + 1
            jid = key if seen[key] == 1 else f"{key}-{seen[key]}"
            try:
                d = get(f"/position/v2/jobflex/{sn}", prefix)
                raw = d.get("jobDescription") or ""
            except Exception:
                raw = ""
            text = strip_html(raw)
            # 본문이 이미지 한 장뿐인 공고는 세부 직무를 읽을 수 없습니다.
            image_only = len(text) < 50 and "<img" in raw.lower()
            jobs.append({
                "id": jid,
                "unit": "공고",
                "company": name, "companySlug": slug,
                "title": x["title"],
                "location": "",
                "career": CAREER.get(x.get("careerType"), x.get("careerType") or ""),
                "postedAt": (x.get("startDateTime") or "")[:10],
                "closesAt": (x.get("endDateTime") or "")[:10],
                "dday": x.get("dday"),
                "multiRole": image_only,
                "sourceTitle": "",
                "sourceUrl": f"https://{prefix}.recruiter.co.kr/career/jobs/{sn}",
                # 본문이 있으면 상세 페이지와 JobPosting 스키마가 생성됩니다.
                "description": raw if not image_only else "",
            })
            time.sleep(0.2)
        print(f"  {name}: {len(rows)}건")

    OUT.write_text(json.dumps(
        {"collectedAt": date.today().isoformat(), "jobs": jobs},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n총 {len(jobs)}건 → {OUT}")


if __name__ == "__main__":
    main()
