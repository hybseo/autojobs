import { companies, industries, roles, JOBS, daysLeft, COLLECTED_AT } from '../lib.js';

export async function GET({ site }) {
  const base = site.href.replace(/\/$/, '');
  /*
   * lastmod — 마지막으로 바뀐 날.
   *
   * 검색엔진이 "언제 다시 와야 하나" 를 정할 때 봅니다. 없으면 감으로
   * 정하는데, 네이버는 특히 이 값을 참고합니다.
   *
   * 목록 성격의 페이지(홈·산업·직무·기업)는 수집일을 씁니다. 하루 두 번
   * 갱신되므로 내용도 그때 바뀝니다.
   *
   * 공고 상세는 게시일을 씁니다. 공고 내용 자체는 올라온 뒤 바뀌지
   * 않으므로, 수집일을 적으면 "매일 바뀐다" 는 거짓 신호가 됩니다.
   * 그러면 검색엔진이 헛걸음을 반복하고, 나중에는 lastmod 를 믿지
   * 않게 됩니다.
   */
  const today = COLLECTED_AT || new Date().toISOString().slice(0, 10);

  const urls = [
    { loc: `${base}/`, pri: '1.0', freq: 'daily', mod: today },
    // 산업 페이지가 산업 키워드 검색을 받습니다. 메인 다음으로 중요합니다.
    ...industries().map((i) => ({ loc: `${base}/industry/${i.slug}/`, pri: '0.9', freq: 'daily', mod: today })),
    // 직무 페이지. "회로설계 채용", "임베디드 개발자 채용" 같은 검색을 받습니다.
    ...roles().map((r) => ({ loc: `${base}/role/${r.code}/`, pri: '0.9', freq: 'daily', mod: today })),
    ...companies().map((c) => ({ loc: `${base}/company/${c.slug}/`, pri: '0.8', freq: 'daily', mod: today })),
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
      .map((j) => ({
        loc: `${base}/job/${j.id}/`, pri: '0.6', freq: 'weekly',
        // 게시일이 없는 공고가 있습니다(상시채용 등). 그때는 수집일을 씁니다.
        mod: /^\d{4}-\d{2}-\d{2}$/.test(j.postedAt || '') ? j.postedAt : today,
      })),
  ];
  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map((u) => `  <url><loc>${u.loc}</loc><lastmod>${u.mod}</lastmod><changefreq>${u.freq}</changefreq><priority>${u.pri}</priority></url>`).join('\n')}
</urlset>`;
  return new Response(body, { headers: { 'Content-Type': 'application/xml; charset=utf-8' } });
}
