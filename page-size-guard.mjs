/*
 * 페이지 크기 감시 장치
 * ============================================================
 * 빌드가 끝날 때마다 만들어진 HTML 페이지 크기를 재서, 네이버 검색로봇이
 * 포기하는 크기에 가까워지면 알려줍니다.
 *
 * 왜 필요한가 (2026-10-14)
 * ------------------------
 * 네이버 웹마스터도구 도움말의 수집 오류 유형에 이렇게 적혀 있습니다.
 *
 *     다운로드 사이즈가 큰 페이지
 *     HTML 문서의 사이즈가 큰 경우(4MB 이상 등)에 발생할 수 있습니다.
 *
 * 홈이 어느새 5,039KB(4.9MB)가 되어 이 선을 넘었고, 네이버가 홈을 수집하지
 * 못했습니다. 문제는 넘었다는 사실을 아무도 몰랐다는 것입니다. 공고가 쌓이면
 * 홈은 저절로 커집니다. 카드 한 장이 약 650바이트이니 공고 1,000건이 늘면
 * 650KB가 늘어납니다. 아무도 재지 않으면 다시 조용히 넘어갑니다.
 *
 * 그래서 빌드할 때마다 자동으로 재게 했습니다. 공고갱신은 하루 두 번 도니까
 * 하루 두 번 확인되는 셈입니다.
 *
 * 어떻게 동작하나
 * ---------------
 *   3.5MB 넘으면   경고만 하고 빌드는 계속합니다. "슬슬 줄일 때" 라는 신호.
 *   3.9MB 넘으면   빌드를 멈춥니다.
 *
 * 왜 4MB 가 아니라 3.9MB 에서 멈추나
 *   4MB 는 "이미 넘은" 상태입니다. 그 전에 멈춰야 합니다. 빌드가 멈추면
 *   배포가 안 되고, 사이트는 직전에 성공한 버전(=4MB 아래)을 계속
 *   보여줍니다. 즉 멈추는 쪽이 안전한 상태로 남습니다.
 *
 * 빌드가 멈추면 어떻게 하나
 *   공고갱신이 실패한 것처럼 보일 겁니다. 당황하지 마세요. 사이트는 그대로
 *   돌아가고 있고, 공고 데이터만 직전 상태입니다. 아래 "줄이는 방법" 을
 *   보고 홈을 줄인 뒤 다시 올리면 됩니다.
 *
 * 줄이는 방법 (2026-10-14 에 실제로 5,039KB → 3,330KB 로 줄인 방법)
 *   - JobCard.astro 에 <style> 을 두지 않기. 아스트로가 모든 요소에 표식을
 *     붙여서 그것만으로 1,287KB 였습니다. 자세한 내용은 그 파일 맨 아래 주석.
 *   - 카드에 보이는 글자를 data 속성에 또 담지 않기. 검색용으로 중복해서
 *     담았다가 483KB 였습니다. 지금은 화면에 없는 것만 담습니다.
 *   - 그래도 모자라면 홈에 싣는 카드 수를 줄이는 수밖에 없습니다. 그때는
 *     "마감 임박한 것부터 N건" 식으로 자르고 나머지는 산업·기업 페이지가
 *     받게 하세요. 산업 페이지는 각각 훨씬 작습니다.
 *
 * 홈만 보지 않고 전부 보는 이유
 *   지금은 홈이 가장 크지만, 공고가 특정 산업에 몰리면 그 산업 페이지가
 *   먼저 넘을 수도 있습니다. 어느 페이지든 넘으면 그 페이지가 수집에서
 *   빠집니다. 그래서 전부 재고, 큰 것부터 다섯 개를 매번 로그에 남깁니다.
 *   넘지 않아도 로그를 보면 얼마나 여유가 있는지 알 수 있습니다.
 */
import { readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const MB = 1024 * 1024;
const NAVER_LIMIT = 4 * MB;   // 도움말에 적힌 선. 이 값 자체는 쓰지 않고 기준으로만 둡니다.
const STOP = 3.9 * MB;        // 여기서 빌드를 멈춥니다.
const WARN = 3.5 * MB;        // 여기서 경고합니다.

const kb = (n) => `${Math.round(n / 1024).toLocaleString('en-US')}KB`;

/** dist 안의 .html 을 모두 찾아 경로와 크기를 돌려줍니다. */
function htmlFiles(dir) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...htmlFiles(full));
    else if (entry.name.endsWith('.html')) out.push({ full, bytes: statSync(full).size });
  }
  return out;
}

export default function pageSizeGuard() {
  return {
    name: 'page-size-guard',
    hooks: {
      'astro:build:done': ({ dir, logger }) => {
        const root = fileURLToPath(dir);
        const pages = htmlFiles(root)
          .map((p) => ({
            // dist/industry/it/index.html → /industry/it/
            url: '/' + p.full.slice(root.length).replace(/index\.html$/, '').replace(/^[/\\]/, '').replace(/\\/g, '/'),
            bytes: p.bytes,
          }))
          .sort((a, b) => b.bytes - a.bytes);

        if (pages.length === 0) return;

        const biggest = pages[0];
        logger.info(
          `가장 큰 페이지 다섯 개 (네이버 수집 한계 ${kb(NAVER_LIMIT)})\n` +
          pages.slice(0, 5)
            .map((p, i) => `  ${i + 1}. ${kb(p.bytes).padStart(8)}  ${p.url}`)
            .join('\n') +
          `\n  → 가장 큰 페이지에 남은 여유 ${kb(NAVER_LIMIT - biggest.bytes)}`);

        const over = pages.filter((p) => p.bytes > STOP);
        if (over.length > 0) {
          throw new Error(
            `\n\n페이지가 너무 커서 빌드를 멈췄습니다.\n\n` +
            over.map((p) => `    ${kb(p.bytes)}  ${p.url}`).join('\n') +
            `\n\n네이버는 HTML 문서가 ${kb(NAVER_LIMIT)}를 넘으면 수집하지 못합니다.\n` +
            `실제로 2026년 10월에 홈이 4.9MB가 되어 네이버 수집에서 빠졌고,\n` +
            `몇 달 동안 아무도 몰랐습니다. 같은 일을 막으려고 넘기 직전인\n` +
            `${kb(STOP)}에서 멈추게 해두었습니다.\n\n` +
            `사이트는 멀쩡합니다. 직전에 성공한 버전이 계속 서비스되고 있고\n` +
            `공고 데이터만 이번 갱신분이 반영되지 않은 상태입니다.\n\n` +
            `줄이는 방법은 page-size-guard.mjs 맨 위 주석에 적어두었습니다.\n`);
        }

        const warn = pages.filter((p) => p.bytes > WARN);
        if (warn.length > 0) {
          logger.warn(
            `${kb(WARN)}를 넘은 페이지가 ${warn.length}개 있습니다. ` +
            `${kb(STOP)}를 넘으면 빌드가 멈춥니다.\n` +
            warn.map((p) => `    ${kb(p.bytes)}  ${p.url}`).join('\n') +
            `\n  줄이는 방법은 page-size-guard.mjs 맨 위 주석을 보세요.`);
        }
      },
    },
  };
}
