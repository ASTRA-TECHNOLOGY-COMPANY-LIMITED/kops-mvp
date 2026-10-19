/* ===================== ③ CONSULTING & QC ===================== */
const RQ = rng(1013);
const QC_BRANDS = [
  { name:'CHALLENGER', ext:false, docs:['Inspection report (mẫu KLMAS)','Ảnh: mặt trước/sau, nhãn chăm sóc, tag, dò kim','Packing list','Bảng đo thông số'] },
  { name:'FILA', ext:true, docs:['FILA QA final report','Bảng đo thông số 3 size','Ảnh lỗi + carton','Giấy dò kim'] },
  { name:'Discovery', ext:true, docs:['Final inspection form (Discovery)','Ảnh carton marking','Bảng đo thông số'] },
  { name:'Beanpole', ext:true, docs:['Beanpole QC sheet','Ảnh nhãn & tag','Giấy dò kim'] },
  { name:'FootJoy', ext:true, docs:['FJ AQL report','Ảnh logo/thêu','Bảng đo thông số'] },
  { name:'Kuho Plus', ext:true, docs:['Báo cáo kiểm (mẫu KLMAS)','Ảnh lỗi'] }
].map(b => ({ ...b, lots: b.ext ? 20 + Math.round(RQ() * 60) : 0, fail: +(1 + RQ() * 6).toFixed(1) }));

const DEFECTS = [
  ['A01','Bỏ mũi / đứt chỉ','Major'],['A02','Nhăn đường may','Minor'],['A03','Bẩn, vết dầu','Major'],['A04','Lỗi vải (sợi, lỗ)','Major'],
  ['A05','Khác màu / lệch shade','Major'],['A06','Hở đường may','Major'],['A07','Chỉ thừa chưa cắt','Minor'],['A08','Lỗi in / thêu / ép logo','Major'],
  ['A09','Sai thông số ngoài dung sai','Major'],['A10','Lỗi khóa, cúc, phụ liệu','Major'],['A11','Kim loại sót (dò kim)','Critical'],['A12','Sai nhãn / tag','Minor']
];
const AQL_LETTER = [[8,2],[15,3],[25,5],[50,8],[90,13],[150,20],[280,32],[500,50],[1200,80],[3200,125],[10000,200],[35000,315],[1e9,500]];
const AC25 = {2:0,3:0,5:0,8:0,13:1,20:1,32:2,50:3,80:5,125:7,200:10,315:14,500:21};
const AC40 = {2:0,3:0,5:0,8:1,13:1,20:2,32:3,50:5,80:7,125:10,200:14,315:21,500:21};
const aql = lot => { const n = (AQL_LETTER.find(([max]) => lot <= max) || [0, 500])[1]; return { n, maj: AC25[n], min: AC40[n] }; };

/* ---------------- inspectors & tomorrow's requests ---------------- */
const INSPECTORS = [
  ['Nguyễn Thị Hằng','Thanh Hóa',['PT','SK','HP'],'TAN BINH MINH'],['Lê Văn Tú','Thanh Hóa',['PT','JK'],null],['Phạm Thu Trang','Hà Nội',['LT','WT','ST'],'DONG MY'],
  ['Trần Minh Đức','Hà Nội',['LT','WT'],null],['Đỗ Thị Lan','Nam Định',['JK','VT'],'TRUONG PHUC'],['Vũ Quốc Huy','Nam Định',['JK','VT','WT'],'NATEXCO'],
  ['Bùi Thị Mai','Thái Bình',['JK','WT'],'MTT'],['Hoàng Văn Nam','Hải Dương',['VT','WT','LT'],'HA HIEU'],['Ngô Thị Thảo','Hưng Yên',['JK','PT'],null],
  ['Đinh Văn Long','Bắc Giang',['JK','PT','LT'],'FG BAC GIANG'],['Mai Thị Hoa','Hà Nam',['ST','LT','PT'],null],['Trịnh Văn Khoa','Hà Nội',['JK','PT','WT'],null]
].map(([name, region, spec, ded], i) => ({ id: 'I' + (i + 1), name, region, spec, ded }));
const EXT_FACT = [['Hưng Yên Garment 2','Hưng Yên'],['Nam Định Knit','Nam Định'],['Hà Nam Apparel','Hà Nam'],['Thái Bình Fashion','Thái Bình'],['Bắc Giang Sport','Bắc Giang']];
const REQUESTS = (() => {
  const own = FW.filter(s => s.out > s.ins + 20 || (s.ins < s.q * 0.98 && s.out > 0)).slice(0, 10).map(s => ({
    id: 'R-' + s.no, brand: 'CHALLENGER', ext: false, style: s.s, item: s.item2, factory: s.factory, region: (FACTORY_INFO[s.factory] || {}).region || '?', lot: Math.max(50, s.out - s.ins || s.q), type: 'Kiểm cuối' }));
  const ext = [];
  for (let i = 0; i < 14; i++) {
    const b = QC_BRANDS[1 + Math.floor(RQ() * 5)], [f, region] = EXT_FACT[Math.floor(RQ() * EXT_FACT.length)];
    const item = ['JK','PT','LT','WT','ST','SK'][Math.floor(RQ() * 6)];
    ext.push({ id: 'X-' + (301 + i), brand: b.name, ext: true, style: `${b.name.slice(0, 3).toUpperCase()}-${item}${400 + Math.floor(RQ() * 500)}`, item, factory: f, region, lot: 300 + Math.round(RQ() * 2700), type: RQ() > .7 ? 'Kiểm inline' : 'Kiểm cuối' });
  }
  return [...own, ...ext];
})();
let ASSIGN = null;
function autoAssign() {
  const load = Object.fromEntries(INSPECTORS.map(i => [i.id, []]));
  const out = {};
  [...REQUESTS].sort((a, b) => b.lot - a.lot).forEach(r => {
    let best = null;
    for (const ins of INSPECTORS) {
      const jobs = load[ins.id], sameFactory = jobs.some(j => j.factory === r.factory);
      if (jobs.length >= 3 || (jobs.length >= 2 && !sameFactory)) continue;
      let sc = 0; const why = [];
      if (ins.ded && ins.ded === r.factory) { sc += 5; why.push('kiểm viên chuyên trách nhà máy'); }
      if (ins.region === r.region) { sc += 3; why.push('cùng khu vực'); }
      if (ins.spec.includes(r.item)) { sc += 2; why.push('đúng mặt hàng ' + r.item); }
      if (sameFactory) { sc += 2; why.push('ghép chuyến cùng nhà máy'); }
      sc -= jobs.length * 1.5;
      if (!best || sc > best.sc) best = { ins, sc, why };
    }
    if (best) { load[best.ins.id].push(r); out[r.id] = best; } else out[r.id] = null;
  });
  return out;
}

/* ---------------- consulting pipeline ---------------- */
const STAGES = ['Tiếp nhận','Phân tích minimap','Báo giá & đàm phán','Chọn nhà máy','Mẫu REF / FPP','Ký hợp đồng','Bàn giao sản xuất'];
const DEALS = [
  { id:'L001', brand:'Thương hiệu golf nữ A (KR)', item:'SK', qty:18000, stage:1, owner:'Lee Min Ji', src:'Email', hot:true },
  { id:'L002', brand:'Outdoor B (KR)', item:'JK', qty:42000, stage:2, owner:'Kim Dae Woo', src:'Giới thiệu' },
  { id:'L003', brand:'Athleisure C (KR)', item:'LT', qty:25000, stage:3, owner:'Lee Min Ji', src:'Website', hot:true },
  { id:'L004', brand:'Golf D (KR)', item:'PT', qty:15000, stage:4, owner:'Nguyệt', src:'Hội chợ' },
  { id:'L005', brand:'Kids E (KR)', item:'WT', qty:9000, stage:0, owner:'Chưa phân', src:'Website' },
  { id:'L006', brand:'CHALLENGER 27FW', item:'JK', qty:60000, stage:5, owner:'Lee Min Ji', src:'Khách cũ' },
  { id:'L007', brand:'Unisex F (KR)', item:'ST', qty:12000, stage:6, owner:'Kim Dae Woo', src:'Giới thiệu' }
];
const CHECK = [
  ['Ghi nhận yêu cầu, mặt hàng, số lượng, RDD','Hẹn họp giới thiệu'],
  ['Upload minimap / order list','AI tách style, màu, số lượng → bản nháp master style','MR rà soát các dòng AI không chắc'],
  ['Thu giá gia công (CMPH) từ 2–3 nhà máy','Đàm phán giá, MOQ, ngày giao'],
  ['Xem gợi ý nhà máy theo năng lực & lịch','Chốt nhà máy, ghi lý do'],
  ['REF sample về Hà Nội','FPP gửi Hàn Quốc','Nhận comment, chốt FPP'],
  ['Hợp đồng sản xuất thương hiệu ↔ nhà máy','Hợp đồng dịch vụ KLMAS ↔ thương hiệu'],
  ['Tạo đơn trong KOPS, lịch ngược từ RDD','Bàn giao MR phụ trách và QA nhà máy']
];
function recommendFactories(item) {
  const by = groupBy(FW.filter(s => s.item2 === item), s => s.factory);
  return Object.entries(by).map(([f, a]) => {
    const dl = a.map(shipDelay).filter(x => x != null), ok = dl.length ? dl.filter(x => x <= 7).length / dl.length : .5;
    const shp = sum(a, x => x.shp) / sum(a, x => x.q), load27 = SS.filter(x => x.factory === f && !x.cancelled).length, ret = (QUALITY[f] || {}).ret || 2;
    const score = ok * 40 + Math.min(1, shp) * 25 + Math.min(a.length, 10) * 2 - ret * 5 - load27 * 0.3;
    return { f, n: a.length, ok, ret, load27, score };
  }).sort((a, b) => b.score - a.score);
}

pages.qc.flow = main => {
  const all = [...DEALS, ...LEADS];
  main.innerHTML = `<div class="ph"><div><h2>Luồng tư vấn</h2><p>Từ yêu cầu đầu tiên đến khi bàn giao cho sản xuất. Yêu cầu gửi từ website (module ①) vào cột "Tiếp nhận".</p></div><div class="tools"><span class="muted" style="font-size:13px">${all.length} cơ hội · ${fmt(sum(all, d => d.qty))} pcs/mùa</span></div></div>
    <div class="kanban" id="kb">${STAGES.map((st, i) => { const ds = all.filter(d => d.stage === i); return `<div class="kcol"><h4>${st}<span>${ds.length}</span></h4>
      ${ds.map(d => `<div class="kcard ${d.hot ? 'hot' : ''}" data-id="${d.id}" tabindex="0" role="button"><b>${esc(d.brand)}</b>${esc(d.item)} ${ITEM[d.item] || ''} · ${fmt(d.qty)} pcs<br><small>${esc(d.owner)} · ${esc(d.src)}</small></div>`).join('')}</div>`; }).join('')}</div>
    <p class="muted" style="font-size:12px">Cơ hội L001–L007 là <span class="sim">mô phỏng</span>; gợi ý nhà máy dùng dữ liệu thật 26FW.</p>`;
  const open = id => {
    const d = all.find(x => x.id === id); if (!d) return;
    const rec = recommendFactories(d.item).slice(0, 4);
    openDrawer(`<h3 style="font-family:var(--display)">${esc(d.brand)}</h3><p class="muted">${d.id} · ${esc(d.src)} · ${esc(d.owner)}</p>
      <dl class="dl"><dt>Mặt hàng</dt><dd>${d.item} ${ITEM[d.item] || ''}</dd><dt>Số lượng/mùa</dt><dd class="num">${fmt(d.qty)}</dd><dt>Bước</dt><dd>${STAGES[d.stage]}</dd>${d.note ? `<dt>Ghi chú</dt><dd>${esc(d.note)}</dd>` : ''}</dl>
      <h4 style="margin:0 0 6px">Việc cần làm ở bước này</h4><ul class="docs">${CHECK[d.stage].map(c => `<li>${esc(c)}</li>`).join('')}</ul>
      <div class="ai"><div class="h">AI gợi ý nhà máy cho ${d.item}, dựa trên 26FW</div>
      ${rec.length ? `<table class="t"><thead><tr><th>Nhà máy</th><th class="r">Style ${d.item}</th><th class="r">Đúng hạn</th><th class="r">Return <span class="sim"></span></th><th class="r">Tải 27SS</th></tr></thead><tbody>
      ${rec.map(r => `<tr><td><b>${esc(r.f)}</b></td><td class="r num">${r.n}</td><td class="r num">${Math.round(r.ok * 100)}%</td><td class="r num">${r.ret}%</td><td class="r num">${r.load27} st</td></tr>`).join('')}</tbody></table>
      <p class="reason">Điểm = đúng hạn 40% + tỷ lệ xuất đủ 25% + kinh nghiệm mặt hàng − return − tải mùa sau.</p>` : '<p class="muted">Chưa có lịch sử cho mặt hàng này.</p>'}</div>
      <div style="display:flex;gap:8px;margin-top:16px">${d.stage < 6 ? `<button class="btn" id="nextSt">Chuyển sang: ${STAGES[d.stage + 1]}</button>` : ''}</div>`);
    const b = $('#nextSt'); if (b) b.addEventListener('click', () => { d.stage++; closeDrawer(); pages.qc.flow(main); toast(`${d.brand}: ${STAGES[d.stage]}`); });
  };
  $('#kb').addEventListener('click', e => { const c = e.target.closest('.kcard'); if (c) open(c.dataset.id); });
  $('#kb').addEventListener('keydown', e => { const c = e.target.closest('.kcard'); if (c && e.key === 'Enter') open(c.dataset.id); });
};

/* ---------------- buyer inbox with AI drafts (meeting items #2, #14) ---------------- */
const by = code => FW.find(s => s.s === code) || SS.find(s => s.s === code);
const INBOX = [
  { id:1, ch:'KakaoTalk', from:'CHALLENGER · MD 박', at:'12/10 09:14', subj:'W33 선적 일정 문의', body:'W33 (CHF4MPT6444) 선적 언제 가능한가요?\nETD 10/7이었는데 아직 소식이 없어서요.', style:'CHF4MPT6444', kind:'status' },
  { id:2, ch:'Email', from:'CHALLENGER · 생산팀', at:'11/10 17:40', subj:'[26FW] 3개 스타일 수량 20% 감량 확정', body:'아래 스타일 수량 감량 확정되었습니다.\nCHF3MPT6334 360 → 288\nCHF3WPT6745 400 → 320\nCHF3WSK6751 370 → 296\n공장에도 전달 부탁드립니다.', kind:'change',
    changes:[['CHF3MPT6334',288],['CHF3WPT6745',320],['CHF3WSK6751',296]] },
  { id:3, ch:'Email', from:'CHALLENGER · 27SS 기획', at:'11/10 10:02', subj:'CHG1MJK7102 공장/FPP 일정', body:'27SS SP1 CHG1MJK7102 공장 확정됐나요?\nFPP 일정도 공유 부탁드립니다.', style:'CHG1MJK7102', kind:'status' },
  { id:4, ch:'KakaoTalk', from:'CHALLENGER · QC 이', at:'10/10 15:22', subj:'W41 검사 결과', body:'CHF4WHP6852 검사 진행 상황 공유 부탁드려요.', style:'CHF4WHP6852', kind:'status' }
];
const APPLIED = [];
function draftFor(m) {
  if (m.kind === 'change') return `안녕하세요, KLMAS 이민지입니다.\n\n3개 스타일 수량 감량 내용 확인했습니다. KOPS에 반영했고 공장(TAN BINH MINH)에도 오늘 전달하겠습니다.\n- CHF3MPT6334: 360 → 288\n- CHF3WPT6745: 400 → 320\n- CHF3WSK6751: 370 → 296\n\n이미 재단된 수량이 있으면 따로 말씀드리겠습니다.\n감사합니다.`;
  const s = by(m.style);
  if (!s) return '';
  if (s.season === '27SS') return `안녕하세요, KLMAS입니다.\n\n${s.s}(${s.no})는 아직 공장이 확정되지 않았습니다. 이번 주 안에 공장 확정 후 FPP 일정 공유드리겠습니다.\n오더 ${fmt(s.q)}장, ETD ${ddy(s.etdD)} 기준으로 일정 잡겠습니다.\n감사합니다.`;
  const r = styleStatus(s);
  if (m.id === 1) return `안녕하세요, KLMAS 이민지입니다.\n\n${s.s}(${s.no})는 현재 ${s.factory}에서 생산 중이며 OUTPUT ${fmt(s.out)}/${fmt(s.q)}장입니다.\n현재 생산 속도(일 ${r.proj.rate}장${r.proj.assumed ? ', 공장 확인 필요' : ''}) 기준으로 봉제 완료 ${dd(r.proj.finish)}, 출고 가능 ${dd(r.proj.ready)} 예상이며 ETD 대비 약 ${r.proj.late}일 지연됩니다.\n일정 단축을 위해 일부 수량 AIR 선적 가능 여부 검토 부탁드립니다.\n감사합니다.`;
  return `안녕하세요, KLMAS입니다.\n\n${s.s}(${s.no}) 검사 현황 공유드립니다.\n오더 ${fmt(s.q)}장 중 OUTPUT ${fmt(s.out)}장, 검사 완료 ${fmt(s.ins)}장 (${pct(s.ins, s.q)}), 선적 ${fmt(s.shp)}장입니다.\n남은 수량은 ${dd(addDays(TODAY, 3))}까지 검사 예정이며 검사 리포트 PDF는 완료 후 바로 보내드리겠습니다.\n감사합니다.`;
}
pages.qc.inbox = main => {
  let cur = INBOX[0].id;
  main.innerHTML = `<div class="ph"><div><h2>Hộp thư buyer</h2><p>AI đọc email/KakaoTalk, gắn với style trong KOPS, soạn câu trả lời bằng dữ liệu thật và đề xuất thay đổi có cấu trúc. MR duyệt trước khi gửi; mọi thay đổi được ghi lịch sử.</p></div></div>
    <div class="inbox"><div class="ilist" id="il"></div><div class="idetail" id="id"></div></div>`;
  const list = () => $('#il').innerHTML = INBOX.map(m => `<div class="iitem" data-id="${m.id}" aria-current="${m.id === cur}" tabindex="0"><span class="ch">${m.ch} · ${m.at}${m.sent ? ' · ĐÃ GỬI' : ''}</span><b>${esc(m.subj)}</b>${esc(m.from)}</div>`).join('');
  const show = () => {
    const m = INBOX.find(x => x.id === cur), s = m.style && by(m.style);
    const chg = m.kind === 'change' ? `<div class="h" style="margin-top:12px">Thay đổi trích xuất</div>${m.changes.map(([c, n]) => { const x = by(c), a = APPLIED.find(z => z.msg === m.id && z.style === c), from = a ? a.from : x.q; return `<div class="change"><span style="font-family:var(--mono)">${c}</span><span>Số lượng đặt ${fmt(from)} → <b>${fmt(n)}</b> (${pct(n - from, from)})${a ? ' · đã áp dụng' : ''}</span><span class="muted">${esc(x.factory)}</span></div>`; }).join('')}
      <p class="reason">Phát hiện khi phân tích: ORDER RECAP đã ghi số mới nhưng báo cáo sản xuất và shipment status vẫn dùng số cũ. Áp dụng trên KOPS sẽ cập nhật cả ba.</p>` : '';
    $('#id').innerHTML = `<p class="muted" style="margin:0 0 6px;font-size:13px">${m.ch} · ${esc(m.from)} · ${m.at}</p><h3 style="font-size:19px;margin-bottom:10px">${esc(m.subj)}</h3>
      <div class="quote">${esc(m.body)}</div>
      <div class="ai"><div class="h">AI phân tích · ý định: ${m.kind === 'change' ? 'thay đổi số lượng' : 'hỏi tiến độ'}${s ? ` · liên kết ${s.s}` : ''}</div>${chg}
        <label for="draft" class="h" style="display:block;margin-top:12px">Bản nháp trả lời (tiếng Hàn)</label><textarea id="draft">${esc(m.draft ?? draftFor(m))}</textarea>
        <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">${m.kind === 'change' && !m.applied ? '<button class="btn warn" id="apply">Áp dụng thay đổi vào KOPS</button>' : ''}
        <button class="btn" id="send" ${m.sent ? 'disabled' : ''}>${m.sent ? 'Đã gửi' : 'Duyệt và gửi'}</button></div>
        ${m.applied ? `<p class="reason">Đã ghi lịch sử: ${APPLIED.filter(a => a.msg === m.id).map(a => `${a.style} ${a.from}→${a.to}`).join(', ')} · bởi Lee Min Ji · nguồn email ${m.at}</p>` : ''}</div>`;
    $('#draft').addEventListener('input', e => m.draft = e.target.value);
    const ap = $('#apply'); if (ap) ap.addEventListener('click', () => { m.changes.forEach(([c, n]) => { const x = by(c); APPLIED.push({ msg: m.id, style: c, from: x.q, to: n }); x.q = n; }); m.applied = true; show(); toast('Đã cập nhật 3 style, có lịch sử thay đổi'); });
    $('#send').addEventListener('click', () => { m.sent = true; list(); show(); toast('Đã gửi trả lời (prototype)'); });
  };
  $('#il').addEventListener('click', e => { const it = e.target.closest('.iitem'); if (it) { cur = +it.dataset.id; list(); show(); } });
  list(); show();
};

/* ---------------- inspection planning (meeting item #12) ---------------- */
pages.qc.plan = main => {
  const draw = () => {
    const rows = REQUESTS.map(r => { const a = ASSIGN && ASSIGN[r.id]; return `<tr><td>${esc(r.id)}<br><small class="muted">${r.type}</small></td><td>${esc(r.brand)} ${r.ext ? '<span class="pill">ngoài</span>' : ''}</td>
      <td style="font-family:var(--mono);font-size:13px">${esc(r.style)}</td><td>${esc(r.factory)}<br><small class="muted">${esc(r.region)}</small></td><td class="r num">${fmt(r.lot)}</td><td class="r num">${aql(r.lot).n}</td>
      <td>${a ? `<span class="who">${esc(a.ins.name)}</span><div class="reason">${esc(a.why.join(', ') || 'còn trống lịch')}</div>` : (ASSIGN ? '<span class="pill bad">thiếu người</span>' : '<span class="muted">–</span>')}</td></tr>`; }).join('');
    const loads = ASSIGN ? INSPECTORS.map(i => ({ label: i.name, a: Object.values(ASSIGN).filter(x => x && x.ins.id === i.id).length })).map(x => ({ ...x, text: x.a + ' lô' })) : [];
    main.innerHTML = `<div class="ph"><div><h2>Lịch &amp; phân công kiểm ngày 13/10</h2><p>${REQUESTS.length} yêu cầu: ${REQUESTS.filter(r => !r.ext).length} lô CHALLENGER (dữ liệu thật: style đã may nhưng chưa kiểm đủ) và ${REQUESTS.filter(r => r.ext).length} lô thương hiệu ngoài <span class="sim">mô phỏng</span>. Khu vực nhà máy là giả định.</p></div>
      <div class="tools"><button class="btn" id="auto">${ASSIGN ? 'Phân công lại' : 'AI đề xuất phân công'}</button>${ASSIGN ? '<button class="btn ghost" id="ok">Xác nhận và gửi Zalo</button>' : ''}</div></div>
      <div class="g3"><div class="panel"><div class="scroll"><table class="t assign"><thead><tr><th>Yêu cầu</th><th>Thương hiệu</th><th>Style</th><th>Nhà máy</th><th class="r">Lô</th><th class="r">Mẫu AQL</th><th>Kiểm viên</th></tr></thead><tbody>${rows}</tbody></table></div></div>
      <div class="panel"><h3>Kiểm viên</h3>${ASSIGN ? hbars(loads, { max: 3 }) : INSPECTORS.map(i => `<div style="font-size:13px;padding:5px 0;border-bottom:1px solid var(--line)"><b>${esc(i.name)}</b> · ${esc(i.region)}<br><small class="muted">${i.spec.join(', ')}${i.ded ? ' · chuyên trách ' + esc(i.ded) : ''}</small></div>`).join('')}
      <p class="reason" style="margin-top:10px">Quy tắc: tối đa 3 lô/người/ngày, 2 lô nếu khác nhà máy; ưu tiên kiểm viên chuyên trách nhà máy (1 kiểm viên 1 style), cùng khu vực, đúng mặt hàng. Bản thật: tối ưu bằng solver + thời gian di chuyển.</p></div></div>`;
    $('#auto').addEventListener('click', () => { ASSIGN = autoAssign(); draw(); });
    const ok = $('#ok'); if (ok) ok.addEventListener('click', () => toast('Đã gửi lịch cho ' + new Set(Object.values(ASSIGN).filter(Boolean).map(a => a.ins.id)).size + ' kiểm viên qua Zalo (prototype)'));
  };
  draw();
};

/* ---------------- mobile inspection report (meeting item #11) ---------------- */
pages.qc.report = main => {
  const st = { req: REQUESTS[0], counts: {}, photos: {}, lot: REQUESTS[0].lot };
  const SLOTS = ['Mặt trước','Mặt sau','Nhãn chăm sóc','Tag','Dò kim','Lỗi 1','Lỗi 2','Carton','Đo thông số'];
  main.innerHTML = `<div class="ph"><div><h2>Báo cáo kiểm trên điện thoại</h2><p>Kiểm viên nhập số lỗi theo mã và chụp ảnh tại xưởng; báo cáo PDF tạo ngay, không phải chép lại vào Excel (hiện 70–100 báo cáo/ngày). Chọn thương hiệu chỉ hiện tài liệu thương hiệu đó yêu cầu.</p></div></div>
    <div class="phone-wrap"><div class="phone"><div class="bar-top">KOPS · Kiểm hàng<small id="pSub"></small></div><div class="body" id="pb"></div></div>
    <div class="panel"><h3>Xem trước kết quả</h3><div id="prev"></div></div></div>`;
  const calc = () => {
    const a = aql(st.lot); let crit = 0, maj = 0, min = 0;
    DEFECTS.forEach(([c, , sev]) => { const n = st.counts[c] || 0; if (sev === 'Critical') crit += n; else if (sev === 'Major') maj += n; else min += n; });
    return { a, crit, maj, min, pass: crit === 0 && maj <= a.maj && min <= a.min };
  };
  const brand = () => QC_BRANDS.find(b => b.name === st.req.brand);
  const renderPrev = () => {
    const c = calc();
    $('#prev').innerHTML = `<dl class="dl"><dt>Yêu cầu</dt><dd>${esc(st.req.id)} · ${esc(st.req.brand)} · <span style="font-family:var(--mono)">${esc(st.req.style)}</span></dd><dt>Nhà máy</dt><dd>${esc(st.req.factory)}</dd>
      <dt>Lô / mẫu</dt><dd class="num">${fmt(st.lot)} / ${c.a.n} (AQL 2.5 / 4.0, mức II)</dd><dt>Lỗi</dt><dd class="num">Critical ${c.crit} · Major ${c.maj}/${c.a.maj} · Minor ${c.min}/${c.a.min}</dd>
      <dt>Ảnh</dt><dd>${Object.keys(st.photos).length}/${SLOTS.length}</dd></dl><div class="verdict ${c.pass ? 'pass' : 'fail'}">${c.pass ? 'ĐẠT' : 'KHÔNG ĐẠT · cần kiểm lại'}</div>
      <button class="btn" id="pdf">Tạo báo cáo PDF</button> <span class="muted" style="font-size:12px">Mở bản in; chọn "Lưu dưới dạng PDF".</span>`;
    $('#pdf').addEventListener('click', makePdf);
  };
  const render = () => {
    const c = calc(), b = brand();
    $('#pSub').textContent = `Hằng · ${st.req.factory}`;
    $('#pb').innerHTML = `<label>Yêu cầu hôm nay<select id="rq">${REQUESTS.map(r => `<option value="${r.id}" ${r.id === st.req.id ? 'selected' : ''}>${r.id} · ${r.brand} · ${r.style}</option>`).join('')}</select></label>
      <div style="font-size:12px;color:var(--ink-3)">Tài liệu ${esc(b.name)} yêu cầu</div><ul class="docs">${b.docs.map(d => `<li>${esc(d)}</li>`).join('')}</ul>
      <label>Số lượng lô<input id="lot" type="number" min="2" value="${st.lot}" inputmode="numeric"></label>
      <div class="aql">Lấy mẫu <b>${c.a.n}</b> sp · chấp nhận Major ≤ ${c.a.maj}, Minor ≤ ${c.a.min}, Critical = 0</div>
      ${DEFECTS.map(([code, name, sev]) => `<div class="defect"><div><b style="font-family:var(--mono);font-size:13px">${code}</b> ${esc(name)}<small>${sev}</small></div>
        <div class="stepper"><button type="button" data-d="${code}" data-v="-1" aria-label="Giảm ${code}">−</button><output>${st.counts[code] || 0}</output><button type="button" data-d="${code}" data-v="1" aria-label="Tăng ${code}">+</button></div></div>`).join('')}
      <div style="font-size:12px;color:var(--ink-3);margin-top:12px">Ảnh bắt buộc</div>
      <div class="photos">${SLOTS.map(sl => `<label class="photo" style="${st.photos[sl] ? `background-image:url(${st.photos[sl]});color:transparent` : ''}">${esc(sl)}<input type="file" accept="image/*" capture="environment" data-slot="${esc(sl)}"></label>`).join('')}</div>
      <div class="verdict ${c.pass ? 'pass' : 'fail'}">${c.pass ? 'ĐẠT' : 'KHÔNG ĐẠT'}</div>`;
    $('#rq').addEventListener('change', e => { st.req = REQUESTS.find(r => r.id === e.target.value); st.lot = st.req.lot; st.counts = {}; render(); });
    $('#lot').addEventListener('change', e => { st.lot = Math.max(2, +e.target.value || 2); render(); });
    $$('.stepper button', $('#pb')).forEach(b => b.addEventListener('click', () => { const d = b.dataset.d; st.counts[d] = Math.max(0, (st.counts[d] || 0) + +b.dataset.v); render(); }));
    $$('.photo input', $('#pb')).forEach(inp => inp.addEventListener('change', () => { const f = inp.files[0]; if (!f) return; const rd = new FileReader(); rd.onload = () => { st.photos[inp.dataset.slot] = rd.result; render(); }; rd.readAsDataURL(f); }));
    renderPrev();
  };
  const makePdf = () => {
    const c = calc(), b = brand(), w = window.open('', '_blank');
    if (!w) { toast('Trình duyệt chặn cửa sổ mới'); return; }
    w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>Inspection ${esc(st.req.id)}</title><style>body{font:13px/1.5 Arial,sans-serif;margin:28px;color:#111}h1{font-size:20px;margin:0}table{border-collapse:collapse;width:100%;margin:10px 0}td,th{border:1px solid #999;padding:4px 6px;text-align:left}.ph{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.ph div{border:1px solid #999;height:150px;background:#eee center/cover;font-size:11px;padding:3px}.v{font-size:18px;font-weight:bold;color:${c.pass ? '#1b6b3a' : '#a01e24'}}</style></head><body>
      <h1>KLMAS Final Inspection Report</h1><p>${esc(b.name)} · ${esc(st.req.id)} · ${ddy(addDays(TODAY, 1))} · Kiểm viên: Nguyễn Thị Hằng</p>
      <table><tr><th>Style</th><td>${esc(st.req.style)}</td><th>Nhà máy</th><td>${esc(st.req.factory)}</td></tr><tr><th>Lô</th><td>${fmt(st.lot)}</td><th>Mẫu (AQL 2.5/4.0 II)</th><td>${c.a.n}</td></tr></table>
      <table><tr><th>Mã</th><th>Lỗi</th><th>Mức</th><th>SL</th></tr>${DEFECTS.filter(([cd]) => st.counts[cd]).map(([cd, n, s]) => `<tr><td>${cd}</td><td>${esc(n)}</td><td>${s}</td><td>${st.counts[cd]}</td></tr>`).join('') || '<tr><td colspan="4">Không phát hiện lỗi</td></tr>'}</table>
      <p>Critical ${c.crit} · Major ${c.maj} (Ac ${c.a.maj}) · Minor ${c.min} (Ac ${c.a.min})</p><p class="v">Kết luận: ${c.pass ? 'PASS' : 'FAIL'}</p>
      <p>Tài liệu kèm theo: ${b.docs.map(esc).join('; ')}</p>
      <div class="ph">${SLOTS.map(sl => `<div style="${st.photos[sl] ? `background-image:url(${st.photos[sl]})` : ''}">${esc(sl)}</div>`).join('')}</div>
      <script>setTimeout(()=>print(),400)<\/script></body></html>`);
    w.document.close();
  };
  render();
};

/* ---------------- defect analytics (simulated) ---------------- */
pages.qc.analytics = main => {
  const r = rng(77);
  const codes = DEFECTS.map(([c, n, s]) => ({ c, n, s, v: Math.round((s === 'Critical' ? 2 : s === 'Minor' ? 60 : 30) * (0.3 + r() * 1.4)) })).sort((a, b) => b.v - a.v);
  const tot = sum(codes, x => x.v); let cum = 0;
  const facs = Object.keys(QUALITY).slice(0, 8).map(f => ({ label: f, a: QUALITY[f].dhu, text: QUALITY[f].dhu + ' DHU', cls: QUALITY[f].dhu > 6 ? 'bad' : QUALITY[f].dhu > 4 ? 'warn' : '' })).sort((a, b) => b.a - a.a);
  const insp = INSPECTORS.map(i => ({ i, lots: 18 + Math.round(r() * 30), missed: Math.round(r() * 4) })).sort((a, b) => b.missed / b.lots - a.missed / a.lots);
  main.innerHTML = `<div class="ph"><div><h2>Phân tích lỗi 30 ngày</h2><p><span class="sim">Dữ liệu mô phỏng</span>: sẽ lấy từ các báo cáo kiểm trên điện thoại. Dùng cho bảng phân tích lỗi và ảnh lỗi hằng ngày gửi nhà máy, theo quy trình trong hồ sơ năng lực.</p></div></div>
    <div class="g2"><div class="panel"><h3>Pareto mã lỗi</h3><table class="t"><thead><tr><th>Mã</th><th>Lỗi</th><th class="r">SL</th><th class="r">Lũy kế</th></tr></thead><tbody>
      ${codes.map(x => { cum += x.v; return `<tr><td style="font-family:var(--mono)">${x.c}</td><td>${esc(x.n)} <small class="muted">${x.s}</small></td><td class="r num">${x.v}</td><td class="r num" style="${cum / tot <= .8 ? 'font-weight:700' : 'color:var(--ink-3)'}">${pct(cum, tot)}</td></tr>`; }).join('')}</tbody></table>
      <p class="reason">Các mã in đậm chiếm 80% lỗi: tập trung kiểm và phản hồi nhà máy.</p></div>
    <div class="panel"><h3>DHU theo nhà máy <span class="muted">lỗi / 100 sp kiểm</span></h3>${hbars(facs)}</div></div>
    <div class="panel"><h3>Thống kê lỗi do kiểm viên <span class="muted">lỗi bị sót khi kiểm lại mẫu ngẫu nhiên</span></h3><div class="scroll"><table class="t"><thead><tr><th>Kiểm viên</th><th>Khu vực</th><th class="r">Lô đã kiểm</th><th class="r">Lô bị phát hiện sót</th><th class="r">Tỷ lệ</th><th>Đề xuất</th></tr></thead><tbody>
      ${insp.map(x => `<tr><td>${esc(x.i.name)}</td><td>${esc(x.i.region)}</td><td class="r num">${x.lots}</td><td class="r num">${x.missed}</td><td class="r num">${pct(x.missed, x.lots, 1)}</td><td>${x.missed / x.lots > .1 ? '<span class="pill bad">đào tạo lại</span>' : x.missed ? '<span class="pill warn">theo dõi</span>' : '<span class="pill good">tốt</span>'}</td></tr>`).join('')}</tbody></table></div></div>`;
};

/* boot */
route();
