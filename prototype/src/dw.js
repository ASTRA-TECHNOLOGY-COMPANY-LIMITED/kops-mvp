/* ===================== ② PRODUCTION DATA WAREHOUSE ===================== */
let DW_SEASON = '26FW';
const seasonSel = () => `<select id="seasonSel" aria-label="Mùa">${['26FW','27SS'].map(s => `<option ${s === DW_SEASON ? 'selected' : ''}>${s}</option>`).join('')}</select>`;
function bindSeason(main, fn) { const el = $('#seasonSel', main); if (el) el.addEventListener('change', () => { DW_SEASON = el.value; fn(main); }); }
const groupBy = (arr, f) => arr.reduce((m, x) => { const k = f(x); (m[k] = m[k] || []).push(x); return m; }, {});
const sum = (arr, f) => arr.reduce((a, x) => a + (f(x) || 0), 0);

/* ---------- simulated partner quality (no source data yet) ---------- */
const R = rng(26);
const QUALITY = {};
['TAN BINH MINH','DONG MY','TRUONG PHUC','MTT','NATEXCO','HA HIEU','TIEN THANH','FG BAC GIANG','JM','SON HA'].forEach(f => {
  QUALITY[f] = { finalFail: +(1 + R() * 5).toFixed(1), claim: +(R() * 1.2).toFixed(2), dhu: +(2 + R() * 6).toFixed(1) };
  QUALITY[f].ret = +(QUALITY[f].finalFail * 0.35 + QUALITY[f].claim).toFixed(2);
});
const HISTORY = [ // 25SS–26SS simulated, 26FW/27SS real (computed)
  { s:'25SS', styles:118, qty:71200, ontime:88, ret:2.1, sim:true },
  { s:'25FW', styles:104, qty:58900, ontime:84, ret:2.6, sim:true },
  { s:'26SS', styles:126, qty:79400, ontime:90, ret:1.9, sim:true }
];

/* ---------- factory moves (real: Order Recap notes + FAB snapshots 19/05, 15/06 + current 12/10) ---------- */
const CODE2F = { NTC:'NATEXCO', HH:'HA HIEU', MTT:'MTT', TBM:'TAN BINH MINH', DM:'DONG MY', TP:'TRUONG PHUC' };
const MOVES = FW.map(s => {
  const ev = [];
  for (const m of (s.fn || '').matchAll(/(\d{2})(\d{2})(\d{2})\s*(FIXED|MOVED)\s*FACT(?:\(([^)]+)\))?/gi)) {
    ev.push({ d: new Date(2000 + +m[1], +m[2] - 1, +m[3]), kind: m[4].toUpperCase(), f: m[5] ? (CODE2F[m[5].toUpperCase()] || nf(m[5])) : null, src: 'Ghi chú ORDER RECAP' });
  }
  if (s.fh[0]) ev.push({ d: new Date(2026, 4, 19), kind: 'SNAP', f: nf(s.fh[0]), src: 'FAB(260519)' });
  if (s.fh[1]) ev.push({ d: new Date(2026, 5, 15), kind: 'SNAP', f: nf(s.fh[1]), src: 'FAB(0615)' });
  ev.push({ d: TODAY, kind: 'SNAP', f: s.factory, src: 'Production status 12/10' });
  ev.sort((a, b) => a.d - b.d);
  const seq = ev.filter(e => e.f).map(e => e.f);
  const distinct = seq.filter((f, i) => i === 0 || f !== seq[i - 1]);
  const moved = distinct.length > 1 || ev.some(e => e.kind === 'MOVED');
  return { s, ev, path: distinct, moved };
}).filter(m => m.moved);

/* ---------- on-time metrics from real shipments ---------- */
function shipDelay(s) { const f = s.ships[0]; return f && f.etd && s.etdD ? days(f.etd, s.etdD) : null; }

/* ================= pages ================= */
pages.dw.overview = main => {
  const S = DW_SEASON === '26FW' ? FW : SS.filter(x => !x.cancelled);
  let kpi, charts;
  if (DW_SEASON === '26FW') {
    const q = sum(S, x => x.q), out = sum(S, x => x.out), ins = sum(S, x => x.ins), shp = sum(S, x => x.shp);
    const dl = S.map(shipDelay).filter(x => x != null);
    kpi = [['Style', S.length, 'đang chạy'], ['Số lượng đặt', fmt(q), 'pcs'], ['Đã may', pct(out, q, 1), fmt(out) + ' pcs'], ['Đã kiểm', pct(ins, q, 1), fmt(ins) + ' pcs'], ['Đã xuất', pct(shp, q, 1), `${fmt(shp)} pcs · đúng hạn ${pct(dl.filter(x => x <= 7).length, dl.length)}`]];
    const byF = groupBy(S, x => x.factory);
    const rows = Object.entries(byF).map(([f, a]) => ({ label: f, b: sum(a, x => x.q), a: sum(a, x => x.shp), text: `${fmt(sum(a, x => x.shp))} / ${fmt(sum(a, x => x.q))}` })).sort((a, b) => b.b - a.b);
    const byT = Object.entries(groupBy(S, x => x.t)).map(([k, a]) => ({ label: k.replace('26FW-', ''), a: sum(a, x => x.q), text: `${fmt(sum(a, x => x.q))} · ${a.length} st` })).sort((a, b) => b.a - a.a);
    charts = `<div class="g3"><div class="panel"><h3>Đặt và đã xuất theo nhà máy <span class="muted">pcs, tính từ dữ liệu chi tiết</span></h3>
      <div class="legend"><span><i style="background:var(--teal-soft)"></i>Số lượng đặt</span><span><i style="background:var(--teal)"></i>Đã xuất</span></div>${hbars(rows)}</div>
      <div class="panel"><h3>Theo collection</h3>${hbars(byT)}</div></div>`;
  } else {
    const all = SS, q = sum(S, x => x.q);
    kpi = [['Style', S.length, `${all.length - S.length} đã hủy`], ['Số lượng đặt', fmt(q), 'pcs'], ['Đã chốt nhà máy', pct(S.filter(x => x.factory).length, S.length), `${S.filter(x => x.factory).length} style`], ['ETD sớm nhất', ddy(new Date(Math.min(...S.map(x => x.etdD || Infinity).filter(x => x > new Date('2026-10-01'))))), 'bỏ qua 5 ETD lỗi năm'], ['Giai đoạn', 'Mẫu', 'chưa có lô xuất']];
    const byF = Object.entries(groupBy(S, x => x.factory || 'Chưa chốt')).map(([f, a]) => ({ label: f, a: sum(a, x => x.q), text: `${fmt(sum(a, x => x.q))} · ${a.length} st` })).sort((a, b) => b.a - a.a);
    const byI = Object.entries(groupBy(S, x => x.item2)).map(([k, a]) => ({ label: `${k} ${ITEM[k] || ''}`, a: a.length, text: a.length + ' style' })).sort((a, b) => b.a - a.a);
    charts = `<div class="g2"><div class="panel"><h3>Số lượng theo nhà máy</h3>${hbars(byF)}</div><div class="panel"><h3>Style theo mặt hàng</h3>${hbars(byI)}</div></div>`;
  }
  const fwQ = sum(FW, x => x.q), ssQ = sum(SS.filter(x => !x.cancelled), x => x.q);
  const dlAll = FW.map(shipDelay).filter(x => x != null);
  const hist = [...HISTORY, { s:'26FW', styles:FW.length, qty:fwQ, ontime:Math.round(100 * dlAll.filter(x => x <= 7).length / dlAll.length), ret:null }, { s:'27SS', styles:SS.filter(x => !x.cancelled).length, qty:ssQ, ontime:null, ret:null }];
  const mx = Math.max(...hist.map(h => h.qty));
  main.innerHTML = `<div class="ph"><div><h2>Tổng quan mùa ${DW_SEASON}</h2><p>Mọi tổng số được tính lại từ dòng chi tiết. File Excel gốc báo tổng 26FW là 106.681 pcs do lỗi công thức; số đúng là ${fmt(fwQ)}.</p></div><div class="tools">${seasonSel()}</div></div>
    <div class="kpis">${kpi.map(([k, v, d]) => `<div class="kpi"><div class="k">${k}</div><div class="v num">${v}</div><div class="d">${d}</div></div>`).join('')}</div>
    ${charts}
    <div class="panel"><h3>Lịch sử các mùa CHALLENGER <span class="sim">25SS–26SS mô phỏng, chờ nạp file cũ</span></h3>
      <div class="scroll"><table class="t"><thead><tr><th>Mùa</th><th class="r">Style</th><th>Số lượng</th><th class="r">Xuất đúng hạn (≤7 ngày so với ETD)</th><th class="r">Tỷ lệ return</th></tr></thead><tbody>
      ${hist.map(h => `<tr><td><b>${h.s}</b> ${h.sim ? '<span class="sim">mô phỏng</span>' : ''}</td><td class="r num">${h.styles}</td>
        <td style="min-width:220px"><div class="hb" style="grid-template-columns:1fr 70px"><div class="track"><i style="width:${100 * h.qty / mx}%;${h.sim ? 'background:repeating-linear-gradient(45deg,var(--sim) 0 3px,transparent 3px 6px)' : ''}"></i></div><div class="num" style="text-align:right">${fmt(h.qty)}</div></div></td>
        <td class="r num">${h.ontime == null ? '–' : h.ontime + '%'}</td><td class="r num">${h.ret == null ? '<span class="muted">chưa có dữ liệu kiểm</span>' : h.ret + '%'}</td></tr>`).join('')}
      </tbody></table></div></div>`;
  bindSeason(main, pages.dw.overview);
};

pages.dw.styles = main => {
  main.innerHTML = `<div class="ph"><div><h2>Lưu trữ style &amp; đơn hàng</h2><p>Tra cứu mẫu mã các mùa, gồm vải chính, logo/phụ liệu, màu, lô xuất và lịch sử nhà máy. Nhấn một dòng để xem chi tiết.</p></div>
    <div class="tools"><input id="q" placeholder="Mã style, tên, vải…" aria-label="Tìm"><select id="fs"><option value="">Mọi mùa</option><option>26FW</option><option>27SS</option></select>
    <select id="fi"><option value="">Mọi mặt hàng</option>${Object.entries(ITEM).map(([k, v]) => `<option value="${k}">${k} ${v}</option>`).join('')}</select>
    <select id="ff"><option value="">Mọi nhà máy</option>${[...new Set(ALL.map(x => x.factory).filter(Boolean))].sort().map(f => `<option>${f}</option>`).join('')}</select></div></div>
    <div class="panel"><div class="scroll"><table class="t" id="stTable"><thead><tr><th>Mùa</th><th>Số đơn</th><th>Mã style</th><th>Tên</th><th>Nhà máy</th><th class="r">SL</th><th>ETD</th><th>Trạng thái</th></tr></thead><tbody></tbody></table></div><p class="muted" id="stCount" style="font-size:13px"></p></div>`;
  const draw = () => {
    const q = $('#q').value.trim().toLowerCase(), fs = $('#fs').value, fi = $('#fi').value, ff = $('#ff').value;
    const rows = ALL.filter(x => (!fs || x.season === fs) && (!fi || x.item2 === fi) && (!ff || x.factory === ff) &&
      (!q || [x.s, x.it, x.kr, x.no, x.fab && x.fab.join(' ')].join(' ').toLowerCase().includes(q)));
    $('#stTable tbody').innerHTML = rows.slice(0, 300).map(x => {
      const st = x.season === '26FW' ? styleStatus(x) : null;
      const pill = st ? `<span class="pill ${st.tone}">${esc(st.label)}</span>` : `<span class="pill ${x.cancelled ? 'bad' : ''}">${x.cancelled ? 'Đã hủy' : 'Đang làm mẫu'}</span>`;
      return `<tr class="click" data-s="${x.s}" tabindex="0"><td>${x.season}</td><td>${esc(x.no)}</td><td style="font-family:var(--mono)">${x.s}</td><td>${esc(x.it)}<br><small class="muted">${esc(x.kr || '')}</small></td><td>${esc(x.factory || '–')}</td><td class="r num">${fmt(x.q)}</td><td>${ddy(x.etdD)}</td><td>${pill}</td></tr>`;
    }).join('');
    $('#stCount').textContent = `${rows.length} style`;
  };
  ['#q', '#fs', '#fi', '#ff'].forEach(s => $(s).addEventListener('input', draw));
  $('#stTable').addEventListener('click', e => { const tr = e.target.closest('tr[data-s]'); if (tr) styleDrawer(tr.dataset.s); });
  $('#stTable').addEventListener('keydown', e => { const tr = e.target.closest('tr[data-s]'); if (tr && e.key === 'Enter') styleDrawer(tr.dataset.s); });
  draw();
};

function styleDrawer(code) {
  const s = ALL.find(x => x.s === code); if (!s) return;
  const mv = MOVES.find(m => m.s.s === code);
  const evs = s.season === '26FW' ? (mv ? mv.ev : [{ d: TODAY, f: s.factory, src: 'Production status 12/10', kind: 'SNAP' }]) : [];
  openDrawer(`<h3>${s.s}</h3><p style="margin:4px 0 0">${esc(s.it)}<br><span class="muted">${esc(s.kr || '')}</span></p>
    <dl class="dl"><dt>Mùa / số đơn</dt><dd>${s.season} · ${esc(s.no)} · ${esc(s.t || '')}</dd>
    <dt>Giới tính / mặt hàng</dt><dd>${s.gender} · ${s.item2} ${ITEM[s.item2] || ''}</dd>
    <dt>Nhà máy hiện tại</dt><dd>${esc(s.factory || 'Chưa chốt')}</dd><dt>Số lượng</dt><dd class="num">${fmt(s.q)} pcs</dd>
    <dt>ETD / RDD</dt><dd>${ddy(s.etdD)} / ${ddy(s.rddD)}</dd>
    ${s.fab ? `<dt>Vải chính</dt><dd>${esc(s.fab[1])}<br><small class="muted">${esc(s.fab[0])} · xuất xứ ${esc(s.fab[2])}</small></dd>` : ''}
    ${s.colors ? `<dt>Màu</dt><dd>${s.colors.map(([c, n]) => `${esc(c)} <span class="muted num">${fmt(n)}</span>`).join('<br>') || '–'}</dd>` : ''}
    ${s.ships ? `<dt>Lô xuất</dt><dd>${s.ships.map(x => `${dd(x.etd)}→${dd(x.eta)} ${x.mode} <span class="num">${fmt(x.qty)}</span>${x.review ? ' <span class="pill bad">ETA < ETD, cần kiểm tra</span>' : ''}`).join('<br>') || '–'}<br><small class="muted">+ ${fmt(s.sm)} mẫu</small></dd>` : ''}
    </dl>
    ${s.logo ? `<h4 style="margin:0 0 6px">Logo &amp; phụ liệu</h4><pre class="logo">${esc(s.logo)}</pre>` : ''}
    ${evs.length ? `<h4 style="margin:18px 0 6px">Lịch sử nhà máy</h4><ul class="tl">${evs.map(e => `<li class="${e.kind === 'MOVED' ? 'move' : ''}">${ddy(e.d)} · ${e.kind === 'MOVED' ? 'Chuyển nhà máy' : e.kind === 'FIXED' ? 'Chốt nhà máy' : 'Ghi nhận'} ${e.f ? '<b>' + esc(e.f) + '</b>' : ''}<small>${esc(e.src)}</small></li>`).join('')}</ul>` : ''}`);
}

pages.dw.partners = main => {
  const byF = groupBy(FW, x => x.factory);
  const moveIn = f => MOVES.filter(m => m.path[m.path.length - 1] === f && m.path.length > 1).length;
  const moveOut = f => MOVES.filter(m => m.path.slice(0, -1).includes(f)).length;
  const rows = Object.entries(byF).map(([f, a]) => {
    const q = sum(a, x => x.q), shp = sum(a, x => x.shp), dl = a.map(shipDelay).filter(x => x != null);
    return { f, n: a.length, q, shp, avg: dl.length ? sum(dl, x => x) / dl.length : null, ok: dl.length ? dl.filter(x => x <= 7).length / dl.length : null, ss: SS.filter(x => x.factory === f && !x.cancelled).length, Q: QUALITY[f] || {} };
  }).sort((a, b) => b.q - a.q);
  const sup = RAW.sup;
  main.innerHTML = `<div class="ph"><div><h2>Đối tác</h2><p>Nhà máy gia công, nhà cung cấp vải và thương hiệu. Tiến độ tính từ dữ liệu thật 26FW; tỷ lệ return và lỗi là <span class="sim">mô phỏng</span> cho tới khi module kiểm hàng có dữ liệu.</p></div></div>
    <div class="panel"><h3>Nhà máy gia công <span class="muted">26FW</span></h3><div class="scroll"><table class="t"><thead><tr>
      <th>Nhà máy</th><th class="r">Style</th><th class="r">Đặt</th><th class="r">Đã xuất</th><th class="r">Lô đầu so với ETD</th><th class="r">Đúng hạn ≤7 ngày</th>
      <th class="r">Fail kiểm cuối <span class="sim"></span></th><th class="r">Claim buyer <span class="sim"></span></th><th class="r">Tỷ lệ return <span class="sim"></span></th><th class="r">Chuyển đến / đi</th><th class="r">27SS</th></tr></thead><tbody>
      ${rows.map(r => `<tr><td><b>${esc(r.f)}</b><br><small class="muted">${esc((FACTORY_INFO[r.f] || {}).code || '')}</small></td><td class="r num">${r.n}</td><td class="r num">${fmt(r.q)}</td><td class="r num">${pct(r.shp, r.q, 1)}</td>
        <td class="r num">${r.avg == null ? '–' : (r.avg > 0 ? '+' : '') + r.avg.toFixed(1) + ' ngày'}</td><td class="r num">${r.ok == null ? '–' : Math.round(100 * r.ok) + '%'}</td>
        <td class="r num">${r.Q.finalFail ?? '–'}%</td><td class="r num">${r.Q.claim ?? '–'}%</td>
        <td class="r num"><span class="pill ${r.Q.ret > 2 ? 'bad' : r.Q.ret > 1.2 ? 'warn' : 'good'}">${r.Q.ret ?? '–'}%</span></td>
        <td class="r num">${moveIn(r.f)} / ${moveOut(r.f)}</td><td class="r num">${r.ss}</td></tr>`).join('')}
      </tbody></table></div>
      <p class="muted" style="font-size:12px;margin:10px 0 0">Tỷ lệ return = (SL fail kiểm cuối phải tái chế × hệ số trả về + SL buyer claim) ÷ SL đã kiểm. Định nghĩa cần KLMAS xác nhận.</p></div>
    <div class="g2"><div class="panel"><h3>Nhà cung cấp vải <span class="muted">FAB 15/06, số dòng vật tư</span></h3>${hbars(sup.map(([n, c, co]) => ({ label: `${n} · ${co}`, a: c, text: c + ' dòng' })))}</div>
      <div class="panel"><h3>Thương hiệu kiểm hàng bên thứ ba <span class="sim">mô phỏng</span></h3>
      <table class="t"><thead><tr><th>Thương hiệu</th><th class="r">Lô kiểm/tháng</th><th class="r">Tỷ lệ fail</th></tr></thead><tbody>
      ${QC_BRANDS.filter(b => b.ext).map(b => `<tr><td>${esc(b.name)}</td><td class="r num">${b.lots}</td><td class="r num">${b.fail}%</td></tr>`).join('')}</tbody></table></div></div>`;
};

pages.dw.moves = main => {
  main.innerHTML = `<div class="ph"><div><h2>Lịch sử đổi nhà máy</h2><p>Ghép 3 nguồn thật: ghi chú "FIXED/MOVED FACT" trong ORDER RECAP, hai snapshot sheet FAB (19/05, 15/06) và báo cáo sản xuất 12/10. Trong kho dữ liệu, đây là bảng <code>dim_factory_assignment</code> lưu theo SCD loại 2.</p></div></div>
    <div class="kpis" style="grid-template-columns:repeat(3,1fr)"><div class="kpi"><div class="k">Style có thay đổi nhà máy</div><div class="v num">${MOVES.filter(m => m.path.length > 1).length}</div><div class="d">trên ${FW.length} style 26FW</div></div>
    <div class="kpi"><div class="k">Có ghi chú MOVED FACT</div><div class="v num">${MOVES.filter(m => m.ev.some(e => e.kind === 'MOVED')).length}</div><div class="d">ghi tay trong ô Excel</div></div>
    <div class="kpi"><div class="k">Ngày gần nhất</div><div class="v">${ddy(new Date(Math.max(...MOVES.flatMap(m => m.ev.filter(e => e.kind !== 'SNAP').map(e => +e.d)), 0)))}</div><div class="d">từ ghi chú</div></div></div>
    <div class="panel"><div class="scroll"><table class="t" id="mvT"><thead><tr><th>Style</th><th>Tên</th><th>Đường đi nhà máy</th><th>Sự kiện</th><th class="r">SL</th></tr></thead><tbody>
    ${MOVES.map(m => `<tr class="click" data-s="${m.s.s}" tabindex="0"><td style="font-family:var(--mono)">${m.s.s}</td><td>${esc(m.s.it)}</td>
      <td>${m.path.map((f, i) => i === m.path.length - 1 ? `<b>${esc(f)}</b>` : esc(f)).join(' → ')}</td>
      <td>${m.ev.filter(e => e.kind !== 'SNAP').map(e => `${ddy(e.d)} ${e.kind === 'MOVED' ? 'chuyển' : 'chốt'}${e.f ? ' ' + esc(e.f) : ''}`).join('<br>') || '<span class="muted">chỉ thấy qua snapshot</span>'}</td>
      <td class="r num">${fmt(m.s.q)}</td></tr>`).join('')}</tbody></table></div>
    <p class="muted" style="font-size:12px;margin-top:10px">Theo TGĐ Kim Dae Woo, nguyên tắc là không nên có chuyển nhà máy. Mỗi lần chuyển sẽ yêu cầu chọn lý do (lệch lịch, năng lực, chất lượng) khi nhập trên KOPS.</p></div>`;
  $('#mvT').addEventListener('click', e => { const tr = e.target.closest('tr[data-s]'); if (tr) styleDrawer(tr.dataset.s); });
};

pages.dw.progress = main => {
  const open = FW.map(s => ({ s, r: styleStatus(s) })).filter(x => x.s.shp < x.s.q * 0.98);
  const late = open.filter(x => x.r.tone === 'bad');
  const noTop = FW.filter(s => !s.top && s.etdD && days(s.etdD, TODAY) <= 14 && s.shp < s.q * 0.98);
  main.innerHTML = `<div class="ph"><div><h2>Tiến độ &amp; cảnh báo</h2><p>Ngày hoàn thành dự kiến = SL còn lại ÷ sản lượng/ngày (bỏ Chủ nhật) + 5 ngày hoàn thiện và kiểm, theo cách tính MR đang dùng. Khi nhà máy chưa báo sản lượng ngày, giả định 45 pcs/ngày.</p></div></div>
    <div class="kpis" style="grid-template-columns:repeat(4,1fr)">
      <div class="kpi"><div class="k">Style chưa xuất đủ</div><div class="v num">${open.length}</div><div class="d">${fmt(sum(open, x => x.s.q - x.s.shp))} pcs còn lại</div></div>
      <div class="kpi"><div class="k">Nguy cơ trễ ETD</div><div class="v num" style="color:var(--bad)">${late.length}</div><div class="d">cần báo buyer / xin AIR</div></div>
      <div class="kpi"><div class="k">Thiếu TOP sample, ETD ≤14 ngày</div><div class="v num">${noTop.length}</div><div class="d">nhắc QA nhà máy</div></div>
      <div class="kpi"><div class="k">Báo cáo sản lượng ngày</div><div class="v num">${FW.filter(s => s.day > 0).length}</div><div class="d">style có số hôm nay</div></div></div>
    <div class="panel"><h3>Style đang mở</h3><div class="scroll"><table class="t" id="pgT"><thead><tr><th>Style</th><th>Nhà máy</th><th>ETD</th><th style="min-width:200px">Đặt / may / kiểm / xuất</th><th>Dự kiến sẵn sàng</th><th>Cảnh báo</th></tr></thead><tbody>
    ${open.sort((a, b) => (b.r.proj?.late ?? -99) - (a.r.proj?.late ?? -99)).map(({ s, r }) => `<tr class="click" data-s="${s.s}" tabindex="0">
      <td><span style="font-family:var(--mono)">${s.s}</span><br><small class="muted">${esc(s.no)} · ${esc(s.it)}</small></td><td>${esc(s.factory)}</td><td>${ddy(s.etdD)}</td>
      <td><div class="hb" style="grid-template-columns:1fr"><div class="track"><i class="b2" style="width:${100 * s.out / s.q}%"></i><i style="width:${100 * s.shp / s.q}%"></i></div></div>
        <small class="num">${fmt(s.q)} / ${fmt(s.out)} / ${fmt(s.ins)} / ${fmt(s.shp)}</small></td>
      <td>${r.proj ? `${ddy(r.proj.ready)}<br><small class="muted">${r.proj.rate} pcs/ngày${r.proj.assumed ? ' (giả định)' : ''}</small>` : '<small class="muted">đã may xong</small>'}</td>
      <td><span class="pill ${r.tone}">${esc(r.label)}</span>${!s.top ? '<br><small class="muted">chưa có TOP sample</small>' : ''}</td></tr>`).join('')}
    </tbody></table></div></div>`;
  $('#pgT').addEventListener('click', e => { const tr = e.target.closest('tr[data-s]'); if (tr) styleDrawer(tr.dataset.s); });
};

pages.dw.model = main => {
  const ent = (n, cols, cls = '') => `<div class="ent ${cls}"><b>${n}</b>${cols.map(c => `<span>${c}</span>`).join('')}</div>`;
  main.innerHTML = `<div class="ph"><div><h2>Mô hình kho dữ liệu</h2><p>Star schema trên PostgreSQL (schema <code>dw</code>), nạp bằng dbt từ schema <code>core</code> đã thiết kế ở bước phân tích. DDL đầy đủ: <code>dw_schema.sql</code>.</p></div></div>
    <div class="panel"><div class="star">
      <div class="col">${ent('dim_date', ['date_key PK', 'date, iso_week', 'season_code'])}${ent('dim_style', ['style_key PK', 'style_no', 'item_type, gender', 'desc_en, name_kr', 'valid_from / valid_to'], 'scd')}${ent('dim_partner', ['partner_key PK', 'type: FACTORY / SUPPLIER / BRAND', 'name, region'])}</div>
      <div class="col">${ent('fact_order_line', ['style_key, color, size', 'season_key, factory_key', 'order_qty'], 'fact')}${ent('fact_shipment_line', ['ship_date_key, eta_key', 'style_key, factory_key', 'mode, qty, is_sample'], 'fact')}${ent('fact_production_daily', ['date_key, style_key, factory_key', 'cut, input, output, inspected', 'plan_output'], 'fact')}${ent('fact_inspection', ['date_key, style_key, factory_key', 'inspector_key, brand_key', 'lot, sample, major, minor, result', 'returned_qty, claim_qty'], 'fact')}</div>
      <div class="col">${ent('dim_factory_assignment', ['style_key, factory_key', 'valid_from / valid_to', 'is_current, reason, source'], 'scd')}${ent('dim_season', ['season_key PK', 'brand, code, half'])}${ent('dim_inspector', ['inspector_key PK', 'region, specialty'])}</div>
    </div></div>
    <div class="g2"><div class="panel"><h3>Cách trả lời các câu hỏi trong brief</h3><table class="t"><tbody>
      <tr><td>Lịch sử đơn &amp; mẫu mã cũ</td><td><code>fact_order_line</code> × <code>dim_style</code> (SCD2 giữ mô tả, màu theo thời điểm)</td></tr>
      <tr><td>Lịch sử đổi nhà máy của lô</td><td><code>dim_factory_assignment</code> SCD2: mỗi lần đổi đóng dòng cũ, mở dòng mới kèm lý do</td></tr>
      <tr><td>Tiến độ</td><td><code>fact_production_daily</code> + <code>fact_shipment_line</code>, so với ETD/RDD trong <code>dim_style</code></td></tr>
      <tr><td>% return theo đối tác</td><td><code>fact_inspection</code>: (returned + claim) ÷ inspected, nhóm theo <code>dim_partner</code></td></tr></tbody></table></div>
      <div class="panel"><h3>Luồng dữ liệu</h3><ol style="margin:0;padding-left:20px;font-size:14px;color:var(--ink-2)">
      <li>Excel / app KOPS → <code>raw</code> (giữ nguyên ô gốc, có hash file)</li><li>Parser + AI nhận dạng minimap → <code>core</code> (OLTP, có ràng buộc)</li>
      <li>dbt chạy mỗi giờ → <code>dw</code> (star schema, snapshot SCD2)</li><li>Dashboard buyer, báo cáo nội bộ, trợ lý AI chỉ đọc <code>dw</code> và view được phân quyền</li></ol></div></div>`;
};
