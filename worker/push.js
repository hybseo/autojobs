/*
 * 웹푸시 보내기 (RFC 8291 암호화 + RFC 8292 VAPID 서명)
 * =====================================================================
 * 외부 라이브러리 없이 브라우저 표준 암호 기능(WebCrypto)만 씁니다.
 * 알림 내용은 받는 사람의 브라우저만 풀 수 있게 암호화되어 구글·애플·모질라의
 * 알림 서버를 거쳐 갑니다. 그 서버들도 내용을 읽지 못합니다.
 *
 * 필요한 환경변수
 *   VAPID_PUBLIC_KEY   발신자 공개키 (브라우저에도 알려 주는 값)
 *   VAPID_PRIVATE_KEY  발신자 비밀키 (비밀 — 절대 코드나 저장소에 넣지 않음)
 *   VAPID_SUBJECT      연락처 (mailto:… 형식, 알림 서버가 문제 시 연락)
 *
 * 검증: scripts/test_push.mjs 가 RFC 8291 부록 A 의 시험값으로 암호화 결과가
 * 문서와 한 글자도 다르지 않은지 확인합니다.
 */
import { b64url, unb64url } from './util.js';

const te = new TextEncoder();

const concat = (...arrs) => {
  const out = new Uint8Array(arrs.reduce((n, a) => n + a.length, 0));
  let o = 0;
  arrs.forEach((a) => { out.set(a, o); o += a.length; });
  return out;
};

async function hkdf(ikm, salt, info, bits) {
  const key = await crypto.subtle.importKey('raw', ikm, 'HKDF', false, ['deriveBits']);
  return new Uint8Array(await crypto.subtle.deriveBits({ name: 'HKDF', hash: 'SHA-256', salt, info }, key, bits));
}

/*
 * 내용을 암호화해 요청 본문(aes128gcm)을 만듭니다.
 * test 에 { privateJwk, publicRaw, salt } 를 넘기면 무작위 대신 그 값을 씁니다(시험 전용).
 */
export async function encryptPayload(payload, p256dhB64, authB64, test) {
  const uaPublic = unb64url(p256dhB64); // 65바이트
  const authSecret = unb64url(authB64); // 16바이트
  if (uaPublic.length !== 65 || authSecret.length !== 16) throw new Error('bad subscription keys');

  let asPrivate;
  let asPublic;
  if (test) {
    asPrivate = await crypto.subtle.importKey('jwk', test.privateJwk, { name: 'ECDH', namedCurve: 'P-256' }, false, ['deriveBits']);
    asPublic = test.publicRaw;
  } else {
    const kp = await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']);
    asPrivate = kp.privateKey;
    asPublic = new Uint8Array(await crypto.subtle.exportKey('raw', kp.publicKey));
  }
  const uaKey = await crypto.subtle.importKey('raw', uaPublic, { name: 'ECDH', namedCurve: 'P-256' }, false, []);
  const ecdh = new Uint8Array(await crypto.subtle.deriveBits({ name: 'ECDH', public: uaKey }, asPrivate, 256));

  const salt = test ? test.salt : crypto.getRandomValues(new Uint8Array(16));
  const keyInfo = concat(te.encode('WebPush: info\0'), uaPublic, asPublic);
  const ikm = await hkdf(ecdh, authSecret, keyInfo, 256);
  const cek = await hkdf(ikm, salt, te.encode('Content-Encoding: aes128gcm\0'), 128);
  const nonce = await hkdf(ikm, salt, te.encode('Content-Encoding: nonce\0'), 96);

  // 마지막(이자 유일한) 레코드이므로 뒤에 0x02 를 붙입니다.
  const plain = concat(payload, new Uint8Array([2]));
  const aes = await crypto.subtle.importKey('raw', cek, 'AES-GCM', false, ['encrypt']);
  const cipher = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce }, aes, plain));

  const header = new Uint8Array(21);
  header.set(salt, 0);
  new DataView(header.buffer).setUint32(16, 4096, false);
  header[20] = asPublic.length;
  return concat(header, asPublic, cipher);
}

/* VAPID 서명 토큰 (ES256 JWT). 만료는 12시간. */
export async function vapidAuthHeader(endpoint, env) {
  const aud = new URL(endpoint).origin;
  const pub = unb64url(env.VAPID_PUBLIC_KEY);
  const jwk = {
    kty: 'EC', crv: 'P-256',
    x: b64url(pub.slice(1, 33)), y: b64url(pub.slice(33, 65)), d: env.VAPID_PRIVATE_KEY,
  };
  const key = await crypto.subtle.importKey('jwk', jwk, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
  const head = b64url(te.encode(JSON.stringify({ typ: 'JWT', alg: 'ES256' })));
  const body = b64url(te.encode(JSON.stringify({
    aud, exp: Math.floor(Date.now() / 1000) + 12 * 3600, sub: env.VAPID_SUBJECT || 'mailto:searchjob.kr@gmail.com',
  })));
  const sig = new Uint8Array(await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, key, te.encode(`${head}.${body}`)));
  return `vapid t=${head}.${body}.${b64url(sig)}, k=${env.VAPID_PUBLIC_KEY}`;
}

/*
 * 알림 하나 보내기. 결과: 'ok' | 'gone'(받는 쪽이 사라짐 — 구독 삭제) | 'error'
 * message 는 { title, body, url } 객체입니다.
 */
export async function sendPush(sub, message, env) {
  try {
    const body = await encryptPayload(te.encode(JSON.stringify(message)), sub.p256dh, sub.auth);
    const res = await fetch(sub.endpoint, {
      method: 'POST',
      headers: {
        Authorization: await vapidAuthHeader(sub.endpoint, env),
        'Content-Encoding': 'aes128gcm',
        'Content-Type': 'application/octet-stream',
        TTL: '86400',
        Urgency: 'normal',
      },
      body,
    });
    if (res.status === 404 || res.status === 410) return 'gone';
    return res.ok ? 'ok' : 'error';
  } catch {
    return 'error';
  }
}

export const pushReady = (env) => !!(env.VAPID_PUBLIC_KEY && env.VAPID_PRIVATE_KEY);
