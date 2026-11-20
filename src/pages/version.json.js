/*
 * 지금 사이트의 빌드 표시 (2026-11-21) — src/v2/build.js 참고.
 * 아주 작은 파일입니다. 화면으로 돌아올 때 이것만 받아 보고 갱신 여부를 판단합니다.
 */
import { BUILD } from '../v2/build.js';

export async function GET() {
  return new Response(JSON.stringify({ b: BUILD }), {
    headers: { 'content-type': 'application/json; charset=utf-8' },
  });
}
