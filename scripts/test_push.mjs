/*
 * 웹푸시 암호화 시험 — RFC 8291 부록 A 의 시험값과 결과가 같은지 봅니다.
 *
 * 실행: node scripts/test_push.mjs
 * 같으면 "통과", 한 글자라도 다르면 "실패" 를 내고 종료 코드 1 로 끝납니다.
 * 알림 코드(worker/push.js)를 고쳤다면 반드시 다시 돌려 보세요.
 */
import { encryptPayload } from '../worker/push.js';
import { b64url, unb64url } from '../worker/util.js';

const as_private = 'yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw';
const as_public = 'BP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8';
const ua_public = 'BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4';
const auth_secret = 'BTBZMqHH6r4Tts7J_aSIgg';
const salt = 'DGv6ra1nlYgDCS1FRnbzlw';
const expected =
  'DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN';

const pub = unb64url(as_public);
const out = await encryptPayload(
  new TextEncoder().encode('When I grow up, I want to be a watermelon'),
  ua_public,
  auth_secret,
  {
    privateJwk: { kty: 'EC', crv: 'P-256', x: b64url(pub.slice(1, 33)), y: b64url(pub.slice(33, 65)), d: as_private },
    publicRaw: pub,
    salt: unb64url(salt),
  },
);
const got = b64url(out);
if (got === expected) {
  console.log('통과: RFC 8291 부록 A 와 일치');
} else {
  console.log('실패\n받은 값 ', got, '\n기대한 값', expected);
  process.exit(1);
}
