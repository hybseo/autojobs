# -*- coding: utf-8 -*-
"""
다우기술 채용 사이트 수집기.

목록  GET https://recruit.daou.co.kr/api/recruitment/list
상세  GET https://recruit.daou.co.kr/api/recruitment/detail?reNo={reNo}&annSeqNo={annSeqNo}

인증 토큰은 필요 없습니다. 대신 함정이 세 개 있으니 반드시 지킬 것.

함정 1 — 응답이 XML 입니다
API 라는 이름과 달리 Content-Type 이 JSON 이 아니라 XML(HashMap) 입니다.
json.loads() 를 쓰면 그대로 깨집니다. xml.etree.ElementTree 로 파싱하세요.

함정 2 — comNm 필드를 믿지 마세요
목록 API 응답의 comNm(회사명) 이 실제로는 "LS전선"으로 잘못 내려옵니다.
사이트 자체는 다우기술 공식 채용 페이지가 맞고, LS전선과는 무관합니다.
아마 다우기술이 여러 그룹사 채용 시스템을 같은 템플릿으로 만들면서 생긴
설정 누락으로 보입니다. 회사명은 API 값을 쓰지 말고 companies.json 의
company["name"] 을 그대로 씁니다.

함정 3 — 접수중 판별
status 가 "접수중" 인 것만 접수중입니다. 목록 API 에 별도 필터 파라미터가
없어 요청 시점에 전체가 내려오므로, 응답에서 status 로 한 번 더 걸러야
합니다.

날짜 필드에 대하여
------------------
목록 항목의 gigan 은 "2026.08.31~2026.09.10" 형태의 접수기간 문자열입니다.
postedAt(접수 시작)·closesAt(접수 마감) 을 여기서 그대로 뽑습니다.
dday 는 API 가 "D-1" 같은 문자열로 이미 계산해 주므로 숫자만 뽑아 씁니다.
숫자가 아닌 값(예: 상시채용류 표기)이 오면 조용히 None 으로 둡니다.

본문에 대하여
------------
2026-09 확인 기준으로 본 API 가 주는 상세 본문(annTxt)은 텍스트가 아니라
전부 이미지 링크(<img>)로 되어 있었습니다. 다우기술 블로그 카드형 이미지를
본문 대신 넣는 방식으로 보입니다. recruiter.py 의 image_only 판정과 같은
기준으로 텍스트가 사실상 없으면 multiRole=True 로 표시하고 description 은
비웁니다. 이후 다우기술이 템플릿을 바꿔 실제 텍스트 본문이 오는 공고가
생기면 자동으로 정상 처리됩니다(아래 strip_html 결과 길이로 판정하므로).
"""

import html
import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

BASE = "https://recruit.daou.co.kr"

# 경력구분: enterTypeNm 이 이미 "신입"/"경력" 그대로 옵니다.
# 혹시 모를 다른 값(예: "인턴")은 사이트 career 필터 값에 없으므로 "무관"으로 접습니다.
CAREER_OK = {"신입", "경력", "신입/경력", "무관", "분야별상이"}


def _get(path, params=None):
    """XML 응답을 받아 ElementTree 루트로 돌려줍니다.
    일시적 실패(타임아웃·연결오류)만 몇 초 쉬었다 재시도합니다.
    """
    url = BASE + path
    if params:
        from urllib.parse import urlencode

        url += "?" + urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    last = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return ET.fromstring(resp.read())
        except urllib.error.HTTPError:
            raise  # 4xx/5xx는 재시도해도 같습니다.
        except Exception as e:
            last = e
            time.sleep(2)
    raise last


def _career(enter_type_nm):
    v = (enter_type_nm or "").strip()
    return v if v in CAREER_OK else "무관"


def _parse_gigan(gigan):
    """'2026.08.31~2026.09.10' → ('2026-08-31', '2026-09-10'). 못 읽으면 ('','')."""
    if not gigan or "~" not in gigan:
        return "", ""
    sta, end = gigan.split("~", 1)
    sta = sta.strip().replace(".", "-")
    end = end.strip().replace(".", "-")
    return sta, end


def _parse_dday(dday_str):
    """'D-1' → 1, 'D+3' → -3(마감 지남을 음수로), 그 외(예: '상시') → None."""
    if not dday_str:
        return None
    m = re.match(r"D([+-])(\d+)", dday_str.strip())
    if not m:
        return None
    sign, num = m.groups()
    n = int(num)
    return -n if sign == "+" else n


def strip_html(raw):
    text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    text = re.sub(r"</(p|div|li|tr|h\d)>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{2,}", "\n", html.unescape(text)).strip()


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]

    root = _get("/api/recruitment/list")
    rows = root.findall("./resultData/recruitmentList")

    jobs = []
    for row in rows:

        def text(tag, default=""):
            el = row.find(tag)
            return el.text if el is not None and el.text else default

        status = text("status")
        if status != "접수중":
            continue

        re_no = text("reNo")
        ann_seq_no = text("annSeqNo", "1")
        jid = f"daou-{re_no}-{ann_seq_no}"

        locations = [
            el.text for el in row.findall("./locationNms/locationNms") if el.text
        ]

        posted_at, closes_at = _parse_gigan(text("gigan"))

        try:
            detail = _get(
                "/api/recruitment/detail",
                {"reNo": re_no, "annSeqNo": ann_seq_no},
            )
            ann_txt_el = detail.find("./resultData/annTxt")
            raw = ann_txt_el.text if ann_txt_el is not None and ann_txt_el.text else ""
        except Exception:
            raw = ""

        text_only = strip_html(raw)
        # 본문이 이미지 한 장뿐인 공고는 세부 직무를 읽을 수 없습니다.
        # 억지로 분해하지 않고 원문으로 보냅니다.
        image_only = len(text_only) < 30 and "<img" in raw.lower()

        jobs.append(
            {
                "id": jid,
                "unit": "공고",
                "company": name,
                "companySlug": slug,
                "title": text("annTitle"),
                "location": "/".join(locations),
                "career": _career(text("enterTypeNm")),
                "postedAt": posted_at,
                "closesAt": closes_at,
                "dday": _parse_dday(text("dday")),
                "multiRole": image_only,
                "sourceTitle": "",
                "sourceUrl": f"{BASE}/detail/{re_no}/{ann_seq_no}",
                # 본문이 있으면 상세 페이지와 JobPosting 스키마가 생성됩니다.
                "description": raw if not image_only else "",
            }
        )
        time.sleep(0.2)

    return jobs
