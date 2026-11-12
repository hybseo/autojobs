# -*- coding: utf-8 -*-
"""
현대자동차·기아 자체 채용 사이트 수집기. (2026-11-13 대표님 지시로 추가)

두 회사가 같은 채용 시스템을 씁니다. 주소·코드만 다르고 API 모양은 같습니다.

  현대자동차  https://talent.hyundai.com   hgrCd=1  서비스 HM  화면 .hc
  기아        https://career.kia.com        hgrCd=2  서비스 KM  화면 .kc

  목록  GET /api/rec/AP-{HM|KM}-FO-02700?hgrCd=&lang=ko&page=&pageblock=
  상세  GET /api/rec/AP-{HM|KM}-FO-02800?hgrCd=&lang=ko&recuYy=&recuType=&recuCls=
  원문  /apply/applyView.{hc|kc}?recuYy=&recuType=&recuCls=

2026-11-13 PC 크롬에서 확인한 것
--------------------------------
- 채용 화면(applyList)은 접속 대기열(NetFunnel)을 거쳐 열립니다. 이 어댑터는
  화면을 열지 않고, 화면이 쓰는 위 API 를 직접 부릅니다. API 는 대기열 뒤에
  있지 않아 쿠키·로그인 없이 200 이 옵니다. 대기열을 속이거나 건너뛰는 코드는
  없습니다.
- 사이트 스크립트(common.axios.js)가 모든 요청에 붙이는 헤더가 있습니다.
      X-HKMC-SERVICE: HM (기아는 KM)
      X-HKMC-TOKEN:   로그인한 사람의 값. 비로그인이면 비어 있음
  현대차 목록은 헤더 없이도 오지만, 상세와 기아 목록은 이 헤더가 없으면
  400(HTML 오류 화면)이 옵니다. 비로그인 방문자와 똑같이 빈 토큰을 보냅니다.
- recuType 은 공고마다 다릅니다(N2 경력, N5 계약직 등). 원문 주소를 만들 때
  반드시 목록에서 받은 값을 쓰세요. 다른 값을 넣으면 빈 화면이 나옵니다.
- 본문은 HTML 이 아니라 줄바꿈이 든 글자로 옵니다. 항목별로 나뉘어 있습니다.
      aboutTeamNtc 조직소개 · privJdDtl 직무상세 · privMustReq 지원자격
      prefReq 우대사항 · etc 기타 · procStep1Nm~5Nm 전형단계
- 그날 진행중: 현대차 55건, 기아 11건.
"""
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

SITES = {
    "hyundai": {"host": "https://talent.hyundai.com", "hgr": "1", "svc": "HM",
                "ext": "hc", "prefix": "hmc"},
    "kia":     {"host": "https://career.kia.com", "hgr": "2", "svc": "KM",
                "ext": "kc", "prefix": "kia"},
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

PAGE = 100          # 한 번에 받는 건수. 현대차 55건이 한 번에 옵니다.
MAX_PAGES = 10      # 안전장치
DETAIL_GAP = 0.3    # 상세 요청 사이 쉬는 시간(초). 남의 서버입니다.

# 채용 구분(channelCodeNm) → 사이트의 경력 구분
CAREER = {"경력": "경력", "신입": "신입", "신입/경력": "신입/경력",
          "인턴": "무관", "계약직": "무관", "기타": "무관"}

# 근무지가 이 값이면 지명이 아니라 빈칸으로 둡니다.
NO_PLACE = {"", "기타", "기타지역", "직무별 상이", "전국"}

SECTIONS = (("aboutTeamNtc", "조직소개"), ("privJdDtl", "직무상세"),
            ("privMustReq", "지원자격"), ("prefReq", "우대사항"),
            ("etc", "기타"))


def _site(company):
    code = str(company.get("code") or "").strip().lower()
    if code not in SITES:
        raise RuntimeError(f"hkmc: code 는 hyundai 또는 kia 여야 합니다 (받은 값: {code!r})")
    return SITES[code]


def _get(site, path, params):
    url = f"{site['host']}{path}?{urllib.parse.urlencode(params)}"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "User-Agent": UA,
        "Referer": f"{site['host']}/apply/applyList.{site['ext']}",
        "X-HKMC-SERVICE": site["svc"],
        "X-HKMC-TOKEN": "",
        "Connection": "close",
    }
    if site["svc"] == "KM":
        headers["X-HKMC-EMP-TOKEN"] = ""
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} ({path})") from None
    try:
        return json.loads(raw)
    except ValueError:
        # 대기열·오류 화면(HTML)이 오면 여기로 옵니다. 실패로 올려 지난 회차를 유지합니다.
        raise RuntimeError(f"JSON 이 아닌 응답 ({path}): {raw[:80]!r}") from None


def _today():
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y%m%d")


def _ymd(v):
    v = re.sub(r"\D", "", str(v or ""))
    return f"{v[:4]}-{v[4:6]}-{v[6:8]}" if len(v) >= 8 else ""


def _text(v):
    """API 글자 → 보기 좋은 글자. &#91; 같은 것을 풀고 공백 문자를 정리합니다."""
    s = html.unescape(str(v or ""))
    s = s.replace("ㅤ", " ").replace("\r", "")
    return s.strip()


def _para(s):
    return "<p>" + html.escape(s).replace("\n", "<br>") + "</p>"


def body_html(a):
    parts = []
    for key, label in SECTIONS:
        t = _text(a.get(key))
        if t:
            parts.append(f"<h3>{label}</h3>{_para(t)}")
    steps = [_text(a.get(f"procStep{i}Nm")) for i in range(1, 6)]
    steps = [s for s in steps if s]
    if steps:
        parts.append("<h3>전형단계</h3><ol>"
                     + "".join(f"<li>{html.escape(s)}</li>" for s in steps) + "</ol>")
    # 위 항목이 비어 있는 공고는 자유 형식 본문(HTML)을 씁니다.
    if not parts:
        web = str(a.get("recuNoticeWebCont") or "").strip()
        if web:
            parts.append(web)
    return "".join(parts)


def list_open(site):
    """접수중인 공고 목록(목록 API 그대로)."""
    rows, total = [], None
    for page in range(1, MAX_PAGES + 1):
        j = _get(site, f"/api/rec/AP-{site['svc']}-FO-02700", {
            "hgrCd": site["hgr"], "lang": "ko", "page": page, "pageblock": PAGE,
            "searchSectorList": "", "searchSecList": "", "searchPlaceList": "",
            "searchText": ""})
        data = j.get("data") or {}
        got = data.get("list")
        if got is None:
            raise RuntimeError(f"목록 응답에 list 가 없습니다: {str(j)[:120]}")
        rows += got
        total = data.get("listCnt")
        if not got or len(got) < PAGE or (total and len(rows) >= int(total)):
            break
    today = _today()
    return [x for x in rows if re.sub(r"\D", "", str(x.get("applyEndDt") or "99999999")) >= today]


def _source_url(site, x):
    base = f"{site['host']}/apply/applyView.{site['ext']}"
    grp = str(x.get("ntcGroupNo") or "0")
    if str(x.get("groupYn") or "N").upper() == "Y" and grp not in ("", "0"):
        return f"{base}?ntcGroupNo={grp}"
    return (f"{base}?recuYy={x.get('recuYy')}&recuType={x.get('recuType')}"
            f"&recuCls={x.get('recuCls')}")


def fetch(company):
    site = _site(company)
    slug = company["slug"]
    rows = list_open(site)
    jobs = []
    for x in rows:
        yy, typ, cls = x.get("recuYy"), x.get("recuType"), x.get("recuCls")
        if not (yy and typ and cls is not None):
            continue
        desc = ""
        try:
            d = _get(site, f"/api/rec/AP-{site['svc']}-FO-02800", {
                "hgrCd": site["hgr"], "lang": "ko",
                "recuYy": yy, "recuType": typ, "recuCls": cls})
            info = (d.get("data") or {}).get("applyInfo") or {}
            desc = body_html(info)
        except RuntimeError as e:
            # 본문 하나 못 받았다고 공고를 버리지 않습니다. 원문으로 보냅니다.
            print(f"      · {company['name']} {typ}-{cls} 본문 실패: {e}")
        time.sleep(DETAIL_GAP)

        place = _text(x.get("workPlaceCodeNm"))
        chan = _text(x.get("channelCodeNm"))
        jobs.append({
            "id": f"{site['prefix']}-{yy}{typ}{cls}",
            "unit": "공고",
            "company": company["name"],
            "companySlug": slug,
            "title": _text(x.get("recuNoticeNm")),
            "location": "" if place in NO_PLACE else place,
            "career": CAREER.get(chan, "무관"),
            "postedAt": _ymd(x.get("applyStartDt")),
            "closesAt": _ymd(x.get("applyEndDt")),
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": _source_url(site, x),
            "description": desc,
        })
    return jobs
