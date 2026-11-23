/*
 * 레벨 진단 화면 (2026-11-20) — searchjob.co.kr/level/
 * =====================================================================
 * 계산·화면은 대표님이 확정한 시안(시작 화면 포함, 100건 실제 입력 테스트 통과본)을 그대로 옮겼습니다.
 * 바꾼 것은 서치잡 회원 연결뿐입니다(맨 아래 「회원 연결」).
 *   - 시작 화면은 누구나 보고, 「진단 시작하기」는 SNS 간편로그인 회원만
 *   - 처음 한 번 「레벨 진단 입력 내용 저장·이용」 동의
 *   - 진단할 때마다 입력·결과 저장(서버 worker/level.js), 다시 오면 지난 입력을 채우고 지난 레벨과 비교
 *   - 결과지에 표시할 이름(선택) — 화면과 메일에만 쓰고 서버에 저장하지 않음(이 브라우저에만 기억)
 *   - 결과를 이메일로 받기(선택) — 주소를 적으면 「이 주소로 보낼까요?」로 한 번 더 확인한 뒤 바로 보냄(주소는 기억).
 *     서버 설정 전에는 「준비 중」
 *   - /level/?run=번호 — 지난 진단 한 회차의 결과 화면을 다시 엶(결과 메일·마이페이지 기록에서 연결)
 * 기준 데이터: /level/duty_data.json(직무별 기술·자격증), /level/univ.json(대학 구분)
 */
const NOW={y:2026,m:11};
const TYPES=[
  ['big10','대기업 상위 (10대 그룹 계열)',10,5],['big','대기업 (상호출자제한 집단)',9,5],['bigsub','대기업 하위 (공시대상 집단)',8,5],
  ['listed','상장사',6,3],['unicorn','유니콘',6,3],['public','공공기관·공기업·연구기관',6,3],['foreign','외국계 (한국 법인·지사)',6,3],
  ['private','비상장 기업',3,1],['gbig','해외 글로벌 대기업',9,5],['glisted','해외 상장사',6,3],['gprivate','해외 비상장·스타트업',3,1],
  ['self','창업·자영업·프리랜서',null,1],['np','비영리·대학·협회',null,1]];
const TYPE=Object.fromEntries(TYPES.map(t=>[t[0],{label:t[1],score:t[2],floor:t[3]}]));
const SW_GROUP='AI·개발·데이터';
const SW_PREF=['네이버','naver','카카오','kakao','라인','line','쿠팡','coupang','배민','배달의민족','우아한형제들','당근','토스','비바리퍼블리카'];
const W={L:{school:35,co:30,ten:15,tech:20},M:{school:20,co:20,ten:25,tech:35},S:{school:15,co:15,ten:30,tech:40}};
const LV={6:['대기업 핵심권','대기업이 찾는 인재 기준을 대부분 갖춘 수준입니다. 대기업이 먼저 보는 요소를 대부분 갖췄습니다.'],
  5:['대기업 도전권','대기업 지원이 가능한 수준입니다. 일부 요소를 보강하면 경쟁력이 더 올라갑니다.'],
  4:['중견 핵심권','중견기업이 선호하는 요소를 고르게 갖췄습니다.'],
  3:['중견 도전권','중견기업 지원이 가능하고, 중소기업에서는 경쟁력이 높은 수준입니다.'],
  2:['중소 핵심권','중소기업에서 경쟁력이 있는 수준입니다.'],
  1:['성장 단계','경력과 요소가 쌓이는 단계입니다. 아래 항목을 보강하면 레벨이 오릅니다.']};
const BONUS={deg:{기본:{석사:2,박사:3},큰:{석사:4,박사:6}},eng:{기본:{원어민:2,비즈니스:1.5,일상:1},큰:{원어민:4,비즈니스:3,일상:2}},lic:{기본:2,큰:4}};
const SPECIAL_SCHOOLS=['학점은행제 (평생교육진흥원)','독학학위제','해외 대학'];
const $=s=>document.querySelector(s);
let D=null, UNIV=null, UNIVMAP=null;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const poolOf=duty=>D.duty[duty]||null;
const groupOf=duty=>D.duty[duty]?.g;

/* ---------- 입력: 직무 ---------- */
function fillGroups(){
  $('#grp').innerHTML=Object.keys(D.groups).map(k=>`<option>${esc(k)}</option>`).join('');
  $('#grp').addEventListener('change',()=>{fillDuties();onDuty()});
  $('#duty').addEventListener('change',onDuty);
}
function fillDuties(){$('#duty').innerHTML=D.groups[$('#grp').value].map(d=>`<option>${esc(d)}</option>`).join('')}
const grpOptions=sel=>Object.keys(D.groups).map(g=>`<option ${g===sel?'selected':''}>${esc(g)}</option>`).join('');
const dutyOpts=(g,sel)=>D.groups[g].map(d=>`<option ${d===sel?'selected':''}>${esc(d)}</option>`).join('');
let subState=[];
function onDuty(){
  const duty=$('#duty').value, P=poolOf(duty);
  const note= P.src==='사전 없음'?'이 직무의 기술 목록은 준비 중입니다. 아래 검색 칸으로 기술을 넣을 수 있고, 기술 일치도는 레벨에 반영하지 않습니다.'
    : P.src==='공고 없음'?'서치잡에 이 직무 공고가 아직 없어서 기술 일치도는 레벨에 반영하지 않습니다. 기술을 입력해 두면 저장되고, 공고가 모이면 반영합니다.'
    : !P.tech?'이 직무는 기술 일치도를 레벨에 반영하지 않습니다. 기술을 입력해 두면 저장되고 나중에 기업 검색에 쓰입니다.'
    : P.src==='직무'?`서치잡 공고 ${P.n}건으로 이 직무에서 어떤 기술이 많이 요구되는지 계산했습니다.`
    : `이 직무만의 공고가 아직 적어서, ${P.g} 분야 공고 ${P.n}건으로 기술별 비중을 계산했습니다.`;
  $('#dutyNote').textContent=`분야: ${P.g} · `+note;
  const names=Object.keys(P.subs||{});
  subState=names.length?[names[0]]:[];
  renderSubs();
  skillState={}; renderSkills(); licState={}; renderLics();
  document.querySelectorAll('.career[data-id]').forEach(el=>{const id=el.dataset.id,js=el.querySelector('#cj'+id);if(js.dataset.touched)return;const g=groupOf(duty);el.querySelector('#cg'+id).value=g;js.innerHTML=dutyOpts(g,duty)});
}
function renderSubs(){
  const P=poolOf($('#duty').value); const names=Object.keys(P.subs||{}); const box=$('#subs'); box.innerHTML='';
  $('#subWrap').hidden=names.length<=1;
  names.forEach(n=>{const l=document.createElement('label');l.className='chk tag';l.style.color='var(--ink)';
    const id='sub_'+encodeURIComponent(n).replace(/[%.()]/g,'');
    l.innerHTML=`<input type="checkbox" id="${id}" ${subState.includes(n)?'checked':''}> ${esc(n)}`;
    const cb=l.querySelector('input');
    cb.addEventListener('change',()=>{ if(cb.checked){ if(subState.length>=2){cb.checked=false;return} subState.push(n)} else { if(subState.length<=1){cb.checked=true;return} subState=subState.filter(x=>x!==n)} renderSkills(); });
    box.appendChild(l)});
}
/* ---------- 입력: 기술 ---------- */
let skillState={};
const effLv=s=>{if(!s||!s.lv)return 0;const y=(s.yrs===''||s.yrs==null)?0:+s.yrs;return Math.min(+s.lv,y<1?3:y<3?4:5)};
function skillRow(name,star){
  const st=skillState[name]||{}; const id='sk_'+encodeURIComponent(name).replace(/[%.()]/g,'');
  const d=document.createElement('div'); d.className='skill'+(st.lv?' on':''); d.style.flexWrap='wrap';
  d.innerHTML=`<span style="flex:1 1 140px;min-width:0"><label for="${id}">${star?'<b style="color:var(--accent)">★</b> ':''}${esc(name)}</label></span>
    <select id="${id}" aria-label="${esc(name)} 수준" style="width:auto;padding:4px 6px;font-size:12.5px"><option value="">수준</option><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="5">5</option></select>
    <input type="number" min="0" max="40" step="0.5" placeholder="년" aria-label="${esc(name)} 사용 년수" style="width:62px;padding:4px 6px;font-size:12.5px">`;
  const sel=d.querySelector('select'), yr=d.querySelector('input');
  sel.value=st.lv||''; yr.value=st.yrs??'';
  const save=()=>{ if(sel.value){skillState[name]={lv:+sel.value,yrs:yr.value===''?'':+yr.value};d.classList.add('on')} else {delete skillState[name];d.classList.remove('on')} };
  sel.addEventListener('change',save); yr.addEventListener('input',save);
  return d;
}
function curGroups(){
  const P=poolOf($('#duty').value); const out={'업무 역량':[],'도구·시스템':[],'기술·방법론':[]};
  const seen=new Set(); // 같은 항목이 여러 묶음에 있으면 처음 묶음에만 표시
  subState.forEach(sn=>{const sg=P.subs[sn].groups; for(const k in out) (sg[k]||[]).forEach(i=>{if(!seen.has(i)){seen.add(i);out[k].push(i)}})});
  return out;
}
const coreOf=S=>S.core_all&&S.core_all.length?S.core_all:[];
function jobYNow(){const duty=$('#duty').value;let m=0;
  document.querySelectorAll('.career[data-id]').forEach(el=>{const id=el.dataset.id;if($('#ce'+id).value==='인턴'||$('#cj'+id).value!==duty)return;
    const s=ym($('#cs'+id).value),e=$('#cc'+id).checked?nowM:ym($('#cf'+id).value);if(s!=null&&e!=null&&!isNaN(s)&&!isNaN(e)&&e>=s)m+=e-s+1});return m/12}
function renderSkills(){
  const P=poolOf($('#duty').value); const box=$('#skills'); box.innerHTML='';
  $('#skillHint').textContent='가진 항목에 수준(1~5)과 사용 년수를 입력하세요. 이 직무·세부 분야에 맞춰 정리한 목록입니다.';
  $('#skillNoTech').hidden=true;
  box.className=''; box.style.display='flex'; box.style.flexDirection='column'; box.style.gap='14px';
  // 핵심 기술(점수에 반영되는 항목)을 맨 위에 ★로
  let core=[];
  if(P&&P.tech&&P.subs){const m=new Map(); // 핵심 기술은 연차와 관계없이 직무·세부 분야 공고 전체 기준
    subState.forEach(sn=>{const S=P.subs[sn];if(!S)return;coreOf(S).forEach(([i,v])=>{if(!m.has(i)||m.get(i)<v)m.set(i,v)})});
    core=[...m.entries()].sort((a,b)=>b[1]-a[1]).map(x=>x[0]);}
  const cs=new Set(core);
  const groups=Object.entries(curGroups()).map(([g,v])=>[g,v.filter(i=>!cs.has(i))]);
  if(core.length){groups.unshift(['★ 핵심 기술 · 이 직무 공고에서 자주 요구해 점수에 반영되는 항목',core]);
    $('#skillHint').textContent='가진 항목에 수준(1~5)과 사용 년수를 입력하세요. ★ 핵심 기술은 점수에 반영되고, 아래 항목은 기록용으로 저장됩니다.';}
  const listed=new Set(groups.flatMap(([,v])=>v));
  const extra=Object.keys(skillState).filter(k=>!listed.has(k));
  if(extra.length) groups.push(['직접 추가한 기술',extra]);
  let any=false;
  groups.forEach(([gname,items])=>{ if(!items.length) return; any=true;
    const sec=document.createElement('div'); sec.style.display='flex'; sec.style.flexDirection='column'; sec.style.gap='8px';
    sec.innerHTML=`<span class="small" style="font-weight:600">${esc(gname)}</span>`;
    const grid=document.createElement('div'); grid.className='skills'; items.forEach(n=>grid.appendChild(skillRow(n,gname.startsWith('★')))); sec.appendChild(grid); box.appendChild(sec);
  });
  if(!any){box.innerHTML='<p class="muted small">이 직무의 기술 목록은 준비 중입니다. 아래 검색 칸으로 기술을 추가해 주세요.</p>'}
}
$('#skillAdd').addEventListener('click',()=>{const v=$('#skillSearch').value.trim(); if(!v)return;
  const hit=D.alltags.find(x=>x.toLowerCase()===v.toLowerCase())||D.alltags.find(x=>x.toLowerCase().includes(v.toLowerCase()));
  const name=hit||v; if(!(name in skillState)) skillState[name]={lv:3,yrs:1}; $('#skillSearch').value=''; renderSkills();});
/* ---------- 입력: 자격증 ---------- */
let licState={};
function renderLics(){
  const P=poolOf($('#duty').value); const box=$('#lics'); box.innerHTML='';
  const list=P?P.licenses:[];
  const note=$('#licNote'); if(note){note.textContent=[!list.length?'이 직무는 따로 가산점을 주는 자격증이 없습니다.':'',P&&P.lic_req&&P.lic_req.length?`${P.lic_req.join(', ')}${josa(P.lic_req[P.lic_req.length-1],'은','는')} 이 직무를 하려면 원래 필요한 면허라 가산점 대상이 아닙니다.`:''].filter(Boolean).join(' ');note.hidden=!note.textContent}
  list.forEach(n=>{const l=document.createElement('label');l.className='chk tag';l.style.color='var(--ink)';
    const id='lic_'+encodeURIComponent(n).replace(/%/g,'');
    l.innerHTML=`<input type="checkbox" id="${id}" ${licState[n]?'checked':''}> ${esc(n)}`;
    l.querySelector('input').addEventListener('change',e=>{licState[n]=e.target.checked});box.appendChild(l)});
}
$('#engTest').addEventListener('change',()=>{const v=$('#engTest').value;$('#opicWrap').hidden=v!=='opic';$('#engScoreWrap').hidden=(v===''||v==='opic');
  $('#engScore').max=v==='ts'?200:990;$('#engScore').placeholder=v==='ts'?'예: 160':'예: 860'});
/* ---------- 입력: 학력 ---------- */
let eid=0;
function addEdu(e={}){
  const id=++eid; const el=document.createElement('div'); el.className='career'; el.dataset.eid=id;
  el.innerHTML=`<div class="lv-row">
      <label class="lv-f">학위<select id="ed${id}"><option value="고졸">고등학교 졸업</option><option value="전문학사">전문학사</option><option value="학사">학사</option><option value="석사">석사</option><option value="박사">박사</option></select></label>
      <label class="lv-f">상태<select id="es${id}"><option value="졸업">졸업</option><option value="수료">수료</option><option value="재학">재학</option><option value="중퇴">중퇴</option></select></label>
      <label class="lv-f" id="egl${id}">졸업 년월<input type="text" inputmode="decimal" data-ym placeholder="예: 2015.02" autocomplete="off" id="eg${id}" value="${esc(e.grad||'')}"></label>
    </div>
    <div class="lv-row" id="esr${id}">
      <label class="lv-f" style="flex:2 1 240px">학교<input type="text" id="en${id}" list="schoolList" placeholder="학교 이름을 입력하면 목록에서 찾아집니다" value="${esc(e.school||'')}"></label>
      <label class="lv-f">전공<input type="text" id="em${id}" placeholder="예: 전자공학" value="${esc(e.major||'')}"></label>
    </div>
    <div class="lv-row" id="eo${id}" hidden>
      <label class="lv-f">해외 대학 이름<input type="text" id="eon${id}" placeholder="예: University of Michigan" value="${esc(e.oname||'')}"></label>
      <label class="lv-f">세계 대학 랭킹<select id="eor${id}"><option value="10">100위 이내</option><option value="6">101~400위</option><option value="3">그 외 또는 모름</option></select></label>
    </div>
    <div class="lv-row"><button type="button" class="link" data-del>삭제</button></div>`;
  $('#edus').appendChild(el);
  el.querySelector('#ed'+id).value=e.deg||'학사'; el.querySelector('#es'+id).value=e.st||'졸업';
  const sync=()=>{const hs=el.querySelector('#ed'+id).value==='고졸'; el.querySelector('#esr'+id).hidden=hs;
    el.querySelector('#eo'+id).hidden=hs||el.querySelector('#en'+id).value!=='해외 대학'};
  const lab=()=>{const s=el.querySelector('#es'+id).value;el.querySelector('#egl'+id).firstChild.textContent={졸업:'졸업 년월',수료:'수료 년월',재학:'졸업 예정 년월 (선택)',중퇴:'중퇴 년월'}[s]};
  el.querySelector('#es'+id).addEventListener('change',lab); lab();
  el.querySelector('#ed'+id).addEventListener('change',sync); el.querySelector('#en'+id).addEventListener('input',sync); sync();
  el.querySelector('[data-del]').addEventListener('click',()=>el.remove());
}
$('#addEdu').addEventListener('click',()=>addEdu({}));
/* ---------- 입력: 경력 ---------- */
let cid=0;
function addCareer(c={}){
  const id=++cid; const el=document.createElement('div'); el.className='career'; el.dataset.id=id;
  el.innerHTML=`<div class="lv-row">
      <label class="lv-f">회사명<input type="text" id="cn${id}" value="${esc(c.name||'')}" placeholder="예: 현대모비스"></label>
      <label class="lv-f">회사 유형<select id="ct${id}"><option value="">선택해 주세요</option>${TYPES.map(t=>`<option value="${t[0]}">${esc(t[1])}</option>`).join('')}</select></label>
    </div>
    <div class="lv-row">
      <label class="lv-f">직무 분야<select id="cg${id}">${grpOptions(groupOf(c.job||$('#duty').value))}</select></label>
      <label class="lv-f">직무<select id="cj${id}" data-cjob>${dutyOpts(groupOf(c.job||$('#duty').value),c.job||$('#duty').value)}</select></label>
      <label class="lv-f">고용 형태<select id="ce${id}"><option value="정규">정규직</option><option value="계약">계약직</option><option value="인턴">인턴</option></select></label>
    </div>
    <div class="lv-row">
      <label class="lv-f">입사 년월<input type="text" inputmode="decimal" data-ym placeholder="예: 2019.03" autocomplete="off" id="cs${id}" value="${esc(c.start||'')}"></label>
      <label class="lv-f">퇴사 년월<input type="text" inputmode="decimal" data-ym placeholder="예: 2023.08" autocomplete="off" id="cf${id}" value="${esc(c.end||'')}"></label>
      <label class="chk" style="padding-bottom:10px"><input type="checkbox" id="cc${id}" ${c.cur?'checked':''}> 재직 중</label>
      <button type="button" class="link" data-del>삭제</button>
    </div>`;
  $('#careers').appendChild(el);
  if(c.type) el.querySelector('#ct'+id).value=c.type;
  if(c.emp) el.querySelector('#ce'+id).value=c.emp;
  const js=el.querySelector('#cj'+id), gs=el.querySelector('#cg'+id);
  js.addEventListener('change',()=>{js.dataset.touched='1'});
  gs.addEventListener('change',()=>{js.innerHTML=dutyOpts(gs.value);js.dataset.touched='1'});
  if(c.job) js.dataset.touched='1';
  const cur=el.querySelector('#cc'+id), fin=el.querySelector('#cf'+id);
  const sync=()=>{fin.disabled=cur.checked; if(cur.checked) fin.value=''}; cur.addEventListener('change',sync); sync();
  el.querySelector('[data-del]').addEventListener('click',()=>el.remove());
}
$('#addCareer').addEventListener('click',()=>addCareer({}));
function setDuty(duty){$('#grp').value=groupOf(duty);fillDuties();$('#duty').value=duty;onDuty()}
function loadSample(){
  skillState={'C·C++':'3p','RTOS·MCU':'3p','임베디드·펌웨어':'3p','Python':'1to3','Git·형상관리':'3p'};
  setDuty('소프트웨어개발자');
  $('#edus').innerHTML=''; addEdu({deg:'학사',st:'졸업',school:'광운대학교',major:'전자공학'});
  $('#careers').innerHTML='';
  addCareer({name:'(예시) 비상장 전장 협력사',type:'private',job:'소프트웨어개발자',emp:'정규',start:'2017-03',end:'2020-02'});
  addCareer({name:'(예시) 상장 자동차 부품사',type:'listed',job:'소프트웨어개발자',emp:'정규',start:'2020-03',cur:true});
  $('#engTest').value='toeic'; $('#engTest').dispatchEvent(new Event('change')); $('#engScore').value=780; $('#natlic').checked=false;
  renderSkills(); $('#sampleNote').hidden=false;
}
$('#clearBtn').addEventListener('click',()=>{skillState={};licState={};$('#edus').innerHTML='';addEdu({});$('#careers').innerHTML='';addCareer({});
  $('#engTest').value='';$('#engTest').dispatchEvent(new Event('change'));$('#engScore').value='';$('#natlic').checked=false;renderSkills();renderLics();$('#sampleNote').hidden=true});

/* ---------- 계산 ---------- */
function parseYM(s){s=String(s||'').trim(); if(!s) return null;
  let m=s.match(/^(\d{4})\s*(?:[.\-\/]|년)\s*(\d{1,2})\s*월?\.?$/)||s.match(/^(\d{4})(\d{2})$/);
  let y,mo;
  if(m){y=+m[1];mo=+m[2]}
  else if((m=s.match(/^(\d{2})\s*(?:[.\-\/]|년)\s*(\d{1,2})\s*월?\.?$/))){y=+m[1];mo=+m[2];y+= (2000+y<=NOW.y)?2000:1900}
  else return NaN;
  if(mo<1||mo>12||y<1950) return NaN;
  return y*12+(mo-1)}
const ym=parseYM;
const fmtYM=v=>`${Math.floor(v/12)}.${String(v%12+1).padStart(2,'0')}`;
document.addEventListener('focusout',e=>{const el=e.target; if(!el.matches||!el.matches('input[data-ym]'))return;
  const v=parseYM(el.value); if(v==null){el.style.borderColor='';return}
  if(Number.isNaN(v)){el.style.borderColor='var(--warn)';return}
  el.style.borderColor=''; el.value=fmtYM(v)});
const nowM=NOW.y*12+(NOW.m-1);
function engGrade(t,s,o){
  if(t==='toeic')return s>=945?'원어민':s>=850?'비즈니스':s>=550?'일상':null;
  if(t==='ts')return s>=180?'원어민':s>=160?'비즈니스':s>=120?'일상':null;
  if(t==='opic')return {AL:'원어민',IH:'비즈니스',IM3:'일상',IM2:'일상',IM1:'일상'}[o]||null;
  return null;
}
function collect(){
  const edus=[...document.querySelectorAll('[data-eid]')].map(el=>{const id=el.dataset.eid;const school=$('#en'+id).value.trim();
    return {deg:$('#ed'+id).value,st:$('#es'+id).value,g:ym($('#eg'+id).value),school,major:$('#em'+id).value.trim(),oname:$('#eon'+id).value.trim(),orank:+$('#eor'+id).value}});
  const careers=[...document.querySelectorAll('.career[data-id]')].map(el=>{const id=el.dataset.id;
    return {name:$('#cn'+id).value.trim(),type:$('#ct'+id).value,job:$('#cj'+id).value,emp:$('#ce'+id).value,
      s:ym($('#cs'+id).value),e:$('#cc'+id).checked?nowM:ym($('#cf'+id).value),cur:$('#cc'+id).checked}});
  const t=$('#engTest').value;
  return {duty:$('#duty').value,edus,careers,skills:JSON.parse(JSON.stringify(skillState)),subs:[...subState],eng:engGrade(t,+$('#engScore').value,$('#opic').value),
    lic:Object.values(licState).some(Boolean),licNames:Object.keys(licState).filter(k=>licState[k]),natlic:$('#natlic').checked};
}
/* 학력 → 학교 점수, 학위 가산 단계 */
function schoolScore(e){
  if(e.school==='해외 대학') return {score:e.orank||3,label:e.oname||'해외 대학'};
  if(e.school==='학점은행제 (평생교육진흥원)'||e.school==='독학학위제') return {score:3,label:e.school};
  const u=UNIVMAP[e.school]; if(!u) return {score:3,label:e.school||'학교 미입력',unknown:true};
  if(u.kind==='전문대'||u.kind==='원격') return {score:3,label:e.school};
  return {score:u.tier,label:e.school};
}
function eduEval(edus){
  const grads=edus.filter(e=>e.st==='졸업');
  const ba=grads.filter(e=>e.deg==='학사').map(schoolScore).sort((a,b)=>b.score-a.score)[0];
  let school,label,basis;
  if(ba){school=ba.score;label=ba.label;basis='학사'}
  else if(grads.some(e=>e.deg==='전문학사')){school=2;label=grads.find(e=>e.deg==='전문학사').school||'전문대';basis='전문학사'}
  else if(grads.some(e=>e.deg==='석사'||e.deg==='박사')){const g=grads.find(e=>e.deg==='석사'||e.deg==='박사');const s=schoolScore(g);school=s.score;label=s.label;basis='대학원(학부 미입력)'}
  else {school=1;label='고등학교 졸업';basis='고졸'}
  // 석박사: 졸업 = 해당 단계, 수료 = 한 단계 낮은 가산(-1점)
  let adv=null,advSt=null;
  for(const e of edus){ if((e.deg==='석사'||e.deg==='박사')&&(e.st==='졸업'||e.st==='수료')){
    const rank=(e.deg==='박사'?2:1)*10+(e.st==='졸업'?1:0);
    if(!adv||rank>adv.rank) adv={deg:e.deg,st:e.st,rank}; } }
  return {school,label,basis,adv};
}
const ANCHOR={1:'교육·학습으로 안다',2:'도움받아 수행',3:'혼자 실무 수행',4:'복잡 과제·개선 주도',5:'가르치거나 기준을 만든다'};
const SKILL_RULE={'1~3':{k:4,exp:4},'3~7':{k:4,exp:4},'7~12':{k:4,exp:4},'12+':{k:4,exp:4}}; // 연차와 관계없이 같은 기준. 연차대는 핵심 기술 목록을 고르는 데만 씀
const rankOf=y=>y<1?['신입','1년 미만']:y<3?['사원급','1~3년']:y<7?['대리급','3~7년']:y<12?['과장급','7~12년']:['차장·부장급','12년 이상'];
const W_NEW={school:40,exp:20,tech:20,spec:20}; // 신입: 학교·실무 경험·기술·영어/자격(스펙)
const bandOf=y=>y<3?'1~3':y<7?'3~7':y<12?'7~12':'12+';
function evaluate(c){
  const P=poolOf(c.duty), g=P.g; const out={P,g};
  const E=eduEval(c.edus); out.edu=E;
  const valid=c.careers.filter(x=>x.s!=null&&x.e!=null&&x.e>=x.s); const mon=x=>x.e-x.s+1;
  const work=valid.filter(x=>x.emp!=='인턴');
  out.totalY=work.reduce((a,x)=>a+mon(x),0)/12;
  out.jobY=work.filter(x=>x.job===c.duty).reduce((a,x)=>a+mon(x),0)/12;
  out.band=bandOf(out.jobY);
  // 직급대: 총 경력(인턴 제외) 기준. 같은 직급대 안에서 레벨 1~6을 매긴다
  const RK=rankOf(out.totalY); out.rank=RK[0]; out.rankRange=RK[1];
  const reg=valid.filter(x=>x.emp==='정규'); let ten=null; out.tenY=null;
  if(out.totalY>=3&&reg.length){out.tenY=reg.reduce((a,x)=>a+mon(x),0)/reg.length/12;const t=out.tenY;ten=out.totalY<7?(t>=3?10:t>=2?8:t>=1?5:2):(t>=5?10:t>=3?8:t>=2?6:t>=1?4:2)}
  const cur=work.filter(x=>x.cur)[0]||[...work].sort((a,b)=>b.e-a.e)[0]; // 인턴 제외
  // 회사 점수: 경력 기간 × 최근성 가중 평균(최근 3년 1.0 / 3~7년 전 0.6 / 7~10년 전 0.3 / 그 이전 0, 계약직 절반, 인턴 제외)
  //          단, 현재 회사 점수보다 낮아지지 않음. 레벨 하한은 현재 회사에만 적용.
  //          레벨 하한(2026-11-20 대표 확정): 지금 재직 중이고 그 회사에서 1년 이상일 때만, 그리고 계산 레벨보다 최대 2단계까지만 올림.
  const coOf=x=>{const T=TYPE[x.type]||{score:null,floor:1,label:'유형 미입력'};let r={score:T.score,floor:T.floor,label:T.label};
    if(g===SW_GROUP&&SW_PREF.some(k=>(x.name||'').toLowerCase().includes(k.toLowerCase())))r={score:10,floor:5,label:'SW 선호 기업'};return r};
  const recW=ago=>ago<36?1:ago<84?.6:ago<120?.3:0;
  let co=null,floor=1,coLabel='입력 없음',curCo=null;
  if(cur){const r=coOf(cur);curCo=r.score;coLabel=r.label;out.floorFull=r.floor;floor=(cur.cur&&mon(cur)>=12)?r.floor:1}
  const parts=[];let ws=0,wsum=0;
  valid.filter(x=>x.emp!=='인턴').forEach(x=>{const r=coOf(x);if(r.score==null)return;const ew=x.emp==='계약'?.5:1;let w=0;
    for(let m=x.s;m<=x.e;m++)w+=recW(nowM-m)*ew; if(w>0){parts.push({x,score:r.score,label:r.label,w});ws+=w*r.score;wsum+=w}});
  const avg=wsum?ws/wsum:null;
  co=avg==null?curCo:curCo==null?avg:Math.max(avg,curCo);
  out.coAvg=avg; out.coCur=curCo; out.coParts=parts.map(p=>({...p,share:p.w/wsum}));
  out.coBasis=avg!=null&&curCo!=null&&curCo>=avg?'현재 회사':'경력 가중';
  if(co!=null)co=Math.round(co*10)/10;
  out.cur=cur; out.coLabel=coLabel;
  let tech=null; out.core=[]; out.cover=null;
  out.sub=null;
  // 기술 일치도: ★ 핵심 기술(공고에서 자주 요구된 항목, 4~8개) 중 본인이 가장 잘하는 K개만 본다. 기대 수준(4단계)에 닿으면 그 칸은 만점.
  // 도구·시스템은 4칸의 절반까지만(개발 분야는 제한 없음). ★에 도구가 많아 4칸을 다 채울 수 없는 분야는 채울 수 있는 칸 수로 나눔.
  const SK=SKILL_RULE[out.band]; out.K=SK.k; out.exp=SK.exp;
  if(P&&P.tech){let best=null;
    for(const sn of (c.subs&&c.subs.length?c.subs:Object.keys(P.subs))){const S=P.subs[sn];const core=coreOf(S);const tools=new Set(S.groups['도구·시스템']||[]);
      const nTool=core.filter(([t2])=>tools.has(t2)).length, nOther=core.length-nTool;
      const K=Math.max(1,Math.min(SK.k,nOther+(g===SW_GROUP?nTool:Math.min(nTool,Math.floor(SK.k/2)))));
      const cand=core.map(([t2])=>({t:t2,v:Math.min(1,effLv(c.skills[t2])/SK.exp),tool:tools.has(t2)})).filter(x=>x.v>0).sort((a,b)=>b.v-a.v);
      const pick=[];let nt=0;for(const x of cand){if(pick.length>=K)break;if(x.tool&&g!==SW_GROUP){if(nt>=Math.floor(SK.k/2))continue;nt++}pick.push(x)}
      const cov=pick.reduce((a,x)=>a+x.v,0)/K; if(!best||cov>best.cov)best={sn,core,cov,pick,K}}
    out.core=best.core; out.cover=best.cov; out.sub=best.sn; out.pick=best.pick; out.K=best.K; tech=Math.max(1,Math.round(out.cover*10))}
  let it,prof={};
  if(out.rank==='신입'){
    // 실무 경험: 인턴·계약·정규 경험 중 가장 높은 회사 급 × 기간 계수(6개월 이상 1.0, 3~6개월 0.7, 3개월 미만 0.4). 없으면 2점
    const expM=valid.reduce((a,x)=>a+mon(x),0); const bestCo=valid.map(x=>coOf(x).score).filter(v=>v!=null).reduce((m,v)=>Math.max(m,v),0);
    const exp=bestCo?Math.max(2,Math.round(bestCo*(expM>=6?1:expM>=3?.7:.4)*10)/10):2;
    // 영어·자격(스펙): 영어 원어민 7 / 비즈니스 5 / 일상 3, 직무 자격증 +3, 국가기술자격 +2, 최대 10, 최소 1
    const spec=Math.max(1,Math.min(10,({원어민:7,비즈니스:5,일상:3}[c.eng]||0)+(c.lic?3:0)+(c.natlic?2:0)));
    it={school:E.school,exp,tech,spec}; floor=1; out.cur=null;
    let s1=0,s2=0;for(const[k,w] of Object.entries(W_NEW)){if(it[k]==null)continue;s1+=w*it[k];s2+=w}const sc=s2?s1/s2*10:0; prof={L:sc,M:sc,S:sc};
  } else {
    it={school:E.school,co,ten,tech};
    for(const p of ['L','M','S']){let t=0,s=0;for(const[k,w] of Object.entries(W[p])){if(it[k]==null)continue;t+=w*it[k];s+=w}prof[p]=s?t/s*10:0}
  }
  out.items=it; out.prof=prof;
  const ty=P?P.type:{deg:'기본',eng:'기본',lic:'기본'}; out.ty=ty;
  const gate=[];
  if(ty.deg==='관문'&&!(E.adv&&E.adv.st==='졸업'))gate.push('석사 이상 학위');
  if(ty.eng==='관문'&&!c.eng)gate.push('영어 공인 점수');
  if(ty.lic==='관문'&&!c.lic&&P.licenses.length&&!(P.lic_req&&P.lic_req.length))gate.push('직무 자격증'); // 직무 자체가 면허인 경우(변호사 등)는 관문 대상 아님
  out.gate=gate;
  const bd=[];let b=0;
  if(E.adv){const full=BONUS.deg[ty.deg==='큰'?'큰':'기본'][E.adv.deg];const v=E.adv.st==='수료'?Math.max(0,full-1):full;b+=v;bd.push([`${E.adv.deg} ${E.adv.st}`,v])}
  if(out.rank!=='신입'&&c.eng){const v=BONUS.eng[ty.eng==='큰'?'큰':'기본'][c.eng];b+=v;bd.push(['영어 '+c.eng+' 수준',v])}
  if(out.rank!=='신입'&&c.lic){const v=BONUS.lic[ty.lic==='큰'?'큰':'기본'];b+=v;bd.push(['직무 자격증',v])}
  if(out.rank!=='신입'&&c.natlic){const v=out.jobY<7?2:1;b+=v;bd.push(['국가기술자격',v])} // 연차가 쌓이면 실무 이력이 증명하므로 가산 축소
  out.bonusRaw=b;out.bonus=Math.min(8,b);out.bonusDetail=bd;
  const lvl=s=>s.L>=85?6:s.L>=75?5:s.M>=70?4:s.M>=60?3:s.S>=50?2:1;
  out.raw=lvl(prof);
  out.withBonus=Math.min(lvl({L:Math.min(100,prof.L+out.bonus),M:Math.min(100,prof.M+out.bonus),S:Math.min(100,prof.S+out.bonus)}),out.raw+1);
  out.floor=Math.min(floor,out.withBonus+2); out.level=Math.max(out.withBonus,out.floor);
  return out;
}
function nextPaths(c,base){
  const target=base.level+1; if(target>6)return{target:null,paths:[]};
  const moves=[];
  const ex=base.exp, ny=ex>=5?3:ex>=4?1:0;
  base.core.forEach(([t])=>{if(effLv(c.skills[t])<ex)moves.push({label:`${t} ${ex}단계(${ANCHOR[ex]})로 올리기`,cost:2,apply:x=>{x.skills={...x.skills,[t]:{lv:ex,yrs:Math.max(ny,(c.skills[t]&&+c.skills[t].yrs)||0)}}}})});
  const up={null:'일상',일상:'비즈니스',비즈니스:'원어민'};const nx=up[c.eng];
  if(nx)moves.push({label:`영어 ${nx==='원어민'?'원어민':nx+'회화'} 수준 점수 취득`,cost:1,apply:x=>{x.eng=nx}});
  if(!c.lic)moves.push({label:'직무 인정 자격증 취득',cost:2,apply:x=>{x.lic=true}});
  if(!c.natlic)moves.push({label:'국가기술자격 취득',cost:2,apply:x=>{x.natlic=true}});
  if(!base.edu.adv)moves.push({label:'석사 학위 취득',cost:5,apply:x=>{x.edus=[...x.edus,{deg:'석사',st:'졸업',school:''}]}});
  const found=[];const test=combo=>{const x=JSON.parse(JSON.stringify(c));combo.forEach(m=>m.apply(x));return evaluate(x).level>=target};
  moves.forEach(m=>{if(test([m]))found.push({cost:m.cost,n:1,items:[m]})});
  for(let i=0;i<moves.length;i++)for(let j=i+1;j<moves.length;j++){const a=moves[i],b=moves[j];
    if(found.some(f=>f.n===1&&(f.items[0]===a||f.items[0]===b)))continue; if(test([a,b]))found.push({cost:a.cost+b.cost,n:2,items:[a,b]})}
  found.sort((p,q)=>p.cost-q.cost||p.n-q.n); return{target,paths:found.slice(0,3)};
}
/* ---------- 종합 의견 · 성장 포인트 · 러닝 플랜 · 커리어 코칭 (규칙 기반, AI 미사용) ---------- */
const CO_SHORT={big10:'대기업',big:'대기업',bigsub:'대기업',listed:'상장사',unicorn:'유니콘',public:'공공기관',foreign:'외국계',private:'비상장 기업',gbig:'해외 대기업',glisted:'해외 상장사',gprivate:'해외 비상장 기업'};
const TECH_GROUPS=['엔지니어링·설계','제조·생산','AI·개발·데이터','건축·시설'];
const LV_KEY={6:['L',85],5:['L',75],4:['M',70],3:['M',60],2:['S',50]};
const ENG_TARGET={일상:'TOEIC 550 · OPIc IM1 · TOEIC Speaking 120 이상',비즈니스:'TOEIC 850 · OPIc IH · TOEIC Speaking 160 이상',원어민:'TOEIC 945 · OPIc AL · TOEIC Speaking 180 이상'};
const clone=o=>JSON.parse(JSON.stringify(o));
const fmtNow=m=>fmtYM(m);
const hasBatchim=w=>{w=String(w).replace(/\s*\([^)]*\)\s*$/,'').trim();const ch=w.charCodeAt(w.length-1);
  if(ch>=0xAC00&&ch<=0xD7A3)return (ch-0xAC00)%28!==0;
  const l=w[w.length-1];if(/[0-9]/.test(l))return '0136789'.includes(l);
  if(/[A-Z]/.test(l)&&/[A-Z]{2,}$/.test(w))return 'LMNR'.includes(l); // 약어는 알파벳 이름으로 읽음
  return /(ng|m|n|l)$/i.test(w)};
const josa=(w,a,b)=>hasBatchim(w)?a:b; // 조사만 반환, 받침 있으면 a
const roEuro=w=>{const ch=w.charCodeAt(w.length-1);if(ch<0xAC00||ch>0xD7A3)return '로';const j=(ch-0xAC00)%28;return (j===0||j===8)?'로':'으로'};
function gapTo(r,target){if(!LV_KEY[target])return null;const[k,thr]=LV_KEY[target];return Math.max(0,thr-Math.min(100,r.prof[k]+r.bonus))}
const dotTxt=v=>v==null?'-':'●'.repeat(Math.round(v/2))+'○'.repeat(5-Math.round(v/2));
const EL_NAME={school:'학교',co:'회사 경력',ten:'평균 근속',tech:'기술 일치도',exp:'실무 경험',spec:'영어·자격'};
const ADD_NAME={eng:p=>p.title.replace(' 공인 점수',''),lic:()=>'직무 자격증',nat:()=>'국가기술자격',deg:()=>'석사 학위'};
function effectTxt(r,p){
  const r2=p.r2, parts=[];
  for(const k of ['school','co','ten','tech','exp','spec']){const a=r.items[k],b=r2.items[k];if(a==null||b==null||b<=a)continue;
    parts.push(Math.round(a/2)!==Math.round(b/2)?`${EL_NAME[k]} <span class="lv-dt">${dotTxt(a)}</span> → <span class="lv-dt">${dotTxt(b)}</span>`:`${EL_NAME[k]} 강화 <span class="lv-dt">${dotTxt(b)}</span>`)}
  if(ADD_NAME[p.kind]&&r.rank!=='신입') parts.push(`추가 반영 항목에 ${ADD_NAME[p.kind](p)} 추가`);
  if(r2.level>r.level) parts.push(`<b>레벨 ${r.level} → ${r2.level}</b>`);
  return parts.join(' · ');
}
/* 성장 포인트 결론: 몇 번을 함께 하면 레벨이 오르는지 */
function pointsConclusion(c,r,pts,cc){
  if(r.level>=6) return '가장 높은 레벨입니다. 아래 포인트는 강점을 굳히는 데 도움이 됩니다.';
  const t=r.level+1, nm=`<b>레벨 ${t}</b>(${LV[t][0]})`;
  const reach=idx=>{const x=clone(c);idx.forEach(i=>pts[i].apply(x));return evaluate(x).level>=t};
  const n=pts.length, combos=[];
  for(let i=0;i<n;i++)combos.push([i]);
  for(let i=0;i<n;i++)for(let j=i+1;j<n;j++)combos.push([i,j]);
  if(n===3)combos.push([0,1,2]);
  const hit=combos.find(reach);
  if(hit) return hit.length===1?`${hit[0]+1}번만 해도 ${nm}${josa(LV[t][0],'이','가')} 됩니다.`:`${hit.map(i=>i+1+'번').join('과 ').replace(/과 (?=[^과]*$)/, hit.length>2?', ':'과 ')}을 함께 하면 ${nm}${josa(LV[t][0],'이','가')} 됩니다.`;
  const mv=(cc.scen||[]).filter(([lab])=>lab.startsWith('지금 ')&&lab!=='지금 회사에 3년 더').find(([,x])=>x.level>=t);
  const stay=(cc.scen||[]).find(([lab,x])=>lab==='지금 회사에 3년 더'&&x.level>=t);
  const head='';
  if(stay&&mv) return head+`${nm}는 지금 회사에서 근속이 쌓이거나 <b>회사를 옮길 때</b> 열립니다(커리어 코칭 참고).`;
  if(mv) return head+`${nm}${roEuro(LV[t][0])} 가려면 <b>회사 이동</b>이 필요합니다(커리어 코칭 참고).`;
  if(stay) return head+`지금 회사에서 근속이 쌓이면 ${nm}에 닿습니다(커리어 코칭 참고).`;
  if(r.rank==='신입') return `${nm}까지는 위 포인트를 모두 채워도 거리가 남습니다. 신입은 학교 비중이 커서, 실무 경험과 영어·자격을 가능한 한 높게 채우는 것이 현실적인 방법입니다.`;
  const it=r.items; const fixed=it.school!=null&&it.school<8&&(it.co==null||it.co>=8)&&(it.tech==null||it.tech>=8);
  return head+(fixed?`${nm}까지 남은 차이는 주로 <b>학교</b> 요소에서 옵니다. 바꿀 수 없는 요소라, 영어·자격 같은 추가 반영 항목과 근속을 함께 쌓아 메우는 것이 현실적인 방법입니다.`
                   :`${nm}${roEuro(LV[t][0])} 가려면 지금 바꿀 수 있는 요소 외에 시간이 쌓이며 오르는 요소(근속·회사 경력)가 함께 필요합니다.`);
}
function groupOfItem(P,sub,t){const g=P.subs[sub]?.groups||{};for(const k of ['업무 역량','도구·시스템','기술·방법론'])if((g[k]||[]).includes(t))return k;return '업무 역량'}
const SALES_G=['영업','고객상담·TM'];
const NOTECH_TXT='이 직무는 서치잡 공고가 아직 충분하지 않아 기술 일치도를 레벨에 넣지 않았습니다. 맡은 업무 범위와 성과를 숫자로 정리해 두면 서류에서 실무 역량을 보여줄 수 있습니다.';
function typeOf(c,r){
  const s=v=>v!=null&&v>=8, it=r.items, tech=r.P&&r.P.tech;
  if(r.jobY<3) return 'early';
  if(r.tenY!=null&&r.tenY<2) return 'mover';
  const bg=s(it.school)||s(it.co);
  if(tech&&bg&&s(it.tech)) return 'all';
  if(bg) return 'record';
  if(tech&&s(it.tech)) return 'skill';
  return 'base';
}
function opinion(c,r,type){
  const P=r.P, tech=P&&P.tech, sub=r.sub&&r.sub!=='직무 전체'?r.sub:c.duty, it=r.items;
  const out=[];
  out.push(`${c.duty}${r.sub&&r.sub!=='직무 전체'?`(${r.sub})`:''} ${r.rank==='신입'?'신입':`${r.rank}(경력 ${r.rankRange})`} 중 <b>${LV[r.level][0]}</b>입니다.`);
  const strong=[],weak=[];
  if(it.school!=null){if(it.school>=8)strong.push('출신 학교');else if(it.school<6)weak.push('학교 이력')}
  if(it.co!=null){if(it.co>=8)strong.push('회사 경력');else if(it.co<6)weak.push('회사 이력')}
  if(it.exp!=null){if(it.exp>=8)strong.push('실무 경험(인턴)');else if(it.exp<6)weak.push('실무 경험')}
  if(it.spec!=null){if(it.spec>=8)strong.push('영어·자격');else if(it.spec<6)weak.push('영어·자격')}
  if(it.ten!=null){if(it.ten>=8)strong.push(`안정적인 근속(평균 ${r.tenY.toFixed(1)}년)`);else if(it.ten<6)weak.push(`평균 근속(${r.tenY.toFixed(1)}년)`)}
  if(tech){if(it.tech>=8)strong.push(`${sub} 실무 역량`);else if(it.tech<6)weak.push(`${sub} 핵심 기술의 깊이`)}
  if(strong.length) out.push(`강점은 ${strong.join(', ')}입니다.`);
  const T={
    early: r.rank==='신입'?`신입 서류에서는 학교 다음으로 실무 경험(인턴)과 영어·자격이 당락을 가릅니다. 학교는 바꿀 수 없으니, 나머지 세 가지 중 비어 있는 것부터 채우는 것이 가장 빠른 길입니다.`:`직무 연차가 3년 미만이라 지금은 이력보다 앞으로 무엇을 쌓느냐가 다음 단계를 좌우합니다. 핵심 기술을 혼자 수행하는 수준(3단계) 이상으로 다지는 것이 우선입니다.${(()=>{const cu=c.careers.find(x=>x.cur&&x.emp!=='인턴');return cu&&cu.e-cu.s+1<24?' 지금 회사에서 2년 이상 근속을 만드는 것도 중요합니다.':''})()}`,

    mover:`평균 근속이 ${r.tenY!=null?r.tenY.toFixed(1):'-'}년으로 짧아, 서류에서는 다른 강점보다 잦은 이동이 먼저 눈에 띕니다. 다음 이동은 오래 머물 수 있는 곳인지를 가장 먼저 따져야 합니다.`,
    all:`학교·회사 이력과 실무 역량을 함께 갖춰, 한 단계 위 회사에 지원할 기반이 있습니다. 남은 차이는 영어·자격 같은 추가 반영 항목과 지원 전략으로 좁힐 수 있습니다.`,
    record: tech?`서류에서 먼저 보이는 학교·회사 이력은 강점이지만, ${sub} 핵심 기술의 깊이는 보강 여지가 있습니다. 면접에서는 이력보다 실무 깊이를 확인하므로, 핵심 기술을 기대 수준(${r.exp}단계)까지 채우는 것이 가장 효과적입니다.`
                :`서류에서 먼저 보이는 학교·회사 이력은 강점입니다. ${SALES_G.includes(r.g)?'이 직무는 기술보다 실적으로 평가받으므로, 담당 매출·고객·성과를 숫자로 정리해 두는 것이 다음 단계에서 가장 효과적입니다.':NOTECH_TXT}`,
    skill:`다만 학교·회사 이력이 이 실무 역량을 서류에서 충분히 드러내지 못하고 있습니다. 실력을 이력으로 바꾸는 것, 즉 한 단계 위 회사로의 이동과 영어·자격 같은 서류 보완이 레벨을 올리는 길입니다.`,
    base: tech?`아직 뚜렷하게 앞서는 항목은 없지만, 효과가 큰 한두 가지에 집중하면 레벨이 움직입니다. 특히 ${sub} 핵심 기술은 지금 회사에서 바로 키울 수 있어 가장 먼저 손댈 만합니다.`
              :`아직 뚜렷하게 앞서는 항목은 없지만, 효과가 큰 한두 가지에 집중하면 레벨이 움직입니다. ${SALES_G.includes(r.g)?'이 직무는 실적이 곧 경쟁력이므로 성과를 숫자로 남기는 습관부터 만드는 것이 좋습니다.':NOTECH_TXT}`};
  out.push(T[type]);
  if(P&&P.lic_hint&&!c.lic) out.push(P.lic_hint);
  // 회사 경력 흐름: 과거에 더 높은 회사가 있었는데 지금은 낮은 경우
  const parts=(r.coParts||[]).slice().sort((a,b)=>a.x.s-b.x.s); const curP=parts.find(p=>p.x.cur);
  const best=parts.reduce((m,p)=>!m||p.score>m.score?p:m,null);
  if(curP&&best&&best.score>=curP.score+3) out.push(`${CO_SHORT[best.x.type]||'이전 회사'} 경력이 있지만 최근 경력이 ${CO_SHORT[curP.x.type]||'현재 회사'}${josa(CO_SHORT[curP.x.type]||'현재 회사','이라','라')} 회사 점수는 ${it.co}점으로 반영됐습니다. 상위 회사에 지원할 때는 옮긴 이유와 지금 회사에서 맡고 있는 범위를 분명히 설명할 수 있어야 합니다.`);
  else if(weak.length) out.push(`보강이 필요한 부분은 ${weak.join(', ')}입니다.`);
  return out.join(' ');
}
function skillMoves(c,r){
  if(!(r.P&&r.P.tech)) return [];
  const ex=r.rank==='신입'?3:r.exp, ny=ex>=5?3:ex>=4?1:0; // 신입은 학습으로 갈 수 있는 3단계까지 목표
  return r.core.filter(([t])=>effLv(c.skills[t])<ex).map(([t,v])=>({t,v,cur:effLv(c.skills[t]),yrs:c.skills[t]?+c.skills[t].yrs||0:0,target:ex,ny}));
}
function applySkills(x,items,cap){items.forEach(i=>{const lv=cap?Math.min(cap,i.target):i.target;const yrs=lv>=5?Math.max(3,i.yrs):lv>=4?Math.max(1,i.yrs):i.yrs;x.skills={...x.skills,[i.t]:{lv:Math.max(lv,i.cur),yrs}}})}
const periodSkill=i=>i.target<=3?'1~3개월':i.target===4?(i.yrs>=1?'3~6개월':'6~12개월 (실무 사용 1년 필요)'):(i.yrs>=3?'6~12개월':'1년 이상 (실무 사용 3년 필요)');
function growthPoints(c,r){
  const P=r.P, pts=[];
  const sm=skillMoves(c,r);
  for(let k=0;k<2&&sm.length>k*2;k++){const items=sm.slice(k*2,k*2+2);
    pts.push({kind:'skill',items,title:`${items.map(i=>i.t).join(', ')}${josa(items[items.length-1].t,'을','를')} ${items[0].target}단계(${ANCHOR[items[0].target]})로`,
      why:`이 직무 공고에서 자주 요구하는 핵심 기술인데 지금은 ${items.map(i=>`${i.t} ${i.cur||'미입력'}`).join(', ')} 수준입니다.`,
      period:periodSkill(items.reduce((a,b)=>a.target-a.yrs>b.target-b.yrs?a:b)),cost:2,apply:x=>applySkills(x,items)});}
  if(r.rank==='신입'&&(r.items.exp??0)<6) pts.push({kind:'intern',title:'인턴·현장실습 6개월 (상장사 이상)',why:'신입 서류에서 실무 경험은 학교 다음으로 크게 봅니다. 회사 급과 기간을 함께 봅니다.',period:'6개월',cost:2,apply:x=>{x.careers=[...x.careers,{name:'(가정) 인턴',type:'listed',job:c.duty,emp:'인턴',s:nowM-5,e:nowM,cur:false}]}});
  const up={null:'일상',일상:'비즈니스',비즈니스:'원어민'};const nx=up[c.eng];
  if(nx) pts.push({kind:'eng',title:`영어 ${nx==='원어민'?'원어민':nx+'회화'} 수준 공인 점수`,why:`${ENG_TARGET[nx]}이면 인정됩니다.${P.type.eng==='큰'?' 이 직무는 공고 자격요건에 영어가 자주 나와 가산점이 큽니다.':''}`,period:'2~4개월',cost:1,apply:x=>{x.eng=nx}});
  const shortLic=P.licenses.filter(n=>!(P.lic_long||[]).includes(n)&&!(c.licNames||[]).includes(n));
  if(!c.lic&&shortLic.length) pts.push({kind:'lic',title:`직무 자격증 (${shortLic.slice(0,3).join(', ')})`,why:'이 직무 공고의 자격요건·우대사항에 자주 나온 자격증입니다.',period:'자격별로 다름',cost:3,apply:x=>{x.lic=true}});
  if(!c.natlic&&TECH_GROUPS.includes(r.g)&&r.jobY<7&&!(c.licNames||[]).some(n=>/기사|기술사/.test(n))) pts.push({kind:'nat',title:'국가기술자격 (기사·산업기사)',why:'기술 직군에서 기본 가산점으로 인정합니다.',period:'6개월~1년',cost:3,apply:x=>{x.natlic=true}});
  if(!r.edu.adv&&P.type.deg==='큰') pts.push({kind:'deg',title:'석사 학위',why:'이 직무는 공고 자격요건에 석사 이상이 자주 나와 학위 가산점이 큽니다.',period:'2년',cost:5,apply:x=>{x.edus=[...x.edus,{deg:'석사',st:'졸업',school:'',g:nowM}]}});
  pts.forEach(p=>{const x=clone(c);p.apply(x);p.r2=evaluate(x);p.gain=(p.r2.level-r.level)*100+((gapTo(r,r.level+1)??0)-(gapTo(p.r2,r.level+1)??0));p.score=p.gain/p.cost});
  return pts.filter(p=>p.gain>0.05).sort((a,b)=>b.score-a.score).slice(0,3);
}
const METHOD={
  '업무 역량':{3:'실무 교재·강의로 절차를 익히고, 실제 건을 선배와 함께 처음부터 끝까지 한 번 수행해 봅니다.',4:'개선이 필요한 과제를 직접 맡아 기획부터 결과 보고까지 이끌고, 개선 전후를 숫자로 남깁니다.',5:'업무 기준이나 가이드 문서를 만들고, 사내 교육이나 후배 지도를 맡습니다.'},
  '도구·시스템':{3:'공식 교육 과정이나 튜토리얼로 기능을 익히고, 실제 업무 데이터로 반복 실습합니다.',4:'이 도구로 실제 과제를 처음부터 끝까지 맡아 결과물(설계·개발·분석·보고 등)을 만들고, 처리 규모나 개선 효과를 남깁니다.',5:'사내 사용 기준을 정리하고, 다른 사람에게 사용법을 가르칩니다.'},
  '기술·방법론':{3:'원리와 기준을 강의·교재로 정리하고, 실제 과제에 적용해 봅니다.',4:'난이도가 높은 과제(새 방식 도입, 문제 해결)를 맡아 적용 근거와 결과를 문서로 남깁니다.',5:'회사 내부 표준·기준을 세우고, 새 기술·제도 변화에 대한 대응을 주도합니다.'}};
const EVID={'업무 역량':'맡은 건의 범위(규모·건수), 본인 역할, 개선 전후 수치(기간 단축, 오류 감소 등)','도구·시스템':'사용한 범위(모듈·기능), 맡은 과제와 결과물, 처리 규모, 관련 자격 취득일','기술·방법론':'적용한 기술·방법, 맡은 과제, 결과(성능·품질 개선, 오류·불량 감소, 기준 정착 등)'};
const HOW_TYPE={3:'강의(온라인·국비 훈련 과정) · 교재 · 실습 과제',4:'사내 과제 · 프로젝트 · 스터디',5:'사내 강의 · 가이드 작성 · 멘토링'};
function learningPlan(c,r,pts){
  if(!(r.P&&r.P.tech)) return null;
  const sm=skillMoves(c,r).slice(0,4); if(!sm.length) return {items:[],road:[]};
  const items=sm.map(i=>({...i,grp:groupOfItem(r.P,r.sub,i.t)}));
  // 로드맵: 학습 효과만 반영(시간 경과에 따른 근속 변화는 커리어 코칭에서 따로 봄)
  const engPt=pts.find(p=>p.kind==='eng'), licPt=pts.find(p=>p.kind==='lic'||p.kind==='nat');
  const x=clone(c), road=[];
  const step=(label,todo,fn)=>{fn&&fn(x);const r2=evaluate(x);road.push({label,todo,r2})};
  const t3=items.filter(i=>i.cur<3);
  step('0~3개월',[...t3.map(i=>`${i.t}: 3단계(혼자 수행)까지`),...(engPt?[engPt.title+' 준비·응시']:[])].concat(t3.length||engPt?[]:['핵심 기술 중 가장 약한 항목 기초 다지기']),x=>{applySkills(x,t3,3);engPt&&engPt.apply(x)});
  const t4=items.filter(i=>i.target>=4);
  step('3~12개월',[...t4.map(i=>`${i.t}: ${Math.min(4,i.target)}단계(${ANCHOR[Math.min(4,i.target)]}) — 실무 과제로`),...(licPt?[licPt.title+' 준비']:[])],x=>{applySkills(x,t4,4);licPt&&licPt.apply(x)});
  const t5=items.filter(i=>i.target>=5);
  if(t5.length) step('1년 이후',t5.map(i=>`${i.t}: 5단계(기준을 만든다) — 사내 강의·가이드`),x=>applySkills(x,t5,5));
  return {items,road};
}
function careerCoach(c,r){
  const out=[]; const valid=c.careers.filter(x=>x.s!=null&&x.e!=null&&x.e>=x.s); const mon=x=>x.e-x.s+1;
  const reg=valid.filter(x=>x.emp==='정규'); const cur=valid.find(x=>x.cur&&x.emp!=='인턴');
  const junior=r.totalY<7; // 대리급까지는 평균 3년이면 만점
  const tenScore=y=>junior?(y>=3?10:y>=2?8:y>=1?5:2):(y>=5?10:y>=3?8:y>=2?6:y>=1?4:2); const THR=junior?[1,2,3]:[1,2,3,5]; const floorY=y=>[...THR].reverse().find(t=>y>=t)||0;
  if(reg.length&&r.tenY!=null){
    const sum=reg.reduce((a,x)=>a+mon(x),0)/12, n=reg.length, thr=floorY(r.tenY);
    if(cur&&cur.emp==='정규'&&mon(cur)<24){const left=24-mon(cur);out.push(`<b>이직 시점</b> · 현재 회사 근속이 ${(mon(cur)/12).toFixed(1)}년입니다. 2년을 채우는 ${fmtNow(nowM+left)} 이후에 옮기면 짧은 근속 이력을 남기지 않습니다.`)}
    const nextThr=THR.find(t=>t>r.tenY);
    if(cur&&cur.emp==='정규'&&nextThr&&tenScore(nextThr)>r.items.ten){const m=Math.ceil((nextThr*n-sum)*12);if(m>0&&m<=24)out.push(`<b>근속 점수</b> · 지금 회사에 ${fmtNow(nowM+m)}까지 다니면 평균 근속이 ${nextThr}년이 되어 근속 점수가 ${r.items.ten} → ${tenScore(nextThr)}점으로 오릅니다.`)}
    if(r.tenY<2){const nt=THR.find(x=>x>r.tenY);const need=Math.ceil((nt*(n+1)-sum)*2)/2;out.push(`<b>다음 회사</b> · 지금은 평균 근속이 ${r.tenY.toFixed(1)}년입니다. 다음 회사에서 ${need}년 이상 다녀야 평균이 ${nt}년이 되어 근속 점수가 ${r.items.ten} → ${tenScore(nt)}점으로 오릅니다. 이번 이동은 오래 머물 수 있는 곳인지를 가장 먼저 보세요.`)}
    else if(thr>0){const need=Math.max(0,thr*(n+1)-sum);out.push(need<1?`<b>다음 회사</b> · 평균 근속에 여유가 있어 다음 회사를 짧게 다녀도 근속 점수(${r.items.ten}점)는 유지됩니다. 다만 1~2년 만의 이동은 서류에서 그 자체로 질문을 받으니, 다음 회사도 2년 이상을 기준으로 고르는 것이 좋습니다.`:`<b>다음 회사</b> · 다음 회사에서는 최소 ${Math.ceil(need*2)/2}년 이상 근무해야 지금의 근속 점수(${r.items.ten}점, 평균 ${thr}년 이상)가 유지됩니다.`)}
  }
  // 3년 뒤 시나리오: 그대로 다닐 때 / 지금 옮길 때(회사 급별)
  const shift=(x,mth)=>{x.careers.forEach(k=>{if(k.s!=null)k.s-=mth;if(k.e!=null&&!k.cur)k.e-=mth})};
  const scen=[];
  if(cur){const x=clone(c);shift(x,36);x.careers.forEach(k=>{if(k.cur)k.e=nowM});const r2=evaluate(x);scen.push(['지금 회사에 3년 더',r2])}
  const curType=cur?CO_SHORT[cur.type]:null;
  [['big','대기업'],['listed','상장사·외국계·공공기관'],['private','비상장 기업']].forEach(([ty,lab])=>{
    const x=clone(c);shift(x,36);x.careers.forEach(k=>{if(k.cur){k.cur=false;k.e=nowM-36}});
    x.careers.push({name:'(가정) 다음 회사',type:ty,job:c.duty,emp:'정규',s:nowM-35,e:nowM,cur:true});const r2=evaluate(x);scen.push([r.rank==='신입'?`${lab}에 입사해 3년`:`지금 ${lab}${roEuro(lab)} 옮겨 3년`,r2])});
  const bandNow=r.band;
  return {notes:out,scen,bandNow,
    bandNext:(()=>{const b=[3,7,12].find(t=>t>r.jobY);if(!b)return null;const m=Math.ceil((b-r.jobY)*12);return m<=36?`직무 연차 ${b}년이 되는 ${fmtNow(nowM+m)}부터는 ${b===3?'3~7년':b===7?'7~12년':'12년 이상'} 연차대로 평가됩니다. 기대 수준이 ${SKILL_RULE[b===3?'3~7':b===7?'7~12':'12+'].exp}단계로 바뀌니 미리 준비해 두는 것이 좋습니다.`:null})()};
}
const RANGE={6:['대기업 전반','대기업 상위 그룹·핵심 직무','—'],5:['상장사·외국계·공공기관, 대기업 일부','대기업','대기업 상위 그룹'],4:['상장사·외국계·공공기관','대기업 일부','대기업'],
  3:['비상장 우량 기업, 상장사 일부','상장사·외국계·공공기관','대기업'],2:['비상장 기업','상장사 일부','상장사·외국계·공공기관'],1:['비상장 기업','비상장 우량 기업','상장사']};
/* 연차가 긴 경력자 안내 (2026-11-23 대표님 확정). 나이는 받지 않고 레벨에도 넣지 않습니다(연령 차별 소지).
   대신 총 경력 20년·25년을 기준으로 시장 현실과 현실적인 경로를 커리어 코칭에 안내합니다. */
function seniorNote(r){
  const y=r.totalY||0;
  if(y>=25) return `<div class="lv-senior"><p class="small"><b>경력 25년 이상이면</b> 같은 레벨이라도 실무 포지션 공고의 문은 좁아지는 것이 현실입니다. 대신 경험 자체가 무기가 되는 자리가 열립니다.</p><ul class="il small"><li>중견·중소기업의 임원, 본부장, 공장장</li><li>전문위원, 기술 자문</li><li>지금 일하는 업계의 협력사·고객사로 이동</li></ul><p class="small">레벨은 지금 경력이 가진 가치를 보여 줍니다. 어느 자리를 노릴지는 이 경로들을 함께 놓고 정하세요.</p></div>`;
  if(y>=20) return `<div class="lv-senior"><p class="small"><b>경력 20년이 넘으면</b> 채용 시장의 문이 달라집니다. 공개 채용 공고는 주로 실무 책임자 자리를 뽑고, 그 위 자리는 공고 없이 추천이나 헤드헌팅으로 채우는 경우가 많습니다. 지원서를 많이 내는 것보다 아래 세 가지가 더 효과적입니다.</p><ul class="il small"><li>헤드헌터와 꾸준히 연락을 이어 두기</li><li>업계 사람들에게 지금 하는 일과 강점을 알려 두기</li><li>이력서를 맡았던 조직 규모와 성과 중심으로 다듬기</li></ul></div>`;
  return '';
}
function coachHTML(c,r){
  const type=typeOf(c,r), pts=growthPoints(c,r), lp=learningPlan(c,r,pts), cc=careerCoach(c,r), rg=RANGE[r.level];
  const link=t=>{const sl=D.slugs[t];return sl?` <a class="small" href="https://searchjob.co.kr/tech/${sl}/" target="_blank" rel="noopener">공고 보기</a>`:''};
  return `
  <section class="lv-card"><h2>종합 의견</h2><p>${opinion(c,r,type)}</p></section>
  <section class="lv-card"><h2>성장 포인트</h2>
    ${pts.length?`<p class="concl">${pointsConclusion(c,r,pts,cc)}</p><ol class="gp">${pts.map(p=>`<li><div class="gph"><b>${esc(p.title)}</b></div><p class="small">효과 · ${effectTxt(r,p)}</p>
      <p class="small muted">${esc(p.why)}</p><p class="small">예상 기간 · ${esc(p.period)}</p></li>`).join('')}</ol>`
      :(r.level>=6?'<p class="small">가장 높은 레벨입니다. 지금의 강점을 유지하면서, 아래 러닝 플랜으로 지원할 수 있는 포지션의 폭을 넓혀 보세요.</p>':'<p class="small">지금 입력 기준으로는 단기간에 점수를 크게 바꿀 요소가 많지 않습니다. 아래 커리어 코칭의 시간·이동 요소를 참고하세요.</p>')}
    ${(r.P.lic_long||[]).filter(n=>!(c.licNames||[]).includes(n)).length?`<p class="small"><b>장기 과제</b> · ${esc(r.P.lic_long.filter(n=>!(c.licNames||[]).includes(n)).join(', '))} — 따는 데 몇 년이 걸려 단기 성장 포인트에서는 뺐지만, 가산점이 큰 항목입니다.</p>`:''}
    <p class="small muted">효과는 그 항목만 했을 때 요소별 현황이 어떻게 바뀌는지입니다. 학교와 회사는 단기간에 바꾸기 어려워 여기서는 뺐고, 아래 커리어 코칭에서 다룹니다.</p>
  </section>
  ${lp?`<section class="lv-card"><h2>러닝 플랜</h2>
    ${lp.items.length?`${r.items.tech>=10?'<p class="small"><b>기술 일치도는 이미 만점입니다.</b> 아래는 점수보다 지원할 수 있는 포지션의 폭을 넓히기 위한 계획입니다.</p>':''}<p class="small muted">학습만으로는 3단계까지 인정됩니다. 4단계부터는 실무에서 쓴 기간(1년 이상, 5단계는 3년 이상)이 필요해 실무 과제를 함께 계획했습니다.</p>
    <div class="lp">${lp.items.map(i=>`<div class="lpi"><div class="gph"><b>${esc(i.t)}</b><span class="small muted">${esc(i.grp)} · ${i.cur||'미입력'} → <b>${i.target}단계</b>${link(i.t)}</span></div>
      ${[...new Set([r.jobY>=7?i.target:Math.max(3,i.cur+1),i.target].filter(l=>l>i.cur&&l>=3))].sort().map(l=>`<p class="small"><span class="lvb">${l}단계</span> ${esc(METHOD[i.grp][Math.min(5,l)])} <span class="muted">(${HOW_TYPE[Math.min(5,l)]})</span></p>`).join('')}
      <p class="small muted">이력서에 남길 것 · ${esc(EVID[i.grp])}</p></div>`).join('')}</div>
    <h3 class="h3">기간별 로드맵</h3>
    <div class="road">${lp.road.map(s=>`<div class="rs"><div class="rsl"><b>${s.label}</b><span class="small muted">기술 일치도 <span class="lv-dt">${dotTxt(s.r2.items.tech)}</span> · 레벨 ${s.r2.level}</span></div><ul class="small">${s.todo.map(t=>`<li>${esc(t)}</li>`).join('')||'<li>유지</li>'}</ul></div>`).join('')}</div>
    ${lp.road.length&&lp.road[lp.road.length-1].r2.level===r.level&&r.items.tech<10?`<p class="small"><b>학습만으로는 레벨이 바뀌지 않습니다.</b> 기술은 오르지만 레벨을 가르는 것은 다른 요소입니다. 아래 커리어 코칭의 회사 이동 시나리오와 함께 보세요.</p>`:''}
    <p class="small muted">로드맵의 결과는 학습 효과만 반영했습니다. 각 구간이 끝나면 다시 진단해 실제 수준을 확인해 보세요.</p>`
    :'<p class="small">핵심 기술이 모두 기대 수준에 닿아 있습니다. 5단계(기준을 만든다)로 넓혀 가면 상위 포지션에서 강점이 됩니다.</p>'}
  </section>`:''}
  <section class="lv-card"><h2>커리어 코칭</h2>
    ${cc.notes.map(n=>`<p class="small">${n}</p>`).join('')}
    ${seniorNote(r)}
    ${cc.scen.length?`<div><p class="small muted">3년 뒤 모습 (기술·영어는 지금과 같다고 가정)</p>
      <table class="lv-sc"><thead><tr><th>경로</th><th>회사 경력</th><th>평균 근속</th><th>레벨</th></tr></thead><tbody>
      ${cc.scen.map(([lab,x])=>`<tr><td>${esc(lab)}</td><td><span class="lv-dt">${dotTxt(x.items.co)}</span></td><td>${x.tenY!=null?x.tenY.toFixed(1)+'년':'-'}</td><td><b>${x.level}</b> ${LV[x.level][0]}</td></tr>`).join('')}</tbody></table></div>`:''}
  </section>
  <section class="lv-card"><h2>지금 지원하기 좋은 범위</h2>
    <div class="rg"><div><span class="small muted">안정권</span><b>${rg[0]}</b></div><div><span class="small muted">도전권</span><b>${rg[1]}</b></div><div><span class="small muted">준비 후 도전</span><b>${rg[2]}</b></div></div>
    ${(r.totalY||0)>=25?'<p class="small">경력 25년 이상은 공고 지원보다 추천·헤드헌팅으로 자리를 옮기는 경우가 많습니다. 공고와 함께 이 경로도 꼭 활용하세요.</p>':''}
    <p class="small muted">회사 급은 채용시장의 평균적인 평가 기준이며, 직무·포지션에 따라 달라질 수 있습니다. <a href="https://searchjob.co.kr/" target="_blank" rel="noopener">서치잡에서 공고 보기</a></p>
  </section>
`;
}

/* ---------- 결과 ---------- */
const dots=n=>`<span class="dots" aria-label="5점 중 ${n}">${[1,2,3,4,5].map(i=>`<i class="${i<=n?'on':''}"></i>`).join('')}</span>`;
const state=v=>v==null?['n','평가 제외']:v>=8?['g','강점']:v>=6?['n','보통']:['w','보강 여지'];
function render(c,r){
  const box=$('#result'),L=LV[r.level],P=r.P;
  if(r.gate.length){box.innerHTML=`<section class="lv-card"><h2>레벨을 산정하지 않았습니다</h2><p>${esc(c.duty)} 직무는 서치잡 공고의 자격요건 과반에 ${r.gate.join(', ')}${josa(r.gate[r.gate.length-1],'이','가')} 들어 있어 필수 요건으로 봅니다. 등록하시면 레벨이 산정됩니다.</p><div class="actions"><button type="button" id="back">입력 수정</button></div></section>`;$('#back').onclick=showForm;return}
  const owned=r.core.filter(([t])=>effLv(c.skills[t])>=r.exp).length;
  const techRow=['기술 일치도',r.items.tech,P&&P.tech?`${r.sub&&r.sub!=='직무 전체'?esc(r.sub)+' 분야 ':''}핵심 기술 ${r.core.length}개 중 잘하는 ${r.K}개로 평가 · 기대 수준(${r.exp}단계) 이상 ${owned}개`:'이 직무는 기술 일치도를 적용하지 않음'];
  const elem=r.rank==='신입'?[
    ['학교',r.items.school,`${esc(r.edu.label)} · ${esc(r.edu.basis)} 기준`],
    ['실무 경험',r.items.exp,(()=>{const v=c.careers.filter(x=>x.s!=null&&x.e!=null);return v.length?v.map(x=>`${esc(x.name||'이름 없음')}(${esc(CO_SHORT[x.type]||'유형 미입력')}, ${x.emp==='인턴'?'인턴':x.emp==='계약'?'계약직':'정규직'} ${x.e-x.s+1}개월)`).join(' · '):'인턴·실무 경험 없음'})()],
    techRow,
    ['영어·자격',r.items.spec,[c.eng?`영어 ${c.eng}${c.eng==='원어민'?'':'회화'} 수준`:'영어 공인 점수 없음',c.lic?'직무 자격증':'',c.natlic?'국가기술자격':''].filter(Boolean).join(' · ')]]
  :[
    ['학교',r.items.school,`${esc(r.edu.label)} · ${esc(r.edu.basis)} 기준`],
    ['회사 경력',r.items.co,r.items.co==null?'평가 대상 경력 없음':(r.coParts.length>1?`${r.coParts.slice().sort((a,b)=>b.share-a.share).map(p=>`${esc(p.x.name||'이름 없음')}(${esc(CO_SHORT[p.x.type]||p.label)}) ${Math.round(p.share*100)}%`).join(' · ')}${r.coBasis==='현재 회사'?' · 최근 이직한 현재 회사 기준 적용':''}`:`${esc(r.cur?.name||'이름 없음')} · ${esc(r.coLabel)}`)],
    ['평균 근속',r.items.ten,r.tenY!=null?`정규직 평균 ${r.tenY.toFixed(1)}년`:(r.totalY<3?'총 경력 3년 미만이라 평가하지 않음':'정규직 경력 없음')],
    ['기술 일치도',r.items.tech,P&&P.tech?`${r.sub&&r.sub!=='직무 전체'?esc(r.sub)+' 분야 ':''}핵심 기술 ${r.core.length}개 중 잘하는 ${r.K}개로 평가 · 기대 수준(${r.exp}단계) 이상 ${owned}개`:'이 직무는 기술 일치도를 적용하지 않음']];
  const strengths=elem.filter(e=>e[1]!=null&&e[1]>=8).map(e=>e[0]);
  const advTag=r.edu.adv?`<span class="tag">✓ ${r.edu.adv.deg} ${r.edu.adv.st}</span>`:'<span class="tag">석사·박사 없음</span>';
  box.innerHTML=`
  <div id="lvWho" class="lv-who"></div>
  <section class="lv-card">
    <div id="lvChange" hidden></div>
    <div class="levelhead"><div class="lvnum">${r.level}</div>
      <div style="display:flex;flex-direction:column;gap:4px;min-width:0"><div class="lvname">${L[0]}</div>
        <div class="tags"><span class="tag">${esc(c.duty)}</span><span class="tag">${r.rank}${r.rank!=='신입'?` (경력 ${r.rankRange})`:''} 기준</span><span class="tag">직무 연차 ${r.jobY.toFixed(0)}년</span><span class="tag">2026년 기준</span></div></div></div>
    <div><div class="gauge">${[1,2,3,4,5,6].map(i=>`<div class="${i<=r.level?'on':''}"></div>`).join('')}</div>
    <div class="gauge-l"><span>성장</span><span>중소 핵심</span><span>중견 도전</span><span>중견 핵심</span><span>대기업 도전</span><span>대기업 핵심</span></div></div>
    <p>${L[1]}</p>${strengths.length?`<p class="small"><b>강점</b> · ${strengths.join(', ')}</p>`:''}
  </section>
  <section class="lv-card"><h2>요소별 현황</h2>
    <div class="lv-rows">${elem.map(e=>{const s=state(e[1]);return `<div class="er"><b>${e[0]}</b><span>${e[1]==null?'<span class="muted small">-</span>':dots(Math.round(e[1]/2))} <span class="state ${s[0]}">${s[1]}</span></span><span class="note small muted">${e[2]}</span></div>`}).join('')}</div>
    ${r.rank==='신입'?`<div class="bonus"><span class="small"><b>추가 반영 항목</b> · 석사·박사 학위는 있으면 레벨에 더해집니다. 영어·자격은 신입에서 위의 정식 항목으로 봅니다.</span><div class="tags">${advTag}</div></div>`:`<div class="bonus"><span class="small"><b>추가 반영 항목</b> · 석사·박사, 영어, 자격증은 있으면 레벨에 더해집니다(없어도 깎이지 않습니다).</span>
      <div class="tags">${advTag}${c.eng?`<span class="tag">✓ 영어 ${c.eng}${c.eng==='원어민'?'':'회화'} 수준</span>`:'<span class="tag">영어 공인 점수 없음</span>'}${c.lic?'<span class="tag">✓ 직무 자격증</span>':''}${c.natlic?'<span class="tag">✓ 국가기술자격</span>':''}</div></div>`}
  </section>
  ${coachHTML(c,r)}
  <p class="disc"><b>평가 항목이 제한적입니다.</b> 학력·회사·근속·직무 기술 등 정해진 몇 가지 항목만으로 평가하며, 실제 업무 성과·프로젝트 경험·리더십·대인 역량은 반영하지 못합니다. 결과는 참고로만 활용해 주세요.<br>이 레벨은 같은 직무 안에서 평균적인 기준으로 본 시장 가치이며, 연봉이나 특정 회사의 합격 여부를 뜻하지 않습니다. 입력하신 내용이 정확해야 결과도 정확합니다. 결과는 본인만 볼 수 있습니다.</p>

  <section class="lv-card" id="lvMail" hidden></section>
  <div class="actions"><button type="button" id="back">입력 수정</button><button type="button" id="lvPrint">인쇄·PDF로 저장</button></div>`;
  $('#back').onclick=showForm; $('#lvPrint').onclick=()=>window.print();
}
$('#startBtn').addEventListener('click',()=>gateStart());
function showForm(){$('#result').hidden=true;$('#form').hidden=false;$('#ttl').textContent='내 경력 레벨 진단';window.scrollTo(0,0)}
$('#form').addEventListener('submit',e=>{e.preventDefault();
  const c=collect(),err=$('#formErr');
  if(!D.duty[c.duty]){err.textContent='주력 직무를 목록에서 골라 주세요.';err.hidden=false;return}
  const badJob=c.careers.filter(x=>!D.duty[x.job]);
  if(badJob.length){err.textContent='경력의 직무를 목록에서 골라 주세요: '+badJob.map(x=>x.job||'(비어 있음)').join(', ');err.hidden=false;return}
  if(c.careers.some(x=>x.s!=null&&!x.type)){err.textContent='경력의 회사 유형을 골라 주세요.';err.hidden=false;return}
  const unknown=c.edus.filter(x=>x.deg!=='고졸'&&x.school&&!UNIVMAP[x.school]&&!SPECIAL_SCHOOLS.includes(x.school));
  const dErr=dateCheck(c); if(dErr){err.textContent=dErr;err.hidden=false;return}
  if(!c.edus.length){err.textContent='학력을 하나 이상 입력해 주세요.';err.hidden=false;return}
  if(unknown.length){err.textContent=`학교 이름을 목록에서 골라 주세요: ${unknown.map(x=>x.school).join(', ')}`;err.hidden=false;return}
  err.hidden=true; sortEntries(c); const r=evaluate(c);render(c,r);
  $('#form').hidden=true;$('#result').hidden=false;$('#ttl').textContent='레벨 진단 결과';window.scrollTo(0,0);
  afterResult(c,r);
});
/* 날짜 검사: 입력 순서는 자유, 날짜가 맞지 않을 때만 오류 */
function dateCheck(c){
  const F='2019.03처럼 연도 네 자리와 월로 입력해 주세요.';
  const edN=(e,i)=>e.deg==='고졸'?'고등학교':(e.school||`${i+1}번째 학력`)+' '+e.deg;
  for(const [i,e] of c.edus.entries()){
    if(Number.isNaN(e.g)) return `학력 날짜를 알아볼 수 없습니다 (${edN(e,i)}). ${F}`;
    if(e.st!=='재학'&&e.g==null) return `${edN(e,i)}의 ${e.st} 년월을 입력해 주세요.`;
    if(e.st!=='재학'&&e.g>nowM) return `${edN(e,i)}의 ${e.st} 년월(${fmtYM(e.g)})이 오늘 이후입니다. 졸업 예정이면 상태를 '재학'으로 골라 주세요.`;
    if(e.st==='재학'&&e.g!=null&&e.g<nowM) return `${edN(e,i)}${josa(edN(e,i),'은','는')} 재학 중인데 졸업 예정 년월(${fmtYM(e.g)})이 이미 지났습니다.`;
  }
  const R={고졸:0,전문학사:1,학사:1,석사:2,박사:3};
  const done=c.edus.map((e,i)=>({...e,i})).filter(e=>e.g!=null&&e.st!=='재학'&&e.st!=='중퇴');
  for(const a of done)for(const b of done){
    if(R[a.deg]<R[b.deg]&&a.st==='졸업'&&a.g>b.g)
      return `${edN(a,a.i)} 졸업(${fmtYM(a.g)})이 ${edN(b,b.i)} ${b.st}(${fmtYM(b.g)})보다 늦습니다. 날짜를 확인해 주세요.`;
  }
  const crN=(x,i)=>x.name||`${i+1}번째 경력`;
  const cs=c.careers.map((x,i)=>({...x,i})).filter(x=>x.name||x.type||x.s!=null||x.e!=null);
  for(const x of cs){
    if(Number.isNaN(x.s)||Number.isNaN(x.e)) return `경력 날짜를 알아볼 수 없습니다 (${crN(x,x.i)}). ${F}`;
    if(x.s==null) return `${crN(x,x.i)}의 입사 년월을 입력해 주세요.`;
    if(!x.cur&&x.e==null) return `${crN(x,x.i)}의 퇴사 년월을 입력하거나 '재직 중'을 체크해 주세요.`;
    if(x.s>nowM||(!x.cur&&x.e>nowM)) return `${crN(x,x.i)}의 날짜가 오늘 이후입니다.`;
    if(x.s>x.e) return `${crN(x,x.i)}의 입사 년월(${fmtYM(x.s)})이 퇴사 년월(${fmtYM(x.e)})보다 늦습니다.`;
  }
  for(let i=0;i<cs.length;i++)for(let j=i+1;j<cs.length;j++){const a=cs[i],b=cs[j];
    const ov=Math.min(a.e,b.e)-Math.max(a.s,b.s)+1;
    if(ov>=2) return `${crN(a,a.i)}${josa(crN(a,a.i),'과','와')} ${crN(b,b.i)}의 기간이 ${ov}개월 겹칩니다. 이직 때 1개월 겹치는 것까지만 허용합니다. 날짜를 확인해 주세요.`;}
  return null;
}
/* 입력 순서와 상관없이 최근 것이 위로 오게 정렬 */
function sortEntries(c){
  const box=$('#careers');[...box.querySelectorAll('.career[data-id]')].map(el=>({el,v:ym($('#cs'+el.dataset.id).value)??-1})).sort((a,b)=>b.v-a.v).forEach(o=>box.appendChild(o.el));
  const eb=$('#edus');[...eb.querySelectorAll('[data-eid]')].map(el=>({el,v:ym($('#eg'+el.dataset.eid).value)??1e9})).sort((a,b)=>b.v-a.v).forEach(o=>eb.appendChild(o.el));
}
/* ---------- 시작 ---------- */
Promise.all([fetch('/level/duty_data.json').then(r=>r.json()),fetch('/level/univ.json').then(r=>r.json())]).then(([d,u])=>{
  D=d; UNIV=u; UNIVMAP=Object.fromEntries(u.map(([n,k,t])=>[n,{kind:k,tier:t}]));
  $('#schoolList').innerHTML=[...u.map(x=>x[0]),...SPECIAL_SCHOOLS].map(n=>`<option value="${esc(n)}"></option>`).join('');
  $('#tagList').innerHTML=D.alltags.map(t=>`<option value="${esc(t)}"></option>`).join('');
  fillGroups();
  setDuty(D.groups[Object.keys(D.groups)[0]][0]); $('#clearBtn').click(); $('#loading').hidden=true; $('#intro').hidden=false; boot();
  window.__lv={evaluate,collect,nextPaths,snapshot,restore};
}).catch(()=>{$('#loading').textContent='기준 데이터를 불러오지 못했습니다. 새로고침해 주세요.'});

/* ---------- 회원 연결 ---------- */
const NAME_KEY='sj_level_name'; // 결과지에 표시할 이름 — 이 브라우저에만 둠(서버에 저장하지 않음)
let ME=null, lastRunId=null;
function api(url,body){
  const opt=body===undefined?{credentials:'same-origin'}:{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};
  return fetch(url,opt).then(r=>r.json().catch(()=>({})).then(d=>({ok:r.ok,status:r.status,data:d}))).catch(()=>({ok:false,status:0,data:{}}));
}
let nextUrl='/level/?go=1';
const here=()=>nextUrl;
const fmtDate=sec=>{const d=new Date(sec*1000);return `${d.getFullYear()}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getDate()).padStart(2,'0')}`};
function setFlag(){try{localStorage.setItem('sj_member','1')}catch(e){}
  const a=document.getElementById('login-link'); if(a){a.textContent='마이페이지';a.classList.add('in')}} // 머리줄 「로그인」도 바로 「마이페이지」로 (member.js 와 같은 방식)
function boot(){
  const q=new URLSearchParams(location.search);
  const run=q.get('run');
  if(run&&/^\d+$/.test(run)) viewRun(run);
  else if(q.get('go')==='1') gateStart();
}
/* 지난 진단 한 회차의 결과 화면 — 결과 메일의 「레벨 진단 결과 보기」, 마이페이지 기록에서 엽니다.
   저장한 입력 내용으로 결과 화면을 다시 그립니다(다시 저장하지 않음). 로그인이 안 돼 있으면 로그인 후 돌아옵니다. */
async function viewRun(id){
  nextUrl='/level/?run='+id;
  $('#intro').hidden=true;
  const r=await api('/api/level');
  if(!r.ok){showGate('fail');return}
  ME=r.data;
  if(!ME.user){showGate('login');return}
  setFlag();
  if(!ME.consented){location.href='/my/?next='+encodeURIComponent(here());return}
  const x=await api('/api/level/run?id='+id);
  if(!x.ok||!x.data.snap){showGate('norun');return}
  try{restore(x.data.snap)}catch(e){console.error(e);showGate('norun');return}
  openForm.done=true;
  const c=collect(); sortEntries(c); const res=evaluate(c); render(c,res);
  $('#lvGate').hidden=true;$('#form').hidden=true;$('#result').hidden=false;$('#ttl').textContent='레벨 진단 결과';
  renderWho(); lastRunId=x.data.id;
  const ch=$('#lvChange'); if(ch){ch.className='lv-change';ch.innerHTML=`${fmtDate(x.data.at)}에 진단한 결과입니다. 입력을 바꿔 다시 진단하려면 아래 「입력 수정」을 눌러 주세요.`;ch.hidden=false}
  renderMail(); window.scrollTo(0,0);
}
/* 「진단 시작하기」: 로그인 → 사이트 약관 동의 → 레벨 진단 저장 동의 → 입력 화면(지난 입력 채움) */
async function gateStart(){
  $('#startBtn').disabled=true;
  const r=await api('/api/level'); $('#startBtn').disabled=false;
  if(!r.ok){showGate('fail');return}
  ME=r.data;
  if(!ME.user){showGate('login');return}
  setFlag();
  if(!ME.consented){location.href='/my/?next='+encodeURIComponent(here());return}
  if(!ME.levelConsent){showGate('consent');return}
  openForm();
}
function showGate(kind){
  $('#intro').hidden=true;$('#form').hidden=true;$('#result').hidden=true;
  const g=$('#lvGate');g.hidden=false;
  if(kind==='login'){
    g.innerHTML=`<section class="lv-card"><h2>SNS 간편로그인 후 바로 시작할 수 있어요</h2>
      <p>레벨 진단은 서치잡 회원 전용입니다. 카카오·네이버·구글 중 하나로 로그인하시면 이 화면으로 돌아와 바로 진단을 시작합니다.</p>
      <p class="small muted">로그인할 때는 회원번호와 별명만 받고, 성명·전화번호는 받지 않습니다. 진단 결과는 본인 계정에 저장되어 다음에 다시 진단할 때 지난 결과와 비교해 볼 수 있습니다.</p>
      <div class="actions"><a class="lv-btn" href="/my/?next=${encodeURIComponent(here())}">SNS 간편로그인</a><button type="button" id="gateBack">안내로 돌아가기</button></div></section>`;
  }else if(kind==='norun'){
    g.innerHTML=`<section class="lv-card"><h2>이 진단 결과를 찾지 못했습니다</h2><p>기록이 지워졌거나 다른 계정으로 로그인하셨을 수 있습니다. 진단 기록은 마이페이지에서 볼 수 있습니다.</p><div class="actions"><a class="lv-btn" href="/level/?go=1">진단 시작하기</a><a class="lv-btn" href="/my/" style="background:#fff;color:inherit;border:1px solid var(--line,#DDE1DE)">마이페이지</a></div></section>`;
  }else if(kind==='consent'){
    g.innerHTML=`<section class="lv-card"><h2>${esc((ME.user&&ME.user.nickname)||'회원')}님, 시작하기 전에 한 가지만 확인해 주세요</h2>
      <p>진단에 입력하신 학력·경력·기술·자격증·영어와 진단 결과를 회원님 계정에 저장합니다. 다음에 다시 진단할 때 지난 입력을 불러오고 레벨 변화를 보여 드리는 데 씁니다.</p>
      <ul class="il small"><li>본인만 볼 수 있고, 기업 등 외부에 제공하지 않습니다.</li><li>최근 20회까지 보관하며, 마이페이지에서 언제든 지울 수 있습니다. 탈퇴하면 바로 지웁니다.</li><li>성명·전화번호는 받지 않습니다.</li></ul>
      <label class="chk"><input type="checkbox" id="lvAgree"> (필수) 레벨 진단 입력 내용과 결과의 저장·이용에 동의합니다. <a href="/privacy/" target="_blank" rel="noopener">[개인정보처리방침]</a></label>
      <p class="err" id="lvAgreeErr" hidden>동의해 주셔야 진단을 시작할 수 있습니다.</p>
      <div class="actions"><button type="button" class="primary" id="lvAgreeGo">동의하고 시작하기</button><button type="button" id="gateBack">안내로 돌아가기</button></div></section>`;
    $('#lvAgreeGo').onclick=async()=>{if(!$('#lvAgree').checked){$('#lvAgreeErr').hidden=false;return}
      const r=await api('/api/level/consent',{}); if(!r.ok){$('#lvAgreeErr').textContent='저장하지 못했습니다. 잠시 뒤 다시 시도해 주세요.';$('#lvAgreeErr').hidden=false;return}
      ME.levelConsent=true; openForm();};
  }else{
    g.innerHTML=`<section class="lv-card"><h2>지금은 진단을 시작할 수 없습니다</h2><p>로그인 정보를 확인하지 못했습니다. 잠시 뒤 다시 시도해 주세요. 계속 안 되면 화면 오른쪽 아래 「오류 신고」를 눌러 주세요.</p><div class="actions"><button type="button" id="gateBack">안내로 돌아가기</button></div></section>`;
  }
  const b=$('#gateBack'); if(b) b.onclick=()=>{g.hidden=true;$('#intro').hidden=false;window.scrollTo(0,0)};
  window.scrollTo(0,0);
}
function openForm(){
  $('#lvGate').hidden=true;$('#intro').hidden=true;$('#result').hidden=true;$('#form').hidden=false;
  if(ME&&ME.last&&ME.last.snap&&!openForm.done){
    try{restore(ME.last.snap);$('#sampleNote span').textContent=`지난 진단(${fmtDate(ME.last.at)})에 입력하신 내용을 불러왔습니다. 바뀐 부분만 고쳐서 다시 진단해 보세요.`;$('#sampleNote').hidden=false}
    catch(e){console.error(e);$('#clearBtn').click()}
  }
  openForm.done=true; window.scrollTo(0,0);
}
/* 입력 화면을 그대로 다시 채울 수 있게 저장하는 입력 내용(계산용 collect()와 별도) */
function snapshot(){
  return {v:1,duty:$('#duty').value,subs:[...subState],skills:JSON.parse(JSON.stringify(skillState)),lics:{...licState},
    edus:[...document.querySelectorAll('[data-eid]')].map(el=>{const id=el.dataset.eid;return {deg:$('#ed'+id).value,st:$('#es'+id).value,grad:$('#eg'+id).value.trim(),school:$('#en'+id).value.trim(),major:$('#em'+id).value.trim(),oname:$('#eon'+id).value.trim(),orank:$('#eor'+id).value}}),
    careers:[...document.querySelectorAll('.career[data-id]')].map(el=>{const id=el.dataset.id;return {name:$('#cn'+id).value.trim(),type:$('#ct'+id).value,job:$('#cj'+id).value,emp:$('#ce'+id).value,start:$('#cs'+id).value.trim(),end:$('#cf'+id).value.trim(),cur:$('#cc'+id).checked}}),
    engTest:$('#engTest').value,engScore:$('#engScore').value,opic:$('#opic').value,natlic:$('#natlic').checked};
}
function restore(s){
  if(!s||!D.duty[s.duty])return;
  setDuty(s.duty);
  const P=poolOf(s.duty),names=Object.keys(P.subs||{});
  const subs=(s.subs||[]).filter(n=>names.includes(n)).slice(0,2); if(subs.length){subState=subs;renderSubs()}
  skillState=s.skills||{}; renderSkills();
  licState={}; (P.licenses||[]).forEach(n=>{if(s.lics&&s.lics[n])licState[n]=true}); renderLics();
  $('#edus').innerHTML=''; (s.edus&&s.edus.length?s.edus:[{}]).forEach(e=>{addEdu(e);const id=eid;if(e.orank)$('#eor'+id).value=e.orank;$('#en'+id).dispatchEvent(new Event('input'))});
  $('#careers').innerHTML=''; (s.careers&&s.careers.length?s.careers:[{}]).forEach(c=>addCareer({...c,job:D.duty[c.job]?c.job:undefined}));
  $('#engTest').value=s.engTest||''; $('#engTest').dispatchEvent(new Event('change')); $('#engScore').value=s.engScore||''; if(s.opic)$('#opic').value=s.opic;
  $('#natlic').checked=!!s.natlic;
}
/* 결과 메일용 한 줄 요약. 화면의 「1번만 해도 …」는 바로 아래 성장 포인트 목록을 가리키지만
   메일에는 그 목록이 없으므로 「성장 포인트 1번(무엇)만 해도 …」로 풀어 씁니다. */
function mailConcl(){
  const n=document.querySelector('#result .concl'); if(!n) return '';
  const t=n.textContent.trim();
  const titles=[...document.querySelectorAll('#result ol.gp > li .gph b')].map(b=>b.textContent.replace(/\s*\([^)]*\)/g,'').trim());
  if(!/^\d+번/.test(t)) return t;
  return '성장 포인트 '+t.replace(/(\d+)번/g,(m,k)=>titles[k-1]?`${k}번(${titles[k-1]})`:m);
}
/* 진단 직후: 저장 → 지난 레벨 비교, 이름 줄, 이메일 칸 */
async function afterResult(c,r){
  renderWho();
  if(r.gate&&r.gate.length) return; // 레벨 미산정(필수 자격증 미등록) — 저장하지 않음
  const res={duty:c.duty,sub:r.sub||'',rank:r.rank,level:r.level,raw:r.raw,items:r.items,
    concl:mailConcl(),
    strengths:(()=>{const n=[...document.querySelectorAll('#result p.small b')].find(b=>b.textContent==='강점');return n?n.parentNode.textContent.replace(/^강점\s*·\s*/,'').trim():''})()};
  const s=await api('/api/level/save',{snap:snapshot(),result:res});
  const ch=$('#lvChange');
  if(!s.ok){ch.className='lv-change warn';ch.textContent='결과를 저장하지 못했습니다. 화면의 결과는 그대로 보실 수 있습니다.';ch.hidden=false;return}
  lastRunId=s.data.id;
  try{if(lastRunId)history.replaceState(null,'','/level/?run='+lastRunId)}catch(e){} // 새로고침해도 이 결과가 보이게
  if(ME){ME.last={id:s.data.id,at:Math.floor(Date.now()/1000),snap:snapshot()};}
  const p=s.data.prev;
  if(p){const d=r.level-p.level, same=p.duty===c.duty;
    ch.className='lv-change'+(same&&d>0?' up':same&&d<0?' down':'');
    ch.innerHTML=same?`지난 진단(${fmtDate(p.at)}) 레벨 <b>${p.level}</b> → 이번 <b>${r.level}</b> ${d>0?`· ${d}단계 올랐습니다`:d<0?`· ${-d}단계 내려갔습니다`:'· 같습니다'}`
      :`지난 진단(${fmtDate(p.at)})은 ${esc(p.duty)} 직무로 레벨 <b>${p.level}</b>이었습니다. 이번은 ${esc(c.duty)} 직무 기준입니다.`;
    ch.hidden=false;}
  renderMail();
}
function renderWho(){
  const box=$('#lvWho'); if(!box)return;
  let nm=''; try{nm=localStorage.getItem(NAME_KEY)||''}catch(e){}
  const nick=(ME&&ME.user&&ME.user.nickname)||'';
  box.innerHTML=`<p class="lv-whot" id="lvWhoT"></p><label class="lv-f lv-namef">결과지에 표시할 이름 (선택 · 서버에 저장하지 않음)<input type="text" id="lvName" maxlength="20" placeholder="${esc(nick||'예: 홍길동')}" autocomplete="off"></label>`;
  const show=()=>{const v=$('#lvName').value.trim()||nick;$('#lvWhoT').textContent=v?`${v} 님의 레벨 진단`:'레벨 진단 결과'};
  $('#lvName').value=nm; show();
  $('#lvName').addEventListener('input',()=>{show();try{localStorage.setItem(NAME_KEY,$('#lvName').value.trim())}catch(e){}});
}
function renderMail(){
  const box=$('#lvMail'); if(!box||!ME)return;
  box.hidden=false;
  const msg=t=>{const m=$('#lvMailMsg');m.innerHTML=t;m.hidden=false};
  const nameNow=()=>$('#lvName')?$('#lvName').value.trim():'';
  if(!ME.mail){box.innerHTML=`<h2>결과를 이메일로 받기</h2><p class="small muted">준비 중입니다. 곧 열립니다. 그 전까지는 아래 「인쇄·PDF로 저장」으로 결과를 보관하실 수 있습니다.</p>`;return}
  const em=ME.email;
  if(em&&!renderMail.edit){
    box.innerHTML=`<h2>결과를 이메일로 받기</h2><p class="small"><b>${esc(em.addr)}</b> 로 이 결과를 보내 드립니다.</p>
      <div class="actions"><button type="button" class="primary" id="lvSend">이메일로 보내기</button><button type="button" class="link" id="lvMailEdit">주소 바꾸기</button><button type="button" class="link" id="lvMailOff">이메일 지우기</button></div><p class="small" id="lvMailMsg" hidden></p>`;
    $('#lvSend').onclick=async()=>{if(!lastRunId){msg('결과를 저장한 뒤에 보낼 수 있습니다.');return}$('#lvSend').disabled=true;const r=await api('/api/level/send',{id:lastRunId,name:nameNow()});
      msg(r.ok?`${esc(r.data.to)} 로 보냈습니다. 메일함을 확인해 주세요.`:esc(r.data.error||'보내지 못했습니다.'));if(!r.ok)$('#lvSend').disabled=false};
    $('#lvMailEdit').onclick=()=>{renderMail.edit=true;renderMail()};
  }else{
    box.innerHTML=`<h2>결과를 이메일로 받기 <span class="small muted">(선택)</span></h2>
      <p class="small">이메일 주소를 적으시면 이 결과를 바로 보내 드립니다. 주소는 기억해 두었다가 다음 진단부터는 버튼 한 번으로 보내 드립니다.</p>
      <div class="lv-mailrow"><label class="lv-f" style="flex:1 1 220px">이메일<input type="email" id="lvEmail" autocomplete="email" placeholder="name@example.com" value="${esc(em?em.addr:'')}"></label><button type="button" class="primary" id="lvAsk">결과 메일 받기</button>${em?'<button type="button" id="lvEditCancel">취소</button>':''}</div>
      <div class="lv-mailask" id="lvConfirm" hidden><p><b id="lvConfirmAddr"></b> 으로 보낼까요?</p><div class="actions"><button type="button" class="primary" id="lvGo">보내기</button><button type="button" id="lvFix">주소 고치기</button></div></div>
      <p class="small muted">결과 메일만 보내며 광고 메일은 보내지 않습니다. 이메일은 언제든 지울 수 있습니다. <a href="/privacy/" target="_blank" rel="noopener">개인정보처리방침</a></p><p class="small" id="lvMailMsg" hidden></p>`;
    const okMail=v=>/^[^\s@<>"',;]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,24}$/.test(v);
    $('#lvAsk').onclick=()=>{const v=$('#lvEmail').value.trim();$('#lvMailMsg').hidden=true;
      if(!okMail(v)){msg('이메일 주소를 다시 확인해 주세요.');return}
      if(!lastRunId){msg('결과를 저장한 뒤에 보낼 수 있습니다.');return}
      $('#lvConfirmAddr').textContent=v;$('#lvConfirm').hidden=false;$('#lvAsk').disabled=true;$('#lvEmail').readOnly=true;$('#lvGo').focus()};
    $('#lvFix').onclick=()=>{$('#lvConfirm').hidden=true;$('#lvAsk').disabled=false;$('#lvEmail').readOnly=false;$('#lvEmail').focus()};
    $('#lvGo').onclick=async()=>{const v=$('#lvEmail').value.trim();$('#lvGo').disabled=true;$('#lvFix').disabled=true;
      const r=await api('/api/level/email',{email:v,id:lastRunId,name:nameNow()});
      if(r.ok){ME.email={addr:r.data.to};renderMail.edit=false;renderMail();msg(`${esc(r.data.to)} 로 보냈습니다. 메일함을 확인해 주세요.`)}
      else{$('#lvConfirm').hidden=true;$('#lvGo').disabled=false;$('#lvFix').disabled=false;$('#lvAsk').disabled=false;$('#lvEmail').readOnly=false;msg(esc(r.data.error||'보내지 못했습니다.'))}};
  }
  const cx=$('#lvEditCancel'); if(cx) cx.onclick=()=>{renderMail.edit=false;renderMail()};
  const off=$('#lvMailOff'); if(off) off.onclick=async()=>{const r=await api('/api/level/email/remove',{});if(r.ok){ME.email=null;renderMail.edit=false;renderMail()}};
}
/* 결과지 샘플 보기: 「진단 시작하기」 옆 버튼 → 샘플 4장을 화면 위에 띄움. 닫기·바깥 누르기·Esc 로 닫힘 */
(function(){
  const dlg=document.getElementById('lv-sample'), btn=document.getElementById('sampleBtn'); if(!dlg||!btn) return;
  const open=()=>{dlg.hidden=false;dlg.scrollTop=0;document.body.style.overflow='hidden';document.getElementById('sampleClose').focus()};
  const close=()=>{dlg.hidden=true;document.body.style.overflow='';btn.focus()};
  btn.addEventListener('click',open);
  document.getElementById('sampleClose').addEventListener('click',close);
  document.getElementById('sampleStart').addEventListener('click',()=>{close();gateStart()});
  dlg.addEventListener('click',e=>{if(e.target===dlg)close()});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!dlg.hidden)close()});
})();
