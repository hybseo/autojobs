/*
 * /jobs/ 화면이 브라우저에서 읽는 데이터 (2026-11-03)
 *
 * 공고 목록은 거르기·검색·탭·정렬을 할 때마다 브라우저가 다시 그립니다.
 * 그 재료입니다. 카드에 필요한 것만 담습니다 — 요약은 한 줄(s.g)만.
 * 전체 요약은 공고 상세 쪽(/job/{id}/)이 들고 있습니다.
 */
import { getData, toRow } from '../../v2/data.js';
import { openJobs } from '../../lib.js';

export async function GET() {
  const D = getData();
  const body = {
    meta: D.meta,
    industries: D.industries,
    roles: D.roles,
    /* g: 그룹 통합 채용 표시. 카드가 그룹 이름 대신 계열사 이름을 쓰게 합니다
       (2026-11-13, views.js coLabel). 그룹일 때만 넣어 용량을 아낍니다. */
    companies: D.companies.map((c) => (c.g ? { s: c.s, n: c.n, i: c.i, g: 1 } : { s: c.s, n: c.n, i: c.i })),
    tagIndex: D.tagIndex,
    jobs: openJobs().map((j) => toRow(j, false)),
    scans: [],
    hist: [],
  };
  return new Response(JSON.stringify(body), {
    headers: { 'content-type': 'application/json; charset=utf-8' },
  });
}
