/* ===================== shared data & utils ===================== */
const RAW = JSON.parse(document.getElementById('kops-data').textContent);
const TODAY = new Date('2026-10-12T00:00:00');
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = n => (n == null || isNaN(n)) ? '–' : Math.round(n).toLocaleString('vi-VN');
const pct = (a, b, d = 0) => b ? (100 * a / b).toFixed(d) + '%' : '–';
const D = s => { if (!s || !/^\d{4}-\d{2}-\d{2}/.test(s)) return null; return new Date(s.slice(0,10) + 'T00:00:00'); };
const dd = d => d ? `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}` : '–';
const ddy = d => d ? `${dd(d)}/${d.getFullYear()}` : '–';
const days = (a, b) => Math.round((a - b) / 864e5);
const addDays = (d, n) => new Date(d.getTime() + n * 864e5);
function addWorkdays(d, n) { let x = new Date(d); while (n > 0) { x = addDays(x, 1); if (x.getDay() !== 0) n--; } return x; } // garment lines work Mon–Sat
function toast(msg) { const t = $('#toast'); t.textContent = msg; t.classList.add('on'); clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove('on'), 2600); }
function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

/* factory name master + aliases (DQ-15 in analysis) */
const FACTORY_ALIAS = {
  'TBM':'TAN BINH MINH','FG':'FG BAC GIANG','TAN BINH MINH':'TAN BINH MINH','TAN BINH MINH PLAN':'TAN BINH MINH','FG VINA -> TBM':'TAN BINH MINH',
  'DM':'DONG MY','DONG MY':'DONG MY','TP':'TRUONG PHUC','TRUONG PHUC':'TRUONG PHUC','TRUONG PHUC TV':'TRUONG PHUC',
  'TIẾN THÀNH':'TIEN THANH','TIEN THANH':'TIEN THANH','FG VINA':'FG BAC GIANG','FG BAC GIANG':'FG BAC GIANG',
  'MTT':'MTT','NATEXCO':'NATEXCO','HA HIEU':'HA HIEU','JM':'JM','SON HA':'SON HA'
};
const nf = x => { const k = (x || '').trim().toUpperCase(); return FACTORY_ALIAS[k] || k; };
const FACTORY_INFO = {
  'TAN BINH MINH':{code:'TBM',region:'Thanh Hóa'}, 'DONG MY':{code:'DM',region:'Hà Nội'}, 'TRUONG PHUC':{code:'TP',region:'Nam Định'},
  'MTT':{code:'MTT',region:'Thái Bình'}, 'NATEXCO':{code:'NTC',region:'Nam Định'}, 'HA HIEU':{code:'HH',region:'Hải Dương'},
  'TIEN THANH':{code:'TT',region:'Hưng Yên'}, 'FG BAC GIANG':{code:'FG',region:'Bắc Giang'}, 'JM':{code:'JM',region:'Hà Nam'}, 'SON HA':{code:'SH',region:'Phú Thọ'}
}; // region values are placeholders for the prototype

/* ---- shipment label parser: "8/12ETD-8/18ETA SEA", "9/5 SHIPPING BY HC" ---- */
function parseShip(label, year = 2026) {
  const L = label.toUpperCase();
  let m = L.match(/(\d{1,2})\/(\d{1,2})\s*ETD\s*-\s*(\d{1,2})\/(\d{1,2})\s*ETA\s*(SEA|AIR|HC)?/);
  const mode = (L.match(/\b(SEA|AIR|HC)\b/) || [])[1] || 'SEA';
  if (m) { const etd = new Date(year, m[1]-1, +m[2]), eta = new Date(year, m[3]-1, +m[4]); return { etd, eta, mode, review: eta < etd }; }
  m = L.match(/(\d{1,2})\/(\d{1,2})/);
  if (m) { const d = new Date(year, m[1]-1, +m[2]); return { etd: d, eta: d, mode, review: false }; }
  return { etd: null, eta: null, mode, review: true };
}

/* ---- normalise 26FW styles ---- */
const FW = RAW.fw.map(s => {
  const ships = s.sh.map(([label, qty]) => ({ label, qty, ...parseShip(label) })).sort((a, b) => (a.etd || 0) - (b.etd || 0));
  const shippedDetail = ships.reduce((a, b) => a + b.qty, 0);
  const shippedToDate = ships.filter(x => x.etd && x.etd <= TODAY).reduce((a, b) => a + b.qty, 0);
  ships.forEach(x => x.planned = !!(x.etd && x.etd > TODAY));
  return { ...s, shpF1: s.shp, shp: Math.max(s.shp, shippedToDate), season:'26FW', factory: nf(s.f), etdD: D(s.etd), rddD: D(s.rdd), ships, shippedDetail,
    colors: s.c, item2: s.s.slice(5,7), gender: s.s[4] };
});
const SS = RAW.ss.map(s => ({ ...s, season:'27SS', factory: /CANCEL/i.test(s.f) ? '' : nf(s.f), cancelled: /CANCEL/i.test(s.f) || s.q === 0,
  etdD: D(s.etd), item2: s.s.slice(5,7), gender: s.s[4] }));
const ALL = [...FW, ...SS];
const ITEM = { JK:'Áo khoác', VT:'Áo gile', WT:'Áo dệt thoi', LT:'Áo thun dài tay', ST:'Áo thun ngắn tay', PT:'Quần dài', SK:'Váy', HP:'Quần short', OP:'Đầm', IT:'Áo lót trong', MK:'Khẩu trang', HC:'Mũ', GW:'Khăn cổ', CP:'Mũ lưỡi trai' };

/* ---- per-style status (shared by landing tracker, DW, chat) ---- */
function styleStatus(s) {
  const q = s.q || 0, near = v => v >= q * 0.98;
  const firstShip = s.ships && s.ships[0], lastShip = s.ships && s.ships[s.ships.length - 1];
  const st = [
    { k:'order', vi:'Xác nhận đơn', ko:'오더 확정', done:true, date:null },
    { k:'fpp', vi:'Duyệt FPP', ko:'FPP 컨펌', done:!!s.fpp, date:D(s.fpp), raw:s.fpp },
    { k:'inline', vi:'Mẫu inline', ko:'인라인 샘플', done:!!s.inl, raw:s.inl },
    { k:'cut', vi:'Cắt vải', ko:'재단', done:!!D(s.cut) && D(s.cut) <= TODAY, date:D(s.cut) },
    { k:'sew', vi:'May xong', ko:'봉제 완료', done:near(s.out), date:D(s.sew) },
    { k:'insp', vi:'Kiểm hàng', ko:'검사', done:near(s.ins) },
    { k:'ship', vi:'Xuất hàng', ko:'선적', done:near(s.shp), date:firstShip ? firstShip.etd : null },
    { k:'rdd', vi:'Về kho Hàn', ko:'창고 입고', done: lastShip && near(s.shp) && addDays(lastShip.eta, 5) <= TODAY, date:s.rddD }
  ];
  const now = st.findIndex(x => !x.done);
  // projection per meeting rule: remaining ÷ daily output (+Sundays off) + 5 days finishing/inspection
  let proj = null;
  if (s.out < q * 0.98) {
    const rate = s.day > 0 ? s.day : 45;
    const finish = addWorkdays(TODAY, Math.ceil((q - s.out) / rate));
    const ready = addDays(finish, 5);
    proj = { rate, assumed: !(s.day > 0), finish, ready, late: s.etdD ? days(ready, s.etdD) : null };
  }
  let tone = 'good', label = 'Đã xuất đủ';
  if (now === -1) { tone = 'good'; label = 'Hoàn tất'; }
  else if (st[now].k === 'rdd') { tone = 'good'; label = 'Đang trên đường về kho'; }
  else if (proj && proj.late > 0) { tone = 'bad'; label = `Trễ dự kiến ${proj.late} ngày`; }
  else if (s.etdD && s.etdD < TODAY && !near(s.shp)) { tone = 'bad'; label = 'Quá ETD, chưa xuất đủ'; }
  else { tone = 'warn'; label = 'Đang sản xuất'; }
  return { st, now, proj, tone, label };
}

/* ===================== router ===================== */
const pages = { dw: {}, qc: {} };
function route() {
  const h = location.hash || '#/site';
  const [, mod, page] = h.split('/');
  const isSiteAnchor = !h.startsWith('#/');
  const m = isSiteAnchor ? 'site' : (mod || 'site');
  $$('.view').forEach(v => v.classList.toggle('on', v.id === 'v-' + m));
  $$('.switcher a').forEach(a => a.setAttribute('aria-current', a.dataset.mod === m));
  closeDrawer();
  if (m === 'dw' || m === 'qc') {
    const p = page || Object.keys(pages[m])[0];
    $$(`#v-${m} .side a`).forEach(a => a.setAttribute('aria-current', a.dataset.page === p));
    const main = $(m === 'dw' ? '#dwMain' : '#qcMain');
    main.innerHTML = '';
    (pages[m][p] || (() => main.innerHTML = '<p>Không có trang.</p>'))(main);
    window.scrollTo(0, 0);
  }
}
window.addEventListener('hashchange', route);

/* theme toggle */
$('#themeBtn').addEventListener('click', () => {
  const r = document.documentElement, dark = r.dataset.theme ? r.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  r.dataset.theme = dark ? 'light' : 'dark';
});

/* drawer */
function openDrawer(html) { $('#drawerBody').innerHTML = html; const d = $('#drawer'); d.classList.add('on'); d.setAttribute('aria-hidden', 'false'); $('#drawerX').focus(); }
function closeDrawer() { const d = $('#drawer'); d.classList.remove('on'); d.setAttribute('aria-hidden', 'true'); }
$('#drawerX').addEventListener('click', closeDrawer);
document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeDrawer(); $('#chat').classList.remove('on'); } });

/* tiny horizontal bar chart */
function hbars(rows, opts = {}) {
  const max = opts.max || Math.max(...rows.map(r => Math.max(r.a || 0, r.b || 0)), 1);
  return `<div class="hb">${rows.map(r => `
    <div title="${esc(r.label)}" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(r.label)}</div>
    <div class="track" role="img" aria-label="${esc(r.label)}: ${esc(r.text || fmt(r.a))}">
      ${r.b != null ? `<i class="b2" style="width:${100 * r.b / max}%"></i>` : ''}
      <i class="${r.cls || ''}" style="width:${100 * (r.a || 0) / max}%"></i></div>
    <div class="num" style="text-align:right">${esc(r.text ?? fmt(r.a))}</div>`).join('')}</div>`;
}
