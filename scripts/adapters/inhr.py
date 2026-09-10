# -*- coding: utf-8 -*-
"""
inhr(careerlink) 채용 사이트 수집기.

목록  POST https://api.inhr.co.kr/v1/recruit/jd/list
원문  https://{회사}.careerlink.kr/jobs/{rcrtNo}

동진쎄미켐이 이걸 씁니다. 회사마다 {회사}.careerlink.kr 주소를 받고,
데이터는 모두 api.inhr.co.kr 한 곳에서 옵니다.

code 는 두 값을 쉼표로 붙여 적습니다
--------------------------------------
    "code": "CO202504082484,dongjin"
             ↑ 회사번호(coNo)      ↑ 사이트 이름

앞은 API 에 보낼 회사번호, 뒤는 원문 주소를 만들 하위도메인입니다.
둘 다 필요합니다. 회사번호만으로는 공고 주소를 만들 수 없습니다.

회사번호 찾는 법
    1. {회사}.careerlink.kr 을 엽니다
    2. 개발자도구 Network 에서 jd/list 요청을 찾습니다
    3. 요청 본문의 coNo 값이 그것입니다

careerlink.kr 주소로 api.inhr.co.kr 을 부르지 마세요
-----------------------------------------------------
dongjin.careerlink.kr/v1/recruit/jd/list 로 부르면 404 입니다.
화면은 careerlink 주소를 쓰지만 실제 데이터는 api.inhr.co.kr 에서
옵니다. 처음에 이걸 몰라 헤맸습니다.

빈 본문을 보내면 400 입니다
---------------------------
coNo 가 없으면 400 이 떨어집니다. 어느 회사인지 알려주지 않으면
서버가 답할 수 없습니다. 인증 토큰은 필요 없습니다.

본문에 대하여
------------
2026-09-10 동진쎄미켐 확인 기준 rcrtCntn 이 이미지 한 장뿐이었습니다.

    <p><img src="https://img.inhr.co.kr/.../CONTENT_IMAGE/....png"></p>

태그를 걷어내면 글자가 0자입니다. 글자를 읽을 수 없으므로 원문으로
보냅니다. 나중에 텍스트 본문을 쓰는 회사가 생기면 아래 판정이
자동으로 처리합니다.

상시채용에 대하여
-----------------
"생산직 인재 POOL" 처럼 마감일(rcrtAcptEndDtm)이 없는 공고가 있습니다.
비워 두면 사이트가 상시채용으로 표시합니다.

응답 구조 (2026-09-10 실제 확인)
--------------------------------
{ "code": "0000", "message": "성공",
  "data": { "rcrtList": [ ... ] } }

    rcrtNo           RC20260831033832   공고 번호. 원문 주소에 들어갑니다
    coNm             동진쎄미켐          회사명
    rcrtNm                              공고 제목
    carrTypeGbcdNm   무관               경력 구분
    hireTypeGbcdNm   정규직             고용형태
    rcrtAcptStrtDtm  2026-09-01 00:00:00  접수 시작
    rcrtAcptEndDtm   2026-09-10 23:59:59  접수 마감. 없으면 상시
    rcrtCntn                            본문 HTML
"""
import html
import json
import re
import time
import urllib.error
import urllib.request

API = "https://api.inhr.co.kr/v1/recruit/jd/list"
SITE = "https://{}.careerlink.kr/jobs/{}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
      "(+https://searchjob.co.kr job aggregator)")

# carrTypeGbcdNm 이 한글로 그대로 옵니다. 표에 없으면 "무관" 으로 접습니다.
CAREER = {"경력": "경력", "신입": "신입", "무관": "무관",
          "신입/경력": "신입/경력", "경력무관": "무관", "인턴": "무관"}


def _post(body):
    """일시적 실패만 몇 초 쉬었다 다시 시도합니다."""
    req = urllib.request.Request(
        API, method="POST", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json",
                 "User-Agent": UA})
    last = None
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 400:
                raise RuntimeError(
                    "inhr: 400 입니다. code 앞자리에 회사번호(coNo)가 "
                    "제대로 들어갔는지 확인하세요.") from None
            raise
        except Exception as e:
            last = e
            if i < 2:
                time.sleep(2 + i * 2)
    raise last


def _split_code(code):
    """'CO202504082484,dongjin' → ('CO202504082484', 'dongjin')."""
    parts = [p.strip() for p in str(code or "").split(",")]
    co = parts[0] if parts else ""
    site = parts[1] if len(parts) > 1 else ""
    if not co:
        raise RuntimeError(
            "inhr: code 가 비어 있습니다. "
            "'회사번호,사이트이름' 형식으로 적으세요. "
            "예: CO202504082484,dongjin")
    return co, site


def _date(v):
    """'2026-09-10 23:59:59' → '2026-09-10'. 없으면 빈 문자열(상시채용)."""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(v or ""))
    if not m:
        return ""
    # 먼 미래 날짜는 상시채용을 뜻하는 가짜 값입니다.
    if int(m.group(1)) >= 2100:
        return ""
    return m.group(0)


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", html.unescape(s)).strip()


def list_open(code):
    """공고 목록. probe 용으로 밖에서도 씁니다."""
    co, _ = _split_code(code)
    j = _post({"coNo": co, "pageNo": 1, "pageSize": 200})

    if str(j.get("code")) != "0000":
        print(f"  ! inhr({co}): 응답이 성공이 아닙니다. {j.get('message')}")
        return []

    rows = ((j.get("data") or {}).get("rcrtList")) or []
    if not rows:
        print(f"  ! inhr({co}): 공고 목록이 비어 있습니다. "
              f"회사번호가 맞는지 확인하세요.")
    return rows


def fetch(company):
    """companies.json 항목 하나를 받아 공고 리스트를 돌려줍니다."""
    name = company["name"]
    slug = company["slug"]
    co, site = _split_code(company["code"])

    rows = list_open(company["code"])

    jobs = []
    for x in rows:
        no = (x.get("rcrtNo") or "").strip()
        if not no:
            continue

        raw = x.get("rcrtCntn") or ""
        text = strip_html(raw)
        # 본문이 이미지뿐인 공고가 많습니다. 글자를 읽을 수 없어 원문으로 보냅니다.
        image_only = len(text) < 50 and "<img" in raw.lower()

        # 정규직이 아니면 제목에 표시합니다.
        title = (x.get("rcrtNm") or "").strip()
        emp = (x.get("hireTypeGbcdNm") or "").strip()
        if emp and emp != "정규직" and emp not in title:
            title = f"{title} ({emp})"

        jobs.append({
            "id": f"inhr-{no}",
            "unit": "공고",
            # 회사명을 응답에서 그대로 씁니다. 계열사가 섞여 오는 곳이 있습니다.
            "company": (x.get("coNm") or name).strip(),
            "companySlug": slug,
            "title": title,
            # 근무지를 주지 않습니다. 지어내지 않습니다.
            "location": "",
            "career": CAREER.get((x.get("carrTypeGbcdNm") or "").strip(), "무관"),
            "postedAt": _date(x.get("rcrtAcptStrtDtm")),
            # 마감일이 없으면 상시채용으로 표시됩니다.
            "closesAt": _date(x.get("rcrtAcptEndDtm")),
            "dday": None,
            "multiRole": image_only,
            "sourceTitle": "",
            # 사이트 이름이 없으면 주소를 만들 수 없습니다. 그때는 목록으로 보냅니다.
            "sourceUrl": (SITE.format(site, no) if site
                          else f"https://{co}.careerlink.kr/jobs"),
            "description": raw if not image_only else "",
        })

    return jobs
