import { companies, industries, JOBS, daysLeft } from '../lib.js';

export async function GET({ site }) {
  const base = site.href.replace(/\/$/, '');
  const urls = [
    { loc: `${base}/`, pri: '1.0', freq: 'daily' },
    // 산업 페이지가 산업 키워드 검색을 받습니다. 메인 다음으로 중요합니다.
    ...industries().map((i) => ({ loc: `${base}/industry/${i.slug}/`, pri: '0.9', freq: 'daily' })),
    ...companies().map((c) => ({ loc: `${base}/company/${c.slug}/`, pri: '0.8', freq: 'daily' })),
    /*
     * 공고 상세.
     *
     * 마감된 공고도 페이지는 남기지만(404 를 없애려고), 사이트맵에는
     * 진행중인 것만 넣습니다. 사이트맵은 "이 주소를 크롤링해 달라" 는
     * 요청이고, 지원할 수 없는 자리를 우선 크롤링하게 할 이유가 없습니다.
     *
     * 마감 공고 페이지는 이미 색인된 주소로 구글이 다시 찾아올 때
     * 404 대신 마감 안내를 보여주는 역할을 합니다.
     */
    ...JOBS.filter((j) => j.description && j.description.trim().length >= 50
        && daysLeft(j) > 0)
      .map((j) => ({ loc: `${base}/job/${j.id}/`, pri: '0.6', freq: 'weekly' })),
  ];
  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map((u) => `  <url><loc>${u.loc}</loc><changefreq>${u.freq}</changefreq><priority>${u.pri}</priority></url>`).join('\n')}
</urlset>`;
  return new Response(body, { headers: { 'Content-Type': 'application/xml; charset=utf-8' } });
}
