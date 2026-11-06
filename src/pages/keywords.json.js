/*
 * 마이페이지 「내 키워드」 고르기 목록 (2026-11-06)
 * 산업·직무·기술 태그를 진행중 공고 수와 함께 담습니다. 작은 파일이라 마이페이지가 열릴 때 받습니다.
 * 이름은 공고 알림 서버(scripts/notify_delta.mjs)가 보내는 이름과 같아야 알림이 맞게 갑니다.
 *   ind  산업 이름   role  직무 이름(roleName)   tag  기술·역량 태그 이름
 */
import { getData } from '../v2/data.js';

export async function GET() {
  const D = getData();
  const body = {
    ind: D.industries.map((x) => [x.n, x.c]).filter((x) => x[1] > 0).sort((a, b) => b[1] - a[1]),
    role: D.roles.map((x) => [x.n, x.c]).filter((x) => x[1] > 0).sort((a, b) => b[1] - a[1]),
    tag: Object.entries(D.tagIndex).map(([n, v]) => [n, v.c || '기타', v.n]).sort((a, b) => b[2] - a[2]),
  };
  return new Response(JSON.stringify(body), {
    headers: { 'content-type': 'application/json; charset=utf-8' },
  });
}
