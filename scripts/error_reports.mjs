/*
 * 오류 신고 가져오기 (.github/workflows/error-reports.yml 이 실행) — 2026-11-20
 * ---------------------------------------------------------------------
 * 서버의 /api/internal/error-reports 를 비밀키로 불러 최근 신고를 받습니다.
 *
 * 저장소가 공개라 Actions 기록(로그)은 누구나 볼 수 있습니다. 그래서 신고 내용은
 * 로그에 그대로 찍지 않고 아래 공개 열쇠(REPORT_PUBLIC_KEY)로 잠근 덩어리만 찍습니다(건수만 평문).
 * 공개 열쇠는 잠그기만 할 수 있고 열 수는 없습니다. 여는 열쇠(개인 열쇠)는 깃허브 어디에도 없고,
 * 매일 점검하는 Claude 예약 작업만 갖고 있습니다(scripts/error_reports_open.mjs 로 엶).
 * 방식: X25519 로 그때그때 만든 임시 열쇠와 공개 열쇠로 공유 비밀을 만들고, 그 해시로 AES-256-GCM 암호화.
 * 열쇠를 바꾸려면 새 열쇠 쌍을 만들어 아래 값과 예약 작업 프롬프트의 개인 열쇠를 함께 바꾸세요.
 *
 *   NOTIFY_URL     예) https://searchjob.co.kr
 *   NOTIFY_SECRET  클라우드플레어의 NOTIFY_SECRET 과 같은 값
 *   HOURS          몇 시간 치를 볼지 (기본 26)
 */
import { createPublicKey, generateKeyPairSync, diffieHellman, createHash, createCipheriv, randomBytes } from 'node:crypto';

const REPORT_PUBLIC_KEY = 'clg3Z0FUru_4-Mr2OietK43g38pADC1kw-MhaxQZvyo'; // X25519 공개 열쇠 (2026-11-20)

const URL_BASE = (process.env.NOTIFY_URL || '').replace(/\/$/, '');
const SECRET = process.env.NOTIFY_SECRET || '';
const HOURS = Number(process.env.HOURS) || 26;
if (!URL_BASE || !SECRET) { console.log('NOTIFY_URL / NOTIFY_SECRET 이 없습니다.'); process.exit(1); }

const r = await fetch(`${URL_BASE}/api/internal/error-reports`, {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${SECRET}`, 'Content-Type': 'application/json',
    'User-Agent': 'searchjob-notify/1.0 (+https://searchjob.co.kr)', Accept: 'application/json',
  },
  body: JSON.stringify({ hours: HOURS }),
});
const text = await r.text();
if (!r.ok) {
  console.log(`실패 ${r.status} (cf-ray ${r.headers.get('cf-ray') || '-'}) ${text.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').slice(0, 300)}`);
  process.exit(1);
}
const d = JSON.parse(text);
const manual = d.reports.filter((x) => x.kind === 'manual').length;
console.log('── 서치잡 오류 신고 ──');
console.log(`최근 ${d.hours}시간: 버튼 신고 ${manual}건 · 자동 기록 ${d.reports.length - manual}건 (보관 중 전체 ${d.total}건)`);
if (!d.reports.length) process.exit(0);

const pub = createPublicKey({ key: { kty: 'OKP', crv: 'X25519', x: REPORT_PUBLIC_KEY }, format: 'jwk' });
const eph = generateKeyPairSync('x25519');
const key = createHash('sha256').update(diffieHellman({ privateKey: eph.privateKey, publicKey: pub })).digest();
const iv = randomBytes(12);
const c = createCipheriv('aes-256-gcm', key, iv);
const ct = Buffer.concat([c.update(JSON.stringify(d), 'utf8'), c.final()]);
const blob = Buffer.concat([iv, c.getAuthTag(), ct]).toString('base64');
console.log(`SJKEY ${eph.publicKey.export({ format: 'jwk' }).x}`);
const parts = blob.match(/.{1,3000}/g) || [];
parts.forEach((p, i) => console.log(`SJENC ${String(i + 1).padStart(3, '0')}/${String(parts.length).padStart(3, '0')} ${p}`));
