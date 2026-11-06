/*
 * 지금 열려 있는 공고 번호 목록 (2026-11-06)
 * 마이페이지가 「찜한 공고」 가운데 마감됐거나 내려간 것을 알아보는 데 씁니다.
 * 사이트를 새로 만들 때마다 같이 만들어지므로 공고 데이터(하루 두 번 갱신)와 같은 시점입니다.
 */
import { openJobs } from '../lib.js';

export async function GET() {
  const body = { ids: openJobs().map((j) => j.id) };
  return new Response(JSON.stringify(body), {
    headers: { 'content-type': 'application/json; charset=utf-8' },
  });
}
