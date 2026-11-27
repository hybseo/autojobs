# -*- coding: utf-8 -*-
"""
공고 본문(description) 줄이기 (2026-11-27 대표님 지시).

왜
---
jobs.json 이 95MB 가 되어 깃허브 한도(100MiB)에 닿기 직전이었습니다.
90MB 가 본문이었고, 큰 덩어리는 글이 아니었습니다.

    에스엘 공고 1건 3.1MB  웹페이지 머리말·스크립트까지 통째로 담김
    동아쏘시오 1건 2.3MB   그림이 base64 글자로 본문에 박힘
    CJ푸드빌 340KB × 여러 건  style 속성과 공백

화면은 원문 HTML 을 그리지 않습니다(요약을 그립니다). 원문은 태그 뽑기,
직무 분류, 요약 작성 재료로만 씁니다. 그래서 글자는 남기고 껍데기만 덜어냅니다.

무엇을 지우나
-------------
  1. <script> <style> <head> <noscript> <svg> 와 HTML 주석 — 통째로
  2. base64 그림(data: 주소) — 그 태그 통째로 (lib.js stripDataImages 와 같은 규칙)
  3. 태그의 속성 — href · src · colspan · rowspan 만 남기고 모두
     (style="font-size:11pt;…" 가 공고마다 수천 번 반복됩니다)
  4. 빈 <span>·<font> 껍데기 — 태그만 지우고 안의 글자는 남김
  5. 연속 공백 — 한 칸으로
  6. 그래도 MAX_CHARS 를 넘으면 그 길이에서 자르고 잘린 태그 조각을 지움
     (2026-11-27 기준 넘는 공고는 없습니다. 6만 자로 했더니 에스엘의
      여러 포지션 공고 뒷부분 글이 잘려 10만 자로 올렸습니다)

남기는 것
---------
  · 글자 전부(1~5 단계는 글자를 지우지 않습니다)
  · 그림 주소(<img src="https://…">) — 그림 공고인지 판단에 씁니다
  · 문단·목록·표 태그 — 요약할 때 줄 나눔에 씁니다
"""
import re

MAX_CHARS = 100000  # 안전장치. 정리 후 가장 긴 공고(에스엘, 여러 포지션을 한 페이지에)가 8만 자입니다.

_BLOCKS = re.compile(r"(?is)<(script|style|head|noscript|svg|iframe)\b.*?</\1\s*>")
_COMMENT = re.compile(r"(?s)<!--.*?-->")
_DOCTYPE = re.compile(r"(?i)<!doctype[^>]*>|</?(html|body|meta|link)\b[^>]*>")
_DATA = re.compile(r"data:[a-z0-9.+-]*/?[a-z0-9.+-]*;base64,", re.I)
_DATA_RUN = re.compile(r"data:[a-z0-9.+-]*/?[a-z0-9.+-]*;base64,[A-Za-z0-9+/=\s]*", re.I)
_TAG = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>")
_KEEP_ATTR = re.compile(r"""\b(href|src|colspan|rowspan)\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""", re.I)
_WRAPPERS = re.compile(r"(?i)</?(span|font|o:p|st1:[a-z]+)\b[^>]*>")
_EMPTY = re.compile(r"(?i)<(p|div|li|strong|b|em|i|u|section)>\s*</\1>")


def _ws(t):
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    return re.sub(r" *\n\s*", "\n", t)


def _tag(m):
    close, name, attrs = m.group(1), m.group(2).lower(), m.group(3)
    if close:
        return f"</{name}>"
    if name in ("img", "source") and _DATA.search(attrs):
        return ""
    keep = []
    for a in _KEEP_ATTR.finditer(attrs):
        val = a.group(2)
        if _DATA.search(val):
            continue
        keep.append(f"{a.group(1).lower()}={val}")
    end = " /" if attrs.rstrip().endswith("/") else ""
    return f"<{name}{(' ' + ' '.join(keep)) if keep else ''}{end}>"


def slim(html):
    if not html or not isinstance(html, str):
        return html
    t = _BLOCKS.sub(" ", html)
    t = _COMMENT.sub(" ", t)
    t = _DOCTYPE.sub(" ", t)
    t = _TAG.sub(_tag, t)
    t = _DATA_RUN.sub("", t)
    t = _WRAPPERS.sub("", t)
    t = t.replace("​", "").replace("&nbsp;", " ").replace("\xa0", " ")
    # 빈 껍데기를 지우면 공백이 다시 붙고, 공백을 줄이면 껍데기가 다시 비어
    # 보입니다. 더 바뀌지 않을 때까지 번갈아 돌립니다. 같은 본문을 두 번 넣어도
    # 결과가 같아야 매일 수집 때 쓸데없는 변경이 생기지 않습니다.
    for _ in range(20):
        t2 = _ws(_EMPTY.sub("", _ws(t)))
        if t2 == t:
            break
        t = t2
    t = t.strip()
    if len(t) > MAX_CHARS:
        t = re.sub(r"<[^>]*$", "", t[:MAX_CHARS])
    return t
