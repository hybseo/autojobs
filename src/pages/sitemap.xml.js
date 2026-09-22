import { companies, industries, roles, JOBS, COLLECTED_AT } from '../lib.js';

// 마감 후 사이트맵에 남겨 두는 날 수. 아래 공고 상세 주석 참고.
const GRACE_DAYS = 7;

const isDate = (v) => /^\d{4}-\d{2}-\d{2}$/.test(v || '');

/**
 * 공고가 마감된 날. 진행중이면 빈 문자열.
 *   - 회사가 공고를 내려 보관 중이면 사라진 날(goneAt)
 *   - 아니면 마감일이 오늘보다 앞일 때 그 마감일
 * 오늘 마감인 공고는 아직 진행중으로 봅니다.
 */
const closedOn = (j, today) => {
  if (isDate(j.goneAt)) return j.goneAt;
  if (isDate(j.closesAt) && j.closesAt < today) return j.closesAt;
  return '';
};

/** 두 날짜(YYYY-MM-DD) 사이의 날 수. */
const daysBetween = (a, b) => Math.round((Date.parse(b) - Date.parse(a)) / 86400000);

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
     * 마감된 공고도 페이지는 남깁니다(보관 60일, 404 를 막으려고). 사이트맵은
     * "이 주소를 크롤링해 달라" 는 요청이라, 여기에는 이렇게 넣습니다.
     *
     *   진행중                넣음. lastmod 는 게시일
     *   마감 후 7일 이내       넣음. lastmod 를 마감한 날로 → "바뀌었다" 신호
     *   마감 후 7일 지남       뺌. 페이지는 그대로 있음
     *
     * 7일을 두는 이유: 구글이 진행중으로 색인해 둔 공고가 마감되면, 다시 와서
     * 마감 안내로 바뀐 것을 봐야 검색 결과에서 내립니다. 바로 빼면 그 확인이
     * 늦어져 마감 공고가 진행중처럼 검색에 남습니다.
     *
     * 7일이 지난 마감 공고를 빼는 이유: 신생 사이트는 구글이 하루에 가져가는
     * 페이지 수가 적습니다. 2026-09-22 서치콘솔에서 1,928건이 "발견됨 - 색인
     * 안 됨" 이었고, 사이트맵의 공고 중 408건(18%)이 마감 공고였습니다.
     * 그 몫을 진행중 공고에 쓰게 합니다.
     *
     * 전에는 daysLeft(j) > 0 으로 걸렀는데 두 군데가 샜습니다.
     *   - 회사가 내려서 보관 중인 공고(goneAt)는 마감일이 비었거나 미래라
     *     그대로 들어갔습니다.
     *   - 오늘 마감인 공고는 남은 날이 0 이라 빠졌습니다.
     */
    ...JOBS.filter((j) => j.description && j.description.trim().length >= 50)
      .filter((j) => {
        const shut = closedOn(j, today);
        return !shut || daysBetween(shut, today) <= GRACE_DAYS;
      })
      .map((j) => {
        const shut = closedOn(j, today);
        return {
          loc: `${base}/job/${j.id}/`, pri: '0.6', freq: 'weekly',
          // 마감됐으면 마감한 날, 아니면 게시일. 게시일이 없으면 수집일.
          mod: shut || (/^\d{4}-\d{2}-\d{2}$/.test(j.postedAt || '') ? j.postedAt : today),
        };
      }),
  ];
  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map((u) => `  <url><loc>${u.loc}</loc><lastmod>${u.mod}</lastmod><changefreq>${u.freq}</changefreq><priority>${u.pri}</priority></url>`).join('\n')}
</urlset>`;
  return new Response(body, { headers: { 'Content-Type': 'application/xml; charset=utf-8' } });
}
