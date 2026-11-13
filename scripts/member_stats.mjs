/*
 * 회원 수 통계를 가져와 읽기 쉽게 출력합니다. (.github/workflows/member-stats.yml 이 실행)
 * 서버의 /api/internal/stats 를 비밀키로 부르며, 이름·별명 없이 숫자만 옵니다.
 *   NOTIFY_URL     예) https://searchjob.co.kr
 *   NOTIFY_SECRET  클라우드플레어의 NOTIFY_SECRET 과 같은 값
 */
const URL_BASE = (process.env.NOTIFY_URL || '').replace(/\/$/, '');
const SECRET = process.env.NOTIFY_SECRET || '';
if (!URL_BASE || !SECRET) { console.log('NOTIFY_URL / NOTIFY_SECRET 이 없습니다.'); process.exit(1); }

const r = await fetch(`${URL_BASE}/api/internal/stats`, {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${SECRET}`, 'Content-Type': 'application/json',
    'User-Agent': 'searchjob-notify/1.0 (+https://searchjob.co.kr)', Accept: 'application/json',
  },
  body: '{}',
});
const text = await r.text();
if (!r.ok) {
  console.log(`실패 ${r.status} (cf-ray ${r.headers.get('cf-ray') || '-'}) ${text.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').slice(0, 300)}`);
  process.exit(1);
}
const s = JSON.parse(text);
const P = { kakao: '카카오', naver: '네이버', google: '구글' };
console.log('── 서치잡 회원 통계 ──');
console.log(`가입한 회원(약관 동의 완료): ${s.members}명`);
console.log('  로그인한 곳별: ' + (Object.entries(s.byProvider).map(([k, v]) => `${P[k] || k} ${v}명`).join(' · ') || '없음'));
console.log(`오늘 가입: ${s.signedUpToday}명 · 최근 7일 가입: ${s.signedUpLast7Days}명 · 최근 7일 접속: ${s.loggedInLast7Days}명`);
console.log(`동의 전 임시 기록: ${s.pendingConsent}건 (하루 지나면 자동 삭제)`);
console.log(`알림 켠 회원: ${s.pushUsers}명 (기기 ${s.pushDevices}대)`);
console.log(`기능을 쓰는 회원 — 팔로우 ${s.usersUsing.follow}명 · 찜 ${s.usersUsing.bookmark}명 · 검색 알림 ${s.usersUsing.savedSearch}명 · 내 키워드 ${s.usersUsing.keyword}명`);
const cr = s.companyRequests;
if (cr) {
  console.log(`기업 등록 요청: 최근 24시간 ${cr.last24h}건 · 누적 ${cr.total}건`);
  for (const r of cr.recent || []) {
    const d = new Date((r.at + 9 * 3600) * 1000).toISOString().slice(5, 16).replace('T', ' ');
    console.log(`  · ${d} ${r.company} — ${r.url}`);
  }
}
console.log(`저장된 항목 — 팔로우 ${s.rows.follows} · 찜 ${s.rows.bookmarks} · 검색 ${s.rows.savedSearches} · 키워드 ${s.rows.keywords} · 새 소식 ${s.rows.alerts}`);
