/* ===================== ① LANDING ===================== */
let LANG = 'vi';
const I18N_KO = {
  nav_svc:'서비스', nav_proc:'프로세스', nav_cap:'역량', nav_contact:'문의',
  hero_h:'베트남 의류 생산관리와 품질검사', hero_p:'KLMAS는 브랜드를 대신해 공장 선정, 샘플 컨펌, 라인 관리, 검사, 선적까지 RDD에 맞춰 책임집니다.',
  f1:'베트남 사업 시작', f2:'임직원: MR 14, QA/QC 65, 관리 5', f3:'누적 생산관리 수량(장)',
  tr_h:'오더는 지금 어디에 있나요?', tr_p:'케어라벨의 스타일 번호 또는 시즌 관리번호를 입력하세요.', tr_btn:'진행 현황 보기',
  tr_note:'정식 버전: 바이어는 로그인 후 자사 오더만 조회합니다. 데모 데이터: CHALLENGER 26FW, 2026-10-12 기준.',
  svc_h:'시즌 전체를 한 창구에서', svc_p:'원부자재와 디자인은 브랜드가 지급하고, 베트남 현지의 나머지는 KLMAS가 생산관리 서비스 계약으로 맡습니다.',
  s1h:'생산관리', s1p:'공장 선정과 스타일 안분, FPP 샘플부터 선적까지 관리합니다.', s1a:'공임·물량·납기 협상', s1b:'BUYER/KLMAS/공장 3부 자재 매칭 차트', s1c:'일일 생산 리포트',
  s2h:'품질검사', s2p:'KLMAS 오더와 약 50개 외부 업체의 인라인·완제품 검사를 수행합니다.', s2a:'공장·품목별 전담 검사원', s2b:'AQL 샘플링', s2c:'당일 불량 사진·리포트',
  s3h:'검사원 교육', s3p:'신규 검사원 5단계 커리큘럼, 지역별 월 1회 정기교육.', s3a:'브랜드별 품질 판정 기준', s3b:'사이즈 스펙 측정·검사 방법', s3c:'검사원 귀책 통계',
  s4h:'생산 컨설팅', s4p:'베트남에 진출하는 브랜드를 위해 공장 선정, 샘플 준비, RDD 역산 일정을 제안합니다.', s4a:'공장 역량 평가', s4b:'RDD 역산 일정', s4c:'수출 서류·원산지증명',
  proc_h:'오더 의뢰부터 선적까지 10단계', proc_p:'단계마다 계획일과 실적일이 시스템에 기록되며, 바이어는 스타일별 현재 단계를 볼 수 있습니다.',
  cap_h:'베트남 북부와 남부 모두에', cap_p:'협력 공장 약 10곳. 2022년 품목 비율: 자켓·코트 25%, 티셔츠·셔츠 30%, 팬츠·스커트 30%, 액세서리 15%.',
  c1:'해외사업, 검사, 한국내수사업, 데이터 분석.', c2:'관리, 회계, 문서, 인사.', c3:'협력 공장 클러스터와 현장 검사.', br_h:'생산관리 및 검사 브랜드',
  ct_h:'새 시즌을 시작하세요', ct_p:'시즌 스타일 리스트나 미니맵을 보내주세요. 컨설팅 흐름에 등록되고 영업일 내 MR이 연락드립니다.',
  l1:'브랜드', l2:'주요 품목', l3:'시즌 예상 수량', l4:'메모', l5:'컨설팅 요청 보내기', ai_btn:'KLMAS 어시스턴트', ai_title:'KLMAS 어시스턴트'
};
const I18N_VI = {};
$$('[data-i18n]').forEach(el => I18N_VI[el.dataset.i18n] = el.textContent);
const t = k => (LANG === 'ko' ? I18N_KO : I18N_VI)[k] || I18N_VI[k] || k;
function setLang(l) {
  LANG = l; document.documentElement.lang = l;
  $$('[data-i18n]').forEach(el => el.textContent = t(el.dataset.i18n));
  $$('.lang button').forEach(b => b.setAttribute('aria-pressed', b.dataset.lang === l));
  renderProcess();
  $('#chatIn').placeholder = l === 'ko' ? '서비스 문의 또는 스타일 번호 입력…' : 'Hỏi về dịch vụ hoặc nhập mã style…';
  if ($('#trackResult').classList.contains('on')) doTrack($('#trackIn').value, false);
}
$$('.lang button').forEach(b => b.addEventListener('click', () => setLang(b.dataset.lang)));

const PROCESS = [
  ['Tiếp nhận đơn','Chốt minimap, danh sách đơn, chi tiết từng style','오더 의뢰','스타일별 미니맵·오더리스트 확정'],
  ['Đàm phán','Giá gia công, số lượng, ngày giao','협상','공임·물량·납기 협상'],
  ['Chọn nhà máy','Phân style theo nhà máy và mặt hàng','공장 선정','공장·아이템별 스타일 안분'],
  ['Mẫu fit, pre-approval','Chốt thông số và size, kiểm chất liệu','FIT·PRE APPROVAL','사양·사이즈 확정, 소재 체크'],
  ['Mẫu FPP','Nhà máy may mẫu tiền sản xuất; KLMAS dịch tài liệu kỹ thuật','FPP 샘플','공장 프리프로덕션 견본, 작업지시서 번역'],
  ['Matching chart','Bảng đối chiếu vật tư 3 bên: buyer, KLMAS, nhà máy','자재 매칭 차트','BUYER/KLMAS/공장 3부'],
  ['Duyệt FPP','Duyệt bulk matching, kiểm tra cuối rồi vào chuyền','FPP 컨펌','벌크 매칭 컨펌 후 본작업'],
  ['Inline & wash test','Mẫu đầu chuyền gửi buyer, thử giặt','인라인·워싱 테스트','라인 초두 샘플 발송'],
  ['Mẫu shipping & kiểm cuối','Kiểm thành phẩm, đóng dấu kiểm','선적 샘플·최종 검사','최종 검사 도장 날인'],
  ['Đóng gói & xuất hàng','Kiểm thùng, gửi chứng từ và C/O đúng hạn','포장·선적','선적 서류·원산지증명 발송']
];
function renderProcess() {
  $('#procList').innerHTML = PROCESS.map(p => `<li><b>${esc(LANG === 'ko' ? p[2] : p[0])}</b>${esc(LANG === 'ko' ? p[3] : p[1])}</li>`).join('');
}
$('#brands').innerHTML = ['CHALLENGER','Mizuno','PXG','Cleveland Golf','Volvik','Black Yak','Nepa','Renoma','Crocodile','Xexymix','8seconds','Beanpole','Khalhon','FootJoy','FILA','Kuho Plus','Rogatis','Kotelo','Beaker']
  .map(b => `<span>${esc(b)}</span>`).join('');

/* ---- order tracking (buyer view) ---- */
const DEMO = [['CHF3MWT6306','Đã xuất'],['CHF4WHP6852','Đang kiểm'],['CHF4MPT6444','Trễ'],['26FW-O20','Số đơn']];
$('#demoChips').innerHTML = DEMO.map(([c]) => `<button type="button" class="chip" data-c="${c}">${c}</button>`).join('');
$('#demoChips').addEventListener('click', e => { const b = e.target.closest('.chip'); if (b) { $('#trackIn').value = b.dataset.c; doTrack(b.dataset.c); } });
$('#trackForm').addEventListener('submit', e => { e.preventDefault(); doTrack($('#trackIn').value); });

function findOrder(q) {
  q = (q || '').trim().toUpperCase().replace(/\s+/g, '');
  if (!q) return null;
  let s = ALL.find(x => x.s === q);
  if (s) return s;
  const m = q.match(/^(?:(\d{2}(?:FW|SS))[-_]?)?([A-Z]{1,2}\d{1,3})$/);
  if (m) return ALL.find(x => x.no === m[2] && (!m[1] || x.season === m[1])) || null;
  return null;
}
const mdToDm = raw => { const m = String(raw).match(/(\d{1,2})\/(\d{1,2})/); return m ? `${m[2].padStart(2,'0')}/${m[1].padStart(2,'0')}` : ''; };
function doTrack(q, scroll = true) {
  const box = $('#trackResult'), s = findOrder(q), ko = LANG === 'ko';
  box.classList.add('on');
  if (!s) {
    box.innerHTML = `<div class="tr-card"><b>${ko ? '조회 결과가 없습니다.' : 'Không tìm thấy đơn này.'}</b>
      <p class="muted">${ko ? '스타일 번호(예: CHF3MWT6306) 또는 시즌-관리번호(예: 26FW-F9)로 다시 입력하세요.' : 'Kiểm tra lại mã style (VD CHF3MWT6306) hoặc số đơn theo mùa (VD 26FW-F9).'}</p></div>`;
  } else if (s.season === '27SS') {
    box.innerHTML = `<div class="tr-card"><div class="tr-head"><div><h3>${esc(s.s)}</h3><div class="desc">${esc(ko && s.kr ? s.kr : s.it)} · 27SS · ${esc(s.no)}</div></div>
      <span class="pill ${s.cancelled ? 'bad' : 'warn'}">${s.cancelled ? (ko ? '취소' : 'Đã hủy') : (ko ? '샘플 진행 중' : 'Đang làm mẫu')}</span></div>
      <div class="tr-grid"><div class="meter"><div class="k">${ko ? '오더 수량' : 'Số lượng đặt'}</div><div class="v num">${fmt(s.q)}</div></div>
      <div class="meter"><div class="k">ETD VN</div><div class="v">${ddy(s.etdD)}</div></div>
      <div class="meter"><div class="k">${ko ? '공장' : 'Nhà máy'}</div><div class="v" style="font-size:18px">${esc(s.factory || (ko ? '미정' : 'Chưa chốt'))}</div></div></div></div>`;
  } else {
    const r = styleStatus(s);
    const stages = r.st.map((x, i) => `<div class="stage ${x.done ? 'done' : ''} ${i === r.now ? 'now' : ''}"><b>${esc(ko ? x.ko : x.vi)}</b><span>${x.date ? dd(x.date) : (x.raw && !x.date ? esc(mdToDm(x.raw)) : '')}</span></div>`).join('');
    const m = (k, v, b) => `<div class="meter"><div class="k">${k}</div><div class="v num">${fmt(v)}</div><div class="bar"><i style="width:${Math.min(100, 100 * v / s.q)}%"></i></div><div class="k">${pct(v, s.q)}</div></div>`;
    const ships = s.ships.length ? s.ships.map(x => `<tr><td>${dd(x.etd)} → ${dd(x.eta)}</td><td>${x.mode}${x.planned ? (ko ? ' · 예정' : ' · kế hoạch') : ''}</td><td class="r num">${fmt(x.qty)}</td></tr>`).join('')
      : `<tr><td colspan="3" class="muted">${ko ? '선적 내역 없음' : 'Chưa có lô xuất'}</td></tr>`;
    const colors = s.colors.map(([c, n]) => `<tr><td>${esc(c)}</td><td class="r num">${fmt(n)}</td></tr>`).join('') || `<tr><td class="muted">–</td><td></td></tr>`;
    const projTxt = r.proj ? (ko
      ? `예상 완료 ${dd(r.proj.finish)}, 출고 가능 ${dd(r.proj.ready)} (일 생산 ${r.proj.rate}장${r.proj.assumed ? ' 가정' : ''})`
      : `Dự kiến may xong ${dd(r.proj.finish)}, sẵn sàng xuất ${dd(r.proj.ready)} (năng suất ${r.proj.rate} sp/ngày${r.proj.assumed ? ', giả định' : ''})`) : '';
    box.innerHTML = `<div class="tr-card">
      <div class="tr-head"><div><h3>${esc(s.s)}</h3><div class="desc">${esc(ko && s.kr ? s.kr : s.it)} · ${esc(s.t)} · ${esc(s.no)}</div></div>
        <div style="text-align:right"><span class="pill ${r.tone}">${esc(ko ? ({good:'정상', warn:'생산 중', bad:'지연 위험'})[r.tone] : r.label)}</span>
        <div class="muted" style="font-size:13px;margin-top:6px">ETD VN ${ddy(s.etdD)} · RDD ${ddy(s.rddD)} · ${ko ? '공장' : 'Nhà máy'} ${esc(s.factory)}</div></div></div>
      <div class="stages">${stages}</div>
      ${projTxt ? `<p style="margin:6px 0 0;font-size:14px">${esc(projTxt)}</p>` : ''}
      <div class="tr-grid">${m(ko ? '오더' : 'Số lượng đặt', s.q)}${m(ko ? '생산(OUTPUT)' : 'Đã may (output)', s.out)}${m(ko ? '검사' : 'Đã kiểm', s.ins)}${m(ko ? '선적' : 'Đã xuất', s.shp)}</div>
      <div class="tr-cols">
        <div><h3 style="font-size:15px;margin-bottom:6px">${ko ? '선적 차수' : 'Các lô xuất'}</h3><table class="t"><thead><tr><th>ETD → ETA</th><th>${ko ? '운송' : 'Phương thức'}</th><th class="r">${ko ? '수량' : 'SL'}</th></tr></thead><tbody>${ships}</tbody></table></div>
        <div><h3 style="font-size:15px;margin-bottom:6px">${ko ? '컬러별 오더' : 'Theo màu'}</h3><table class="t"><thead><tr><th>${ko ? '컬러' : 'Màu'}</th><th class="r">${ko ? '수량' : 'SL'}</th></tr></thead><tbody>${colors}</tbody></table>
        <p class="muted" style="font-size:12px">${ko ? '샘플 발송' : 'Mẫu đã gửi'}: ${fmt(s.sm)} pcs</p></div>
      </div></div>`;
  }
  if (scroll) box.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
}

/* ---- lead form -> consulting pipeline ---- */
const LEADS = [];
$('#leadForm').addEventListener('submit', e => {
  e.preventDefault();
  const f = new FormData(e.target);
  LEADS.push({ id: 'L' + (100 + LEADS.length), brand: f.get('brand'), item: f.get('item'), qty: +f.get('qty') || 0, note: f.get('note'), stage: 0, owner: 'Chưa phân', src: 'Website', created: TODAY });
  e.target.reset();
  toast(LANG === 'ko' ? '요청이 접수되었습니다. (③ 컨설팅 흐름에서 확인)' : 'Đã gửi. Xem thẻ mới ở ③ › Luồng tư vấn.');
});

/* ===================== AI assistant ===================== */
/* Prototype: retrieval over a curated knowledge base + order-status tool.
   Production: Claude API with tools [search_kb, get_order_status, create_ticket]; answers about a buyer's
   own orders require login; anything outside the KB becomes a ticket that an MR approves (meeting item #14). */
const KB = [
  { k:'dịch vụ service 서비스 làm gì 무엇 business', vi:'KLMAS có 4 mảng: (1) quản lý sản xuất cho thương hiệu, (2) kiểm hàng QC inline và thành phẩm, cả cho bên thứ ba, (3) đào tạo kiểm hàng viên, (4) tư vấn sản xuất tại Việt Nam.', ko:'KLMAS는 (1) 브랜드 생산관리, (2) 인라인·완제품 품질검사(3자 검사 포함), (3) 검사원 교육, (4) 베트남 생산 컨설팅을 제공합니다.', src:'Hồ sơ năng lực, tr. 5' },
  { k:'nhà máy factory 공장 riêng own xưởng', vi:'KLMAS không có nhà máy riêng. Chúng tôi làm việc với khoảng 10 nhà máy đối tác ở miền Bắc, chọn xưởng theo mặt hàng và lịch giao.', ko:'KLMAS는 자체 공장이 없으며 북부 지역 약 10개 협력 공장과 일합니다. 품목과 납기에 맞춰 공장을 선정합니다.', src:'Biên bản họp KOPS 15/10' },
  { k:'nguyên phụ liệu vải material 원단 부자재 npl cấp', vi:'Nguyên phụ liệu do thương hiệu cấp. KLMAS theo dõi ngày về, tính định mức × số lượng để phát hiện thiếu trước khi vào chuyền.', ko:'원부자재는 브랜드가 지급합니다. KLMAS는 입고일을 관리하고 요척×수량으로 과부족을 생산 전에 확인합니다.', src:'Biên bản họp KOPS 15/10' },
  { k:'etd rdd ngày giao lead time 납기 입고 bao lâu', vi:'Với đường biển sang Hàn: tàu khoảng 7 ngày + nhập kho 5 ngày, nên ETD Việt Nam thường sớm hơn RDD 12 ngày.', ko:'해상 기준 선박 약 7일 + 창고 입고 5일로, ETD(베트남 출항)는 RDD보다 약 12일 앞섭니다.', src:'Biên bản họp KOPS 15/10' },
  { k:'mẫu sample fpp inline top 샘플 ref shipping', vi:'Các bước mẫu: REF (mẫu tham khảo) → FPP (mẫu duyệt trước sản xuất, chuẩn cho hàng bulk) → INLINE (đầu chuyền) → PHOTO → TOP → WASH → SHIPPING (mẫu cuối trước khi kiểm và xuất).', ko:'샘플 단계: REF → FPP(양산 기준 최종 승인) → INLINE(라인 초두) → PHOTO → TOP → WASH → SHIPPING(선적 전 최종).', src:'Biên bản họp KOPS 15/10' },
  { k:'quy trình process 프로세스 bước step', vi:'Quy trình 10 bước: tiếp nhận đơn → đàm phán → chọn nhà máy → mẫu fit → FPP → matching chart → duyệt FPP → inline & wash test → mẫu shipping & kiểm cuối → đóng gói, chứng từ, C/O.', ko:'10단계: 오더 의뢰 → 협상 → 공장 선정 → FIT → FPP → 매칭 차트 → FPP 컨펌 → 인라인·워싱 → 선적 샘플·최종 검사 → 포장·서류·원산지증명.', src:'Hồ sơ năng lực, tr. 8' },
  { k:'kiểm hàng qc inspection 검사 aql lỗi defect', vi:'Kiểm hàng gồm kiểm inline tại chuyền và kiểm thành phẩm lấy mẫu theo AQL (thường 2.5 lỗi nặng / 4.0 lỗi nhẹ, mức kiểm II). Mỗi nhà máy/mặt hàng có kiểm viên chuyên trách; báo cáo có ảnh lỗi gửi trong ngày.', ko:'인라인 검사와 AQL 기준 완제품 검사(통상 Major 2.5 / Minor 4.0, 일반검사수준 II)를 수행합니다. 공장·품목별 전담 검사원이 배정되고 불량 사진이 포함된 리포트를 당일 공유합니다.', src:'Hồ sơ năng lực, tr. 11–14' },
  { k:'bên thứ ba third party 3자 thương hiệu khác', vi:'Có. Ngoài đơn do KLMAS quản lý, chúng tôi kiểm hàng bên thứ ba cho khoảng 50 đối tác, ví dụ FILA, Discovery.', ko:'네. KLMAS 오더 외에 FILA, Discovery 등 약 50개 업체의 3자 검사를 합니다.', src:'Biên bản họp KOPS 15/10' },
  { k:'văn phòng địa chỉ office 사무소 ở đâu where location', vi:'Văn phòng tại Hà Nội (hải ngoại, kiểm hàng, dữ liệu) và TP.HCM (quản lý, kế toán, nhân sự); cụm nhà máy đối tác tại Thanh Hóa.', ko:'하노이(해외사업·검사·데이터)와 호치민(관리·회계·인사)에 사무소가 있고, 탱화에 협력 공장 클러스터가 있습니다.', src:'Hồ sơ năng lực, tr. 4–6' },
  { k:'nhân sự staff 직원 bao nhiêu người', vi:'Khoảng 84 nhân sự: 14 MR (quản lý sản xuất), 65 QA/QC, 5 quản lý.', ko:'약 84명: MR 14명, QA/QC 65명, 관리 5명.', src:'Hồ sơ năng lực, tr. 4–6' },
  { k:'theo dõi tra cứu track đơn order status 조회 현황', vi:'Nhập mã style trên nhãn (VD CHF3MWT6306) hoặc số đơn theo mùa (VD 26FW-F9), tôi sẽ tra tiến độ. Ở bản chính thức, buyer cần đăng nhập.', ko:'스타일 번호(예: CHF3MWT6306) 또는 관리번호(예: 26FW-F9)를 입력하시면 진행 현황을 알려드립니다. 정식 버전은 로그인이 필요합니다.', src:'KOPS' },
  { k:'giá price cost 가격 báo giá phí', vi:'Giá phụ thuộc mặt hàng, số lượng và nhà máy, nên tôi không báo giá tự động. Tôi đã tạo yêu cầu để MR liên hệ bạn.', ko:'가격은 품목·수량·공장에 따라 달라 자동 안내가 어렵습니다. 담당 MR이 연락드리도록 요청을 등록했습니다.', src:'Chuyển MR', ticket:true }
];
function kbAnswer(text) {
  const words = text.toLowerCase().normalize('NFC').split(/[^\p{L}\p{N}]+/u).filter(w => w.length > 1);
  let best = null, score = 0;
  for (const e of KB) { const ks = e.k.split(' '); const sc = words.reduce((a, w) => a + (ks.some(k => k.includes(w) || w.includes(k)) ? 1 : 0), 0); if (sc > score) { score = sc; best = e; } }
  return score > 0 ? best : null;
}
function orderAnswer(s, ko) {
  if (s.season === '27SS') return ko ? `${s.s} (27SS ${s.no}): 샘플 진행 중, 오더 ${fmt(s.q)}장, ETD ${ddy(s.etdD)}.` : `${s.s} (27SS ${s.no}): đang làm mẫu, ${fmt(s.q)} sp, ETD ${ddy(s.etdD)}.`;
  const r = styleStatus(s), cur = r.now >= 0 ? r.st[r.now] : null;
  return ko
    ? `${s.s} ${s.kr || s.it}\n현재 단계: ${cur ? cur.ko : '완료'}\n오더 ${fmt(s.q)} / 생산 ${fmt(s.out)} / 검사 ${fmt(s.ins)} / 선적 ${fmt(s.shp)}\nETD ${ddy(s.etdD)}, RDD ${ddy(s.rddD)}`
    : `${s.s} ${s.it}\nBước hiện tại: ${cur ? cur.vi : 'hoàn tất'} (${r.label.toLowerCase()})\nĐặt ${fmt(s.q)} · may ${fmt(s.out)} · kiểm ${fmt(s.ins)} · xuất ${fmt(s.shp)}\nETD ${ddy(s.etdD)}, RDD ${ddy(s.rddD)}`;
}
function botReply(text) {
  const ko = /[가-힣]/.test(text) || LANG === 'ko';
  const code = (text.toUpperCase().match(/CH[A-Z]{1,2}\d[MWU][A-Z]{2}\d{4}/) || text.toUpperCase().match(/\b\d{2}(?:FW|SS)[-_ ]?[A-Z]{1,2}\d{1,3}\b/) || [])[0];
  if (code) {
    const s = findOrder(code.replace(' ', '-'));
    if (s) return { tool: `get_order_status("${s.s}")`, text: orderAnswer(s, ko), src: ko ? '출처: KOPS 생산 현황 2026-10-12' : 'Nguồn: dữ liệu sản xuất KOPS 12/10/2026' };
    return { tool: `get_order_status("${code}")`, text: ko ? '해당 번호의 오더를 찾을 수 없습니다.' : 'Không tìm thấy đơn với mã này.' };
  }
  const e = kbAnswer(text);
  if (e) return { text: ko ? e.ko : e.vi, src: (ko ? '출처: ' : 'Nguồn: ') + e.src, ticket: e.ticket };
  return { tool: 'create_ticket()', ticket: true, text: ko ? '정확한 답변을 위해 담당 MR에게 전달했습니다. 영업일 내 회신드립니다.' : 'Câu này cần MR trả lời chính xác. Tôi đã chuyển cho MR, bạn sẽ nhận phản hồi trong ngày làm việc.' };
}
function addMsg(who, text, extra = {}) {
  const el = document.createElement('div');
  el.className = 'msg ' + who;
  el.innerHTML = (extra.tool ? `<span class="tool">⚙ ${esc(extra.tool)}</span>` : '') + esc(text) + (extra.src ? `<span class="src">${esc(extra.src)}</span>` : '');
  $('#msgs').appendChild(el); $('#msgs').scrollTop = 1e6;
}
const SUGG = { vi: ['KLMAS làm những dịch vụ gì?', 'ETD và RDD cách nhau bao lâu?', 'Tình trạng CHF4MPT6444', 'Có kiểm hàng cho thương hiệu khác không?'],
  ko: ['어떤 서비스를 제공하나요?', 'ETD와 RDD 차이는?', 'CHF3MWT6306 현황', '견적을 받고 싶어요'] };
function openChat() {
  const c = $('#chat'); c.classList.add('on'); $('#fab').setAttribute('aria-expanded', 'true');
  if (!$('#msgs').children.length) addMsg('bot', LANG === 'ko' ? '안녕하세요, KLMAS 어시스턴트입니다. 서비스 문의나 스타일 번호로 오더 현황을 물어보세요.' : 'Xin chào, tôi là trợ lý KLMAS. Bạn có thể hỏi về dịch vụ hoặc nhập mã style để xem tiến độ đơn.');
  $('#suggest').innerHTML = SUGG[LANG].map(s => `<button type="button" class="chip">${esc(s)}</button>`).join('');
  $('#chatIn').focus();
}
$('#fab').addEventListener('click', () => $('#chat').classList.contains('on') ? ($('#chat').classList.remove('on'), $('#fab').setAttribute('aria-expanded', 'false')) : openChat());
$('#chatX').addEventListener('click', () => { $('#chat').classList.remove('on'); $('#fab').setAttribute('aria-expanded', 'false'); });
$('#suggest').addEventListener('click', e => { const b = e.target.closest('.chip'); if (b) ask(b.textContent); });
$('#chatForm').addEventListener('submit', e => { e.preventDefault(); const v = $('#chatIn').value.trim(); if (v) { ask(v); $('#chatIn').value = ''; } });
const TICKETS = [];
function ask(q) {
  addMsg('me', q);
  setTimeout(() => { const r = botReply(q); if (r.ticket) TICKETS.push({ q, at: new Date() }); addMsg('bot', r.text, r); }, 350);
}
renderProcess();
