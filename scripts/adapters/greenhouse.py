# -*- coding: utf-8 -*-
"""
Greenhouse 수집기. 국내외 기술 기업이 널리 씁니다.

  목록·본문  GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true

Greenhouse 가 공식으로 제공하는 Job Board API 입니다. 공식 문서에
"Job Board 데이터는 공개이므로 GET 엔드포인트에 인증이 필요 없다"고
적혀 있습니다. 인증이 필요한 것은 지원서 제출(POST)뿐입니다.
  https://developers.greenhouse.io/job-board.html

Ashby 와 마찬가지로 한 번 요청하면 목록과 본문이 함께 옵니다.
공고 수와 무관하게 요청 1회라 상대 서버 부담이 가장 적습니다.

code 는 무엇인가
----------------
Greenhouse 채용 사이트 주소의 회사 부분(board token)입니다.
주소 형태가 두 가지인데 토큰 위치는 같습니다.

  https://job-boards.greenhouse.io/seoulrobotics   →  code = "seoulrobotics"
  https://boards.greenhouse.io/seoulrobotics       →  code = "seoulrobotics"

한국 공고만 담습니다
--------------------
Greenhouse 를 쓰는 회사는 해외 공고를 함께 올리는 경우가 많습니다.
국내 구직자용 사이트이므로 한국 근무지만 남깁니다.
해외까지 원하면 companies.json 에 "overseas": true 를 넣으세요.

주의
----
- Greenhouse 는 마감일을 주지 않습니다. 전부 상시채용으로 표시됩니다.
- 신입/경력 구분도 없습니다. "무관" 으로 둡니다. 지어내지 않습니다.
"""
import json
import re
import html
import urllib.parse
import urllib.request

API = "https://boards-api.greenhouse.io/v1/boards/{}/jobs?content=true"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# 근무지에 나라 이름이 안 붙는 경우가 많아 도시명까지 봅니다.
KOREA = re.compile(
    r"korea|대한민국|한국"
    r"|서울|seoul|부산|busan|대구|daegu|인천|incheon|광주|gwangju"
    r"|대전|daejeon|울산|ulsan|세종|sejong"
    r"|경기|gyeonggi|판교|pangyo|성남|seongnam|수원|suwon|용인|화성|평택|안산"
    r"|천안|cheonan|아산|청주|cheongju|전주|jeonju|포항|pohang|구미|gumi"
    r"|창원|changwon|김해|제주|jeju", re.I)


def _get(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def _location(job):
    return ((job.get("location") or {}).get("name") or "").strip()


def _is_korea(job):
    return bool(KOREA.search(_location(job)))


def list_open(code, overseas=False):
    """공개된 공고 목록. probe 용으로 밖에서도 씁니다."""
    j = _get(API.format(urllib.parse.quote(code)))
    rows = j.get("jobs") or []
    if overseas:
        return rows
    kept = [x for x in rows if _is_korea(x)]
    # 받아온 건 있는데 전부 걸러졌다면 지명 목록이 부족한 것입니다.
    # 무엇이 왔는지 남겨야 다음에 고칠 수 있습니다.
    if rows and not kept:
        seen = sorted({_location(x) or "?" for x in rows})[:8]
        print(f"      ! greenhouse({code}): 한국 근무지로 인식된 공고가 없습니다. "
              f"받은 근무지: {seen}")
    return kept


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    code = company["code"]

    rows = list_open(code, overseas=bool(company.get("overseas")))

    jobs = []
    for x in rows:
        jid = x.get("id")
        if not jid:
            continue
        # content 는 HTML 이 엔티티로 인코딩돼 옵니다. 한 번 풀어줍니다.
        body = html.unescape(x.get("content") or "")
        text = strip_html(body)
        image_only = len(text) < 50 and "<img" in body.lower()

        jobs.append({
            "id": f"greenhouse-{code}-{jid}",
            "unit": "공고",
            "company": name, "companySlug": slug,
            "title": x.get("title") or "",
            "location": _location(x),
            # Greenhouse 는 신입/경력을 구분해 주지 않습니다.
            "career": "무관",
            "postedAt": (x.get("updated_at") or "")[:10],
            # 마감일이 없습니다. 상시채용으로 표시됩니다.
            "closesAt": "",
            "dday": None,
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": x.get("absolute_url") or "",
            "description": body if not image_only else "",
        })
    return jobs
