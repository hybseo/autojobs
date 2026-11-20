/*
 * 빌드 표시 (2026-11-21)
 * 사이트를 새로 지을 때마다(공고 갱신·기능 수정 모두) 바뀌는 값입니다.
 * 모든 페이지와 /version.json 에 같은 값이 들어갑니다.
 * 휴대폰에서 예전에 열어 둔 화면으로 돌아오면, 페이지의 값과 /version.json 의 값을 비교해
 * 다르면(그 사이 공고가 갱신됐으면) 자동으로 새로고침합니다 — src/layouts/Base.astro 맨 아래.
 */
export const BUILD = String(Date.now());
