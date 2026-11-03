import { JOBS, COLLECTED_AT, hasDetail, summaryOf, openJobs, parseDate } from '../lib.js';

/*
 * RSS 피드 (2026-11-03)
 * =====================
 * 네이버 서치어드바이저에 등록해 두면, 네이버가 사이트맵보다 이 주소를
 * 더 자주 들여다보고 "새 글이 생겼다" 는 신호로 씁니다. 사이트맵은
 * "이 주소들이 존재한다" 는 전체 목록이고, RSS 는 "방금 이게 새로
 * 올라왔다" 는 알림이라 역할이 다릅니다.
 *
 * 그래서 전체 공고가 아니라 최근 올라온 것 중 상위 N개만 담습니다.
 * 너무 많이 담으면 매번 통째로 다시 읽어야 해서 "자주 와서 가볍게
 * 확인한다" 는 RSS 의 장점이 사라집니다.
 *
 * 담는 기준
 *   - 접수중인 공고만 (openJobs — 마감됐거나 회사가 내린 공고는 뺍니다)
 *   - 요약이 있는 공고만 (hasDetail — 상세 페이지가 실제로 있는 것만)
 *   - 게시일(postedAt) 내림차순으로 최신 50건
 */
const FEED_SIZE = 50;

const escapeXml = (s) =>
  String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/*
 * YYYY-MM-DD → RFC 822 (한국시간 자정 기준). RSS pubDate 는 이 형식이어야 합니다.
 *
 * d.toUTCString() 을 그냥 쓰면 "+0900" 이라고 적어 놓고 실제 시각은 UTC
 * 그대로 찍혀 9시간이 어긋납니다 (parseDate 는 한국시간 자정을 UTC
 * 인스턴트로 담고 있으므로). 그래서 9시간을 더한 뒤 UTC 필드를 읽어
 * 한국시간 그대로의 요일·날짜·시각을 뽑습니다.
 */
const toRfc822 = (dateStr) => {
  const valid = /^\d{4}-\d{2}-\d{2}$/.test(dateStr || '');
  const d = valid ? parseDate(dateStr) : new Date();
  const kst = new Date(d.getTime() + 9 * 3600000);
  const pad = (n) => String(n).padStart(2, '0');
  return `${WEEKDAYS[kst.getUTCDay()]}, ${pad(kst.getUTCDate())} ${MONTHS[kst.getUTCMonth()]} ` +
    `${kst.getUTCFullYear()} ${pad(kst.getUTCHours())}:${pad(kst.getUTCMinutes())}:${pad(kst.getUTCSeconds())} +0900`;
};

export async function GET({ site }) {
  const base = site.href.replace(/\/$/, '');

  const items = openJobs()
    .filter(hasDetail)
    .sort((a, b) => (b.postedAt || '').localeCompare(a.postedAt || ''))
    .slice(0, FEED_SIZE);

  const rssItems = items.map((j) => {
    const url = `${base}/job/${j.id}/`;
    const gist = summaryOf(j)?.gist || '';
    const title = `[${j.company}] ${j.title}`;
    return `  <item>
    <title>${escapeXml(title)}</title>
    <link>${url}</link>
    <guid isPermaLink="true">${url}</guid>
    <pubDate>${toRfc822(j.postedAt)}</pubDate>
    <description>${escapeXml(gist)}</description>
  </item>`;
  }).join('\n');

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>서치잡 — 자동차부품·전자 채용공고</title>
  <link>${base}/</link>
  <description>자동차부품·전자 업계 채용공고를 한 곳에서. 매일 갱신됩니다.</description>
  <language>ko</language>
  <lastBuildDate>${toRfc822(COLLECTED_AT)}</lastBuildDate>
${rssItems}
</channel>
</rss>`;
  return new Response(body, { headers: { 'Content-Type': 'application/rss+xml; charset=utf-8' } });
}
