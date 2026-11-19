/*
 * 잠긴 오류 신고 열기 — 매일 점검하는 Claude 예약 작업이 씁니다. (2026-11-20)
 *   gh run view <id> -R hybseo/autojobs --log | REPORT_PRIVATE_KEY=… node scripts/error_reports_open.mjs > reports.json
 * REPORT_PRIVATE_KEY 는 「공개열쇠.개인열쇠」 형식이며 예약 작업 프롬프트에만 있습니다. 저장소에 넣지 마세요.
 * 로그에서 「SJKEY …」 줄과 「SJENC 001/00N …」 줄을 모아 풉니다. 결과(JSON)는 공개된 곳에 올리지 마세요.
 */
import { createPrivateKey, createPublicKey, diffieHellman, createHash, createDecipheriv } from 'node:crypto';

const [x, dKey] = String(process.env.REPORT_PRIVATE_KEY || '').trim().split('.');
if (!x || !dKey) { console.error('REPORT_PRIVATE_KEY 가 없습니다.'); process.exit(1); }
let input = '';
for await (const chunk of process.stdin) input += chunk;
let eph = '';
const parts = {};
for (const line of input.split('\n')) {
  const k = line.match(/SJKEY (\S+)/);
  if (k) eph = k[1];
  const m = line.match(/SJENC (\d{3})\/(\d{3}) (\S+)/);
  if (m) parts[m[1]] = m[3];
}
const keys = Object.keys(parts).sort();
if (!eph || !keys.length) { console.error('로그에 잠긴 신고가 없습니다(신고 0건).'); process.exit(2); }
const priv = createPrivateKey({ key: { kty: 'OKP', crv: 'X25519', x, d: dKey }, format: 'jwk' });
const pub = createPublicKey({ key: { kty: 'OKP', crv: 'X25519', x: eph }, format: 'jwk' });
const key = createHash('sha256').update(diffieHellman({ privateKey: priv, publicKey: pub })).digest();
const buf = Buffer.from(keys.map((k2) => parts[k2]).join(''), 'base64');
const dc = createDecipheriv('aes-256-gcm', key, buf.subarray(0, 12));
dc.setAuthTag(buf.subarray(12, 28));
const out = Buffer.concat([dc.update(buf.subarray(28)), dc.final()]).toString('utf8');
console.log(JSON.stringify(JSON.parse(out), null, 2));
