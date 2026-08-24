import { defineConfig } from 'astro/config';

export default defineConfig({
  // 배포 도메인으로 바꾸세요. sitemap 과 canonical 에 쓰입니다.
  site: 'https://searchjob.co.kr',
  output: 'static',
  build: { format: 'directory' },
});
