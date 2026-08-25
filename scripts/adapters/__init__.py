# -*- coding: utf-8 -*-
"""
채용 시스템(ATS)별 수집기를 모아둔 곳입니다.

새 ATS 를 붙이는 방법
---------------------
1. 이 폴더에 <이름>.py 를 만듭니다. 예: greeting.py
2. 그 안에 fetch(company) 함수를 하나 만듭니다.
3. src/data/companies.json 에서 "ats": "<이름>" 으로 기업을 등록합니다.

그러면 fetch_jobs.py 가 알아서 찾아 씁니다. fetch_jobs.py 는 고치지 않아도 됩니다.

fetch(company) 규약
-------------------
company 는 companies.json 의 항목 하나가 그대로 들어옵니다.
반환값은 아래 형태의 dict 리스트입니다. 키 이름과 의미를 반드시 지켜주세요.
사이트(src/lib.js)가 이 형태를 그대로 읽습니다.

  id           공고 고유 ID. 실행할 때마다 같은 값이 나와야 합니다.
               파이썬 hash() 를 쓰면 실행마다 바뀝니다. 쓰지 마세요.
  unit         "공고" 고정
  company      기업 표시명
  companySlug  기업 slug
  title        공고 제목
  location     근무지. 모르면 빈 문자열
  career       "신입" / "경력" / "신입/경력" / "무관" / "분야별상이" 중 하나
  postedAt     게시일 YYYY-MM-DD. 모르면 빈 문자열
  closesAt     마감일 YYYY-MM-DD. 상시채용이면 빈 문자열
  dday         남은 일수(정수). 모르면 None
  multiRole    본문이 이미지뿐이라 세부 직무를 알 수 없으면 True
  sourceTitle  원문 표시용 제목. 안 쓰면 빈 문자열
  sourceUrl    원문 공고 주소. 반드시 채워야 합니다
  description  공고 본문 HTML. 50자 미만이면 상세 페이지를 만들지 않습니다

중요
----
description 이 비어 있으면 자체 상세 페이지도, JobPosting 스키마도 만들지
않습니다. 이건 실수가 아니라 정책입니다. 제목만 있는 페이지에 스키마를 달면
구글 구조화 데이터 정책 위반입니다. 본문을 못 읽으면 비워두고 원문으로
보내세요. 잘못된 정보를 만드는 것보다 낫습니다.
"""
import importlib

__all__ = ["load"]


def load(ats_name):
    """ATS 이름으로 어댑터 모듈을 가져옵니다. 없으면 ValueError."""
    try:
        mod = importlib.import_module(f"{__name__}.{ats_name}")
    except ModuleNotFoundError as e:
        raise ValueError(
            f"'{ats_name}' 어댑터가 없습니다. "
            f"scripts/adapters/{ats_name}.py 를 만들어야 합니다."
        ) from e
    if not hasattr(mod, "fetch"):
        raise ValueError(f"scripts/adapters/{ats_name}.py 에 fetch(company) 가 없습니다.")
    return mod
