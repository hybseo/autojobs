import { companies, industries, JOBS } from '../lib.js';

export async function GET({ site }) {
  const base = site.href.replace(/\/$/, '');
  const urls = [
    { loc: `${base}/`, pri: '1.0', freq: 'daily' },
    // 산업 페이지가 산업 키워드 검색을 받습니다. 메인 다음으로 중요합니다.
    ...industries().map((i) => ({ loc: `${base}/industry/${i.slug}/`, pri: '0.9', freq: 'daily' })),
    ...companies().map((c) => ({ loc: `${base}/company/${c.slug}/`, pri: '0.8', freq: 'daily' })),
    ...JOBS.filter((j) => j.description && j.description.trim().length >= 50)
      .map((j) => ({ loc: `${base}/job/${j.id}/`, pri: '0.6', freq: 'weekly' })),
  ];
  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map((u) => `  <url><loc>${u.loc}</loc><changefreq>${u.freq}</changefreq><priority>${u.pri}</priority></url>`).join('\n')}
</urlset>`;
  return new Response(body, { headers: { 'Content-Type': 'application/xml; charset=utf-8' } });
}
