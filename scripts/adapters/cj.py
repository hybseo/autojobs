# -*- coding: utf-8 -*-
"""
CJ그룹 통합 채용(recruit.cj.net) 수집기. (2026-11-26 대표님 지시로 추가)

  목록  POST https://recruit.cj.net/recruit/ko/recruit/recruit/searchNewGonggoList.fo
        본문 pageNo=1 (폼 형식)
  원문  공채  https://recruit.cj.net/recruit/ko/recruit/recruit/detail.fo?zz_jo_num={번호}
        수시  https://recruit.cj.net/recruit/ko/recruit/recruit/bestDetail.fo?direct=N&zz_jo_num={번호}

CJ는 그리팅·리크루터 같은 흔한 채용 서비스를 쓰지 않고 그룹 자체 사이트를 씁니다.
그래서 채용 서비스 주소를 두드리는 탐지로는 잡히지 않았습니다.

2026-11-26 깃허브 러너에서 확인한 것
------------------------------------
- 채용공고 화면(list.fo)이 위 목록 주소를 부릅니다. 로그인·쿠키 없이 JSON 이 옵니다.
  응답 ds_newRecruitList 에 공고가 한 번에 다 실려 옵니다(그날 168건, tot_cnt 168).
- 한 줄의 값 (화면 스크립트가 쓰는 뜻 그대로)
    zz_jo_num      공고 번호. 공채는 8634 같은 숫자, 수시는 J20261125041138 같은 글자
    gubun          1 공채 · 2 수시(화면 주석 '타스'). 원문 주소가 다릅니다(위 참고)
    compnm         계열사명 (CJ ENM, TVING, CJ대한통운 …)
    zz_title       제목
    zz_str_dt_str  시작일 2026.11.25     zz_end_dt_str 마감일 2026.12.20 (상시는 null)
    zz_till_hire   Y 면 「채용시까지」
    zz_target_1    A 신입 · B 경력 · C 인턴 · E 신입·경력 · K 기타 (list.fo 스크립트에서 확인)
    zz_close_yn    Y 면 이미 마감. 목록에 마감된 공고가 섞여 옵니다(그날 34건). 거릅니다.
    location_cd_nm 근무지 (서울, 충북 음성 …)
- 원문 본문은 <ul class="detail-list"> 부터 <!-- // 메인 내용 --> 앞까지입니다.
  수시 공고는 직무소개·지원자격·우대사항이 글자로 있고, 공채는 공고문을 그림 한 장
  (poster_type)으로 올린 것이 많습니다. 그림뿐이면 다른 수집기와 같이 multiRole=True.

계열사와 산업
-------------
한 항목에 CJ ENM·CJ제일제당·CJ대한통운 등이 함께 들어옵니다. 계열사별 산업은
companies.json 의 affiliateIndustry 로 나눕니다. 회사명은 compnm 을 그대로 씁니다.
"""
import html
import json
import re
import time
import urllib.parse
import urllib.request

BASE = "https://recruit.cj.net/recruit/ko/recruit/recruit/"
LIST = BASE + "searchNewGonggoList.fo"
VIEW = {"1": BASE + "detail.fo?zz_jo_num={}",
        "2": BASE + "bestDetail.fo?direct=N&zz_jo_num={}"}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

CAREER = {"A": "신입", "B": "경력", "C": "무관", "E": "신입/경력", "K": "무관"}

BODY = re.compile(r'<ul class="detail-list">(.*?)<!--\s*//\s*메인 내용\s*-->', re.S)


def _open(req, as_json):
    last = None
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode("utf-8", "replace")
                return json.loads(raw) if as_json else raw
        except Exception as e:
            last = e
            time.sleep(2 + i * 2)
    raise last


def _list(page):
    data = urllib.parse.urlencode({"pageNo": page}).encode()
    req = urllib.request.Request(LIST, data=data, method="POST", headers={
        "User-Agent": UA, "Accept": "application/json, text/javascript, */*",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest"})
    return _open(req, True)


def list_open():
    rows, seen, page = [], set(), 1
    while page <= 10:
        d = _list(page)
        got = d.get("ds_newRecruitList") or []
        new = [x for x in got if str(x.get("zz_jo_num")) not in seen]
        for x in new:
            seen.add(str(x.get("zz_jo_num")))
        rows += new
        total = int((got[0].get("tot_cnt") if got else 0) or 0)
        # 그날은 한 번에 다 왔습니다. 나눠 올 때만 다음 쪽을 봅니다.
        if not new or len(rows) >= total:
            break
        page += 1
        time.sleep(0.5)
    if not rows:
        print("      ! CJ그룹: 공고를 하나도 받지 못했습니다. " + LIST)
    open_ = [x for x in rows
             if str(x.get("zz_close_yn") or "N") != "Y" and str(x.get("zz_open_yn") or "Y") == "Y"]
    print(f"      · CJ그룹: 받은 {len(rows)}건 중 접수중 {len(open_)}건")
    return open_


def _text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _clean(body):
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    body = re.sub(r"(?is)<(svg|style|script)\b.*?</\1>", "", body)
    body = re.sub(r"(?is)<meta[^>]*>", "", body)
    return body.strip()


def detail(url):
    """(본문 HTML, 그림뿐인지). 못 가져오면 ("", False)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        m = BODY.search(_open(req, False))
    except Exception as e:
        print(f"      ! CJ그룹 원문을 못 열었습니다 {type(e).__name__} · {url}")
        return "", False
    if not m:
        return "", False
    body = _clean(m.group(1))
    # 통이미지 공고의 그림 위 투명 링크(공고리스트·채용블로그 등) 글자는 본문이 아닙니다.
    words = _text(re.sub(r'(?is)<a\b[^>]*class="overlay"[^>]*>.*?</a>', "", body))
    image_only = len(words) < 50 and "<img" in body.lower()
    return body, image_only


def _date(s):
    m = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", str(s or ""))
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""


def fetch(company):
    name, slug = company["name"], company["slug"]
    jobs = []
    for x in list_open():
        no = str(x.get("zz_jo_num") or "").strip()
        if not no:
            continue
        url = VIEW.get(str(x.get("gubun")), VIEW["2"]).format(urllib.parse.quote(no))
        body, image_only = detail(url)
        always = str(x.get("zz_till_hire")) == "Y" or not x.get("zz_end_dt_str")
        dday = x.get("dday")
        jobs.append({
            "id": f"cj-{no}",
            "unit": "공고",
            "company": str(x.get("compnm") or "").strip() or name,
            "companySlug": slug,
            # 제목에 <BR> 같은 줄바꿈 태그가 섞여 옵니다(CJ대한통운 건설부문 등).
            # 태그를 빈칸으로 바꾸고 엔티티(&amp; 등)도 풀어 둡니다. (2026-11-26)
            "title": re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(x.get("zz_title") or "")))).strip(),
            "location": str(x.get("location_cd_nm") or "").strip(),
            "career": CAREER.get(str(x.get("zz_target_1") or ""), "무관"),
            "postedAt": _date(x.get("zz_str_dt_str")),
            # 「채용시까지」는 상시로 둡니다. 마감일을 지어내지 않습니다.
            "closesAt": "" if always else _date(x.get("zz_end_dt_str")),
            # 상시 공고는 dday 가 88888 처럼 옵니다. 날짜가 있을 때만 씁니다.
            "dday": dday if (not always and isinstance(dday, int) and 0 <= dday < 1000) else None,
            "multiRole": image_only,
            "sourceTitle": "",
            "sourceUrl": url,
            "description": "" if image_only else body,
        })
        time.sleep(0.3)
    return jobs
