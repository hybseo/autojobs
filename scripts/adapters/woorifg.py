# -*- coding: utf-8 -*-
"""
우리금융그룹 통합 채용공고 목록 수집기 (2026-11-26 대표님 지시로 추가).

  목록  GET https://www.woorifg.com/kor/recruit/recruit-announcement/list.do?pageIndex=N

우리은행·우리카드·우리금융에프앤아이 등 그룹사가 이 목록 한 곳에 공고를 올립니다.
「진행중인 채용 공고 N개」만 보여 주는 목록이라 여기 있으면 접수중입니다.

2026-11-26 깃허브 러너에서 확인한 것
------------------------------------
- 한 쪽에 10건씩. 쪽 번호는 pageIndex 입니다(화면의 commonCtrl.pagination(2)).
- 한 줄이 <div class="list"> 하나입니다. 칸은 구분(경력·신입·무관)·그룹사명·제목·등록일자.
  마감일 칸이 없습니다. 지어내지 않고 비워 둡니다(사이트에서 상시로 보임).
- 제목 링크가 두 가지입니다.
    ./view.do?seq=120        우리금융그룹 사이트 안의 공고 본문
    window.open('https:////recruit.incruit.com/wooribank/job/2610210004')
                             우리은행은 인크루트 채용 페이지로 엽니다. 슬래시가 네 개라 고칩니다.
- 서버가 예전 방식 TLS 재협상을 요구해서 그냥 접속하면 SSL 오류가 납니다
  (UNSAFE_LEGACY_RENEGOTIATION_DISABLED). 이 사이트에만 OP_LEGACY_SERVER_CONNECT 를 켭니다.
"""
import html
import re
import ssl
import time
import urllib.request

BASE = "https://www.woorifg.com/kor/recruit/recruit-announcement/"
LIST = BASE + "list.do?pageIndex={}"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")
PAGE_MAX = 10

ROW = re.compile(r'<div class="list">\s*(.*?)<div class="filings font-mont"[^>]*>\s*([\d.]+)\s*</div>', re.S)
CELL = re.compile(r'<div class="filings"[^>]*>\s*(.*?)\s*</div>', re.S)
LINK = re.compile(r'<a\b([^>]*)>(.*?)</a>', re.S)

CAREER = {"경력": "경력", "신입": "신입", "무관": "무관", "신입/경력": "신입/경력"}


def _ctx():
    c = ssl.create_default_context()
    c.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
    return c


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last = None
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25, context=_ctx()) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(2 + i * 2)
    raise last


def _text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def _url(attrs):
    m = re.search(r"window\.open\('([^']+)'", attrs.replace("\n", ""))
    if m:
        u = re.sub(r"^https?:/+", "https://", m.group(1).strip())
        return u
    m = re.search(r'href="\./(view\.do\?seq=\d+)', attrs)
    if m:
        return BASE + m.group(1)
    return ""


def list_open():
    rows, seen = [], set()
    for page in range(1, PAGE_MAX + 1):
        raw = _get(LIST.format(page))
        got = 0
        for body, date in ROW.findall(raw):
            cells = [_text(c) for c in CELL.findall(body)]
            a = LINK.search(body)
            if not a or len(cells) < 2:
                continue
            seq = re.search(r'data-seq="(\d+)"', a.group(1))
            key = seq.group(1) if seq else _text(a.group(2))
            if key in seen:
                continue
            seen.add(key)
            got += 1
            rows.append({"seq": key, "kind": cells[0], "company": cells[1],
                         "title": _text(a.group(2)), "url": _url(a.group(1)),
                         "posted": date.replace(".", "-")})
        if not got:
            break
        time.sleep(0.5)
    if not rows:
        print("      ! 우리금융그룹: 공고를 하나도 찾지 못했습니다. 화면 구조가 바뀌었는지 보세요. " + LIST.format(1))
    return rows


def fetch(company):
    name, slug = company["name"], company["slug"]
    jobs = []
    for x in list_open():
        jobs.append({
            "id": f"woorifg-{x['seq']}",
            "unit": "공고",
            "company": x["company"] or name,
            "companySlug": slug,
            "title": x["title"],
            "location": "",
            "career": CAREER.get(x["kind"], "무관"),
            "postedAt": x["posted"],
            # 목록에 마감일이 없습니다. 지어내지 않습니다.
            "closesAt": "",
            "dday": None,
            "multiRole": False,
            "sourceTitle": "",
            "sourceUrl": x["url"] or LIST.format(1),
            # 목록에 본문이 없습니다. 원문으로 보냅니다.
            "description": "",
        })
    return jobs
