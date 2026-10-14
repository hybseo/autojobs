import { defineConfig } from 'astro/config';
import pageSizeGuard from './page-size-guard.mjs';

export default defineConfig({
  // 배포 도메인으로 바꾸세요. sitemap 과 canonical 에 쓰입니다.
  site: 'https://searchjob.co.kr',
  output: 'static',
  build: { format: 'directory' },
  /*
   * 빌드가 끝나면 만들어진 페이지 크기를 재서, 네이버가 수집하지 못하는
   * 크기(4MB)에 가까워지면 알려줍니다. 자세한 내용과 줄이는 방법은
   * page-size-guard.mjs 맨 위 주석에 적어두었습니다. (2026-10-14)
   */
  integrations: [pageSizeGuard()],
});
