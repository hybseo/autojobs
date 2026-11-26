# -*- coding: utf-8 -*-
"""
「/rem/apply/」 채용 사이트 수집기 (2026-11-27, 시험 중).

GS칼텍스(recruit.gscaltex.com)와 대우건설(erecruit.daewooenc.com)이 같은
채용 시스템을 씁니다. 화면 주소가 둘 다 /rem/apply/recruit/apply_list.jsp 이고
공고 목록은 자바스크립트가 /Application.do 로 요청해서 그립니다.

목록 요청 (화면 코드 util.js · common.js 에서 확인)
---------------------------------------------------
    POST https://{도메인}/Application.do
    헤더  ajax: true
    본문  (폼 값) S_DSCLASS=biz.rem.apply.recruit.Apply_list
                 S_DSMETHOD=search01
                 S_FORWARD=xsheetResultXML
                 S_PAGE_NO=1 … (화면 f1 폼의 숨은 칸)
                 S_PGM_OPEN_TIME · S_ENC_OTP_KEY · S_CSRF_SALT · S_POP_URL (화면 변수, 보통 빈 값)
                 __viewState = 위 값들을 JSON 으로 묶은 문자열 (AjaxUtil.makeParameters)
    응답  XML(xsheet). 줄마다 C_CD · REM_NO · REM_TYPE_CD(10 신입 / 20 경력 / 30 인턴·계약) …

__viewState (common.js 의 toJsonString · calcHash 를 그대로 옮김)
    칸 이름에 RE_NO · SEQ_NO · C_CD · APPL_NO · USER_ID 가 들어간 칸만 골라
      order = 그 칸 이름들을 순서대로 「이름,」 로 이은 것
      test  = 그 칸 값마다 공백·쉼표를 지우고 encodeURIComponent 한 뒤 영문·숫자·_ 만 남겨 이은 것
      hash  = test 를 SHA-256 으로 3번 거듭 돌린 16진수 (jsSHA numRounds=3)
    '{"order":"…", "hash":"…", "test":"…"}' 문자열입니다. 서버가 이 값으로 요청이
    화면에서 온 것인지 봅니다. 빼거나 틀리면 HTTP 500 이 납니다(2026-11-27 확인).

companies.json 의 code 에는 도메인만 적습니다. 예: "recruit.gscaltex.com"
"""
import hashlib
import html
import http.cookiejar
import json
import re
import ssl
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
LIST = "/rem/apply/recruit/apply_list.jsp"
CAREER = {"10": "신입", "20": "경력", "30": "무관"}


def _opener():
    ctx = ssl.create_default_context()
    ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        urllib.request.HTTPSHandler(context=ctx))


def _page_values(page):
    vals = {}
    for m in re.finditer(r'<input[^>]*type="hidden"[^>]*>', page):
        tag = m.group(0)
        n = re.search(r'name="([^"]+)"', tag)
        if not n:
            continue
        v = re.search(r"value=[\"']([^\"']*)[\"']", tag)
        vals[n.group(1)] = html.unescape(v.group(1)) if v else ""
    for k in ("S_PGM_OPEN_TIME", "S_ENC_OTP_KEY", "S_CSRF_SALT"):
        m = re.search(r"var\s+%s\s*=\s*\"([^\"]*)\"" % k, page)
        vals[k] = m.group(1) if m else ""
    vals["S_POP_URL"] = ""
    return vals


def _check(name):
    return any(k in name for k in ("RE_NO", "SEQ_NO", "C_CD", "APPL_NO", "USER_ID"))


def _enc(v):
    """자바스크립트 encodeURIComponent 와 같게."""
    return urllib.parse.quote(v, safe="-_.!~*'()")


def view_state(params):
    order, test = "", ""
    for k, v in params.items():
        if k == "__viewState" or not _check(k):
            continue
        order += k + ","
        t = re.sub(r"[ ,\s]", "", "" if v is None else str(v))
        test += re.sub(r"\W", "", _enc(t))
    h = test.encode("utf-8")
    for _ in range(3):
        h = hashlib.sha256(h).digest()
    return '{"order":"%s", "hash":"%s", "test":"%s"}' % (order, h.hex(), test)


def _rows(xml):
    """xsheet XML 을 줄(dict) 목록으로. 모양을 모르는 동안은 넓게 잡습니다."""
    rows = []
    # 흔한 모양 1: <ROW><COL_NAME>값</COL_NAME>…</ROW>
    for r in re.findall(r"<(?:ROW|row|Row)\b[^>]*>(.*?)</(?:ROW|row|Row)>", xml, re.S):
        d = {k: html.unescape(re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", v, flags=re.S)).strip()
             for k, v in re.findall(r"<([A-Z_0-9]+)>(.*?)</\1>", r, re.S)}
        if d:
            rows.append(d)
    if rows:
        return rows
    # 흔한 모양 2: 머리줄에 칸 이름, 줄마다 값 (TD)
    cols = re.findall(r'<(?:COL|col|Column|COLUMN)\b[^>]*(?:id|name|ID|NAME)="([^"]+)"', xml)
    for r in re.findall(r"<(?:TR|tr|R)\b[^>]*>(.*?)</(?:TR|tr|R)>", xml, re.S):
        vals = [html.unescape(re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", v, flags=re.S)).strip()
                for v in re.findall(r"<(?:TD|td|C)\b[^>]*>(.*?)</(?:TD|td|C)>", r, re.S)]
        if cols and vals:
            rows.append(dict(zip(cols, vals)))
    return rows


def list_raw(domain):
    op = _opener()
    base = f"https://{domain}"
    head = {"User-Agent": UA}
    with op.open(urllib.request.Request(base + LIST, headers=head), timeout=30) as r:
        page = r.read().decode("utf-8", "replace")
    params = _page_values(page)
    params.update({"S_PAGE_NO": "1", "S_DSCLASS": "biz.rem.apply.recruit.Apply_list",
                   "S_DSMETHOD": "search01", "S_FORWARD": "xsheetResultXML"})
    params["__viewState"] = view_state(params)
    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(base + "/Application.do", data=body, method="POST", headers={
        "User-Agent": UA, "ajax": "true", "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": base + LIST, "Origin": base})
    with op.open(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace"), params


def fetch(company):
    domain = company["code"]
    xml, params = list_raw(domain)
    rows = _rows(xml)
    print(f"      · ehr_rem({domain}): 보낸 칸 {sorted(params)}")
    print(f"      · ehr_rem({domain}): 응답 {len(xml)}자, 줄 {len(rows)}개")
    if not rows:
        print("      · 응답 앞부분: " + re.sub(r"\s+", " ", xml[:1500]))
        return []
    print("      · 첫 줄 칸: " + json.dumps(rows[0], ensure_ascii=False)[:800])
    return []
