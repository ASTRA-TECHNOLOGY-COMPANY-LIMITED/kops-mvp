const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  AlignmentType, HeadingLevel, LevelFormat, Header, Footer, PageNumber, PageBreak, TableLayoutType,
  VerticalAlign, HeightRule,
} = require("docx");

const blocks = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const OUT = process.argv[3];

// ---------- design tokens ----------
const FONT = { ascii: "Arial", hAnsi: "Arial", cs: "Arial", eastAsia: "Malgun Gothic" };
const MONO = { ascii: "Consolas", hAnsi: "Consolas", eastAsia: "Malgun Gothic" };
const C = {
  ink: "1A1A1A", ink2: "4A4A48", ink3: "7A7974", navy: "1F3A5F", line: "D9D7D0", soft: "F4F3F0",
  head: "E8EDF4", answerLine: "D99A00", answerBg: "FFF8E6",
};
const PRIO = {
  p1: { label: "ƯU TIÊN 1 · QUAN TRỌNG NHẤT", short: "ƯU TIÊN 1", fg: "B3261E", bg: "FBE9E7" },
  p2: { label: "ƯU TIÊN 2 · CẦN CHO GIAI ĐOẠN 1", short: "ƯU TIÊN 2", fg: "1F5FA8", bg: "E3EEFB" },
  p3: { label: "ƯU TIÊN 3 · CÓ THỂ TRẢ LỜI SAU", short: "ƯU TIÊN 3", fg: "5F5E5A", bg: "EFEEEA" },
};
const TITLE = "Tài liệu câu hỏi nghiệp vụ";
// send date: SEND_DATE=dd/mm/yyyy, default today
const SEND = process.env.SEND_DATE || new Date().toLocaleDateString("en-GB");
const YEAR = SEND.slice(-4);
const PAGE_W = 11906, MARGIN = 1134, CONTENT_W = PAGE_W - 2 * MARGIN; // A4, 2 cm margins

function prioOf(tier) {
  if (tier && tier.startsWith("Ưu tiên 1")) return PRIO.p1;
  if (tier && tier.startsWith("Ưu tiên 2")) return PRIO.p2;
  return PRIO.p3;
}

function textRuns(runs, base = {}) {
  return runs.map((r) => new TextRun({
    text: r.t,
    bold: r.b || base.bold,
    italics: r.i || base.italics,
    font: r.code ? MONO : FONT,
    size: r.code ? (base.size || 20) - 2 : base.size || 20,
    color: r.code ? C.navy : base.color || C.ink,
    shading: r.code ? { type: ShadingType.CLEAR, fill: "EEF1F5", color: "auto" } : undefined,
  }));
}

const thin = { style: BorderStyle.SINGLE, size: 4, color: C.line };
const cellBorders = { top: thin, bottom: thin, left: thin, right: thin };

function mdTable(rows, indent) {
  const ncol = Math.max(...rows.map((r) => r.length));
  const width = CONTENT_W - (indent ? 360 : 0);
  // column widths proportional to longest text (clamped)
  const len = Array.from({ length: ncol }, (_, c) =>
    Math.min(60, Math.max(9, ...rows.map((r) => (r[c] || []).map((x) => x.t).join("").length))));
  const sum = len.reduce((a, b) => a + b, 0);
  const widths = len.map((l) => Math.floor((l / sum) * width));
  widths[ncol - 1] += width - widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: width, type: WidthType.DXA },
    columnWidths: widths,
    indent: indent ? { size: 360, type: WidthType.DXA } : undefined,
    layout: TableLayoutType.FIXED,
    rows: rows.map((r, ri) => new TableRow({
      tableHeader: ri === 0,
      cantSplit: true,
      children: Array.from({ length: ncol }, (_, c) => new TableCell({
        width: { size: widths[c], type: WidthType.DXA },
        borders: cellBorders,
        shading: ri === 0 ? { type: ShadingType.CLEAR, fill: C.head, color: "auto" } : undefined,
        margins: { top: 60, bottom: 60, left: 90, right: 90 },
        children: [new Paragraph({ keepNext: ri < rows.length - 1, spacing: { after: 0 }, children: textRuns(r[c] || [], { size: 17, bold: ri === 0, color: ri === 0 ? C.navy : C.ink }) })],
      })),
    })),
  });
}

function answerBox(qid) {
  const w = CONTENT_W;
  const amber = { style: BorderStyle.SINGLE, size: 12, color: C.answerLine };
  const borders = { top: amber, bottom: amber, left: amber, right: amber };
  return new Table({
    width: { size: w, type: WidthType.DXA },
    columnWidths: [w],
    layout: TableLayoutType.FIXED,
    rows: [
      new TableRow({ cantSplit: true, children: [new TableCell({
        width: { size: w, type: WidthType.DXA }, borders,
        shading: { type: ShadingType.CLEAR, fill: C.answerBg, color: "auto" },
        margins: { top: 80, bottom: 80, left: 140, right: 140 },
        children: [new Paragraph({ keepNext: true, keepLines: true, spacing: { after: 0 }, children: [
          new TextRun({ text: `TRẢ LỜI CỦA KLMAS — ${qid}`, bold: true, font: FONT, size: 18, color: "8A5A00" }),
          new TextRun({ text: "   (điền trực tiếp vào ô bên dưới)", font: FONT, size: 16, color: C.ink3 }),
        ] })],
      })] }),
      new TableRow({ cantSplit: true, height: { value: 1900, rule: HeightRule.ATLEAST }, children: [new TableCell({
        width: { size: w, type: WidthType.DXA }, borders,
        margins: { top: 100, bottom: 100, left: 140, right: 140 },
        children: [new Paragraph({ keepNext: true, children: [new TextRun({ text: "", font: FONT, size: 20 })] })],
      })] }),
      new TableRow({ cantSplit: true, children: [new TableCell({
        width: { size: w, type: WidthType.DXA }, borders,
        margins: { top: 70, bottom: 70, left: 140, right: 140 },
        children: [new Paragraph({ spacing: { after: 0 }, children: [
          new TextRun({ text: `Người trả lời: ................................................        Ngày: ......../......../${YEAR}`, font: FONT, size: 16, color: C.ink3 }),
        ] })],
      })] }),
    ],
  });
}

function questionHeading(b) {
  const p = prioOf(b.tier);
  const out = [];
  out.push(new Paragraph({
    keepNext: true, spacing: { before: 280, after: 60 },
    children: [new TextRun({ text: ` ${p.label} `, bold: true, font: FONT, size: 14, color: p.fg,
      shading: { type: ShadingType.CLEAR, fill: p.bg, color: "auto" } }),
      ...(b.note ? [new TextRun({ text: `   ${b.note}`, italics: true, font: FONT, size: 16, color: C.ink3 })] : [])],
  }));
  out.push(new Paragraph({
    heading: HeadingLevel.HEADING_3, keepNext: true, spacing: { before: 0, after: 120 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: C.line, space: 4 } },
    children: [
      new TextRun({ text: `${b.id}  `, bold: true, font: FONT, size: 24, color: p.fg }),
      new TextRun({ text: b.title, bold: true, font: FONT, size: 24, color: C.navy }),
    ],
  }));
  return out;
}

// ---------- cover ----------
const qs = blocks.filter((b) => b.k === "q");
const count = (pr) => qs.filter((q) => prioOf(q.tier) === pr).length;
const cover = [
  new Paragraph({ spacing: { before: 1800, after: 120 }, children: [new TextRun({ text: "KOPS · KLMAS Order & Production System", font: FONT, size: 22, color: C.ink3 })] }),
  new Paragraph({ spacing: { after: 160 }, children: [new TextRun({ text: TITLE, bold: true, font: FONT, size: 56, color: C.navy })] }),
  new Paragraph({ spacing: { after: 600 }, border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: C.navy, space: 8 } },
    children: [new TextRun({ text: "Gửi KLMAS điền câu trả lời để ASTRA hoàn thiện giai đoạn 1 của hệ thống KOPS", font: FONT, size: 26, color: C.ink2 })] }),
];
const infoRows = [
  ["Ngày gửi", SEND], ["Bên gửi", "ASTRA TECHNOLOGY"], ["Bên trả lời", "KLMAS"],
  ["Người phụ trách trả lời", ""], ["Ngày gửi lại", ""],
];
const infoW = [3200, CONTENT_W - 3200];
cover.push(new Table({
  width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: infoW, layout: TableLayoutType.FIXED,
  rows: infoRows.map(([k, v]) => new TableRow({ height: { value: 480, rule: HeightRule.ATLEAST }, children: [
    new TableCell({ width: { size: infoW[0], type: WidthType.DXA }, borders: cellBorders, verticalAlign: VerticalAlign.CENTER,
      shading: { type: ShadingType.CLEAR, fill: C.soft, color: "auto" }, margins: { left: 140, right: 140 },
      children: [new Paragraph({ spacing: { after: 0 }, children: [new TextRun({ text: k, bold: true, font: FONT, size: 20, color: C.ink2 })] })] }),
    new TableCell({ width: { size: infoW[1], type: WidthType.DXA }, borders: cellBorders, verticalAlign: VerticalAlign.CENTER, margins: { left: 140, right: 140 },
      children: [new Paragraph({ spacing: { after: 0 }, children: [new TextRun({ text: v, font: FONT, size: 20 })] })] }),
  ] })),
}));
cover.push(new Paragraph({ spacing: { before: 480, after: 160 }, children: [new TextRun({ text: "Tổng quan", bold: true, font: FONT, size: 26, color: C.navy })] }));
const ov = [
  [PRIO.p1, count(PRIO.p1), "Trả lời trước tiên. Hiểu sai thì con số chính trên dashboard sẽ sai."],
  [PRIO.p2, count(PRIO.p2), "Trả lời ngay khi có thể, không cần chờ buổi demo. Đúng với dòng \"ASTRA đang hiểu\" thì chỉ cần ghi \"Đúng\"."],
  [PRIO.p3, count(PRIO.p3), "Giai đoạn 1 chưa cần. Câu nào biết ngay thì trả lời luôn; ASTRA sẽ hỏi lại các câu còn lại sau."],
];
const ovW = [3000, 1000, CONTENT_W - 4000];
cover.push(new Table({
  width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: ovW, layout: TableLayoutType.FIXED,
  rows: ov.map(([p, n, d]) => new TableRow({ children: [
    new TableCell({ width: { size: ovW[0], type: WidthType.DXA }, borders: cellBorders, shading: { type: ShadingType.CLEAR, fill: p.bg, color: "auto" }, verticalAlign: VerticalAlign.CENTER, margins: { top: 80, bottom: 80, left: 140, right: 140 },
      children: [new Paragraph({ spacing: { after: 0 }, children: [new TextRun({ text: p.label, bold: true, font: FONT, size: 17, color: p.fg })] })] }),
    new TableCell({ width: { size: ovW[1], type: WidthType.DXA }, borders: cellBorders, verticalAlign: VerticalAlign.CENTER,
      children: [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 0 }, children: [new TextRun({ text: `${n} câu`, bold: true, font: FONT, size: 20 })] })] }),
    new TableCell({ width: { size: ovW[2], type: WidthType.DXA }, borders: cellBorders, verticalAlign: VerticalAlign.CENTER, margins: { top: 80, bottom: 80, left: 140, right: 140 },
      children: [new Paragraph({ spacing: { after: 0 }, children: [new TextRun({ text: d, font: FONT, size: 18, color: C.ink2 })] })] }),
  ] })),
}));
cover.push(new Paragraph({ children: [new PageBreak()] }));

// ---------- question index ----------
const idx = [new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { after: 160 }, children: [new TextRun({ text: "Danh sách câu hỏi", bold: true, font: FONT, size: 32, color: C.navy })] })];
const idxW = [900, CONTENT_W - 900 - 1500, 1500];
idx.push(new Table({
  width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: idxW, layout: TableLayoutType.FIXED,
  rows: [["Mã", "Câu hỏi", "Mức"], ...qs.map((q) => [q.id, q.title, prioOf(q.tier)])].map((r, ri) => new TableRow({
    tableHeader: ri === 0, cantSplit: true,
    children: r.map((v, ci) => new TableCell({
      width: { size: idxW[ci], type: WidthType.DXA }, borders: cellBorders,
      shading: ri === 0 ? { type: ShadingType.CLEAR, fill: C.head, color: "auto" } : (ci === 2 ? { type: ShadingType.CLEAR, fill: v.bg, color: "auto" } : undefined),
      margins: { top: 40, bottom: 40, left: 90, right: 90 },
      children: [new Paragraph({ spacing: { after: 0 }, children: [new TextRun({
        text: ci === 2 && ri > 0 ? v.short : v, bold: ri === 0 || ci !== 1, font: FONT, size: ci === 2 ? 14 : 17,
        color: ri === 0 ? C.navy : (ci === 2 ? v.fg : C.ink) })] })],
    })),
  })),
}));
idx.push(new Paragraph({ children: [new PageBreak()] }));

// ---------- body ----------
const body = [];
let qIndex = 0, skipFirstH1 = true, justQ = false;
for (const b of blocks) {
  const wasQ = justQ; justQ = false;
  if (b.k === "h1") {
    if (skipFirstH1) { skipFirstH1 = false; body.push(new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { after: 160 }, children: [new TextRun({ text: "Hướng dẫn trả lời", bold: true, font: FONT, size: 32, color: C.navy })] })); continue; }
    body.push(new Paragraph({ pageBreakBefore: true, heading: HeadingLevel.HEADING_1, spacing: { after: 160 },
      border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: C.navy, space: 6 } },
      children: [new TextRun({ text: b.text, bold: true, font: FONT, size: 32, color: C.navy })] }));
  } else if (b.k === "h2") {
    body.push(new Paragraph({ heading: HeadingLevel.HEADING_2, keepNext: true, spacing: { before: 320, after: 120 },
      children: [new TextRun({ text: b.text, bold: true, font: FONT, size: 26, color: C.navy })] }));
  } else if (b.k === "q") {
    qIndex++;
    body.push(...questionHeading(b));
    justQ = true; continue;
  } else if (b.k === "p") {
    body.push(new Paragraph({ spacing: { after: 120, line: 288 }, children: textRuns(b.runs) }));
  } else if (b.k === "note") {
    body.push(new Paragraph({ spacing: { after: 120 }, indent: { left: 240 }, border: { left: { style: BorderStyle.SINGLE, size: 12, color: C.line, space: 8 } }, children: textRuns(b.runs, { color: C.ink2 }) }));
  } else if (b.k === "li") {
    const isAssume = b.runs.length && b.runs[0].i && /^(Tạm hiểu|ASTRA đang hiểu)/.test(b.runs[0].t);
    const base = isAssume ? { color: C.ink2, size: 19 } : {};
    if (b.num) {   // literal numbers: list numbering restarts are unreliable across Word/LibreOffice
      body.push(new Paragraph({
        spacing: { after: 70, line: 276 }, indent: { left: 360 + b.lvl * 360 + 320, hanging: 300 },
        children: [new TextRun({ text: `${b.num}.\t`, font: FONT, size: 20, color: C.ink2 }), ...textRuns(b.runs, base)],
        tabStops: [{ type: "left", position: 360 + b.lvl * 360 + 320 }],
      }));
      continue;
    }
    body.push(new Paragraph({
      numbering: { reference: "bullets", level: b.lvl },
      spacing: { after: 70, line: 276 }, keepNext: wasQ,
      shading: isAssume ? { type: ShadingType.CLEAR, fill: C.soft, color: "auto" } : undefined,
      children: textRuns(b.runs, base),
    }));
  } else if (b.k === "table") {
    body.push(mdTable(b.rows, b.indent));
    body.push(new Paragraph({ spacing: { after: 80 }, children: [] }));
  } else if (b.k === "code") {
    for (const l of b.lines) body.push(new Paragraph({ spacing: { after: 0 }, children: [new TextRun({ text: l || " ", font: MONO, size: 16, color: C.navy })] }));
  } else if (b.k === "answer") {
    body.push(new Paragraph({ spacing: { before: 80, after: 0 }, keepNext: true, children: [] }));
    body.push(answerBox(qs[qIndex - 1].id));
    body.push(new Paragraph({ spacing: { after: 160 }, children: [] }));
  }
}

const bulletLevels = [0, 1, 2].map((l) => ({
  level: l, format: LevelFormat.BULLET, text: ["•", "–", "·"][l], alignment: AlignmentType.LEFT,
  style: { paragraph: { indent: { left: 360 + l * 360, hanging: 240 } }, run: { font: FONT, color: C.ink2 } },
}));
const numLevels = [0, 1, 2].map((l) => ({
  level: l, format: LevelFormat.DECIMAL, text: `%${l + 1}.`, alignment: AlignmentType.LEFT,
  style: { paragraph: { indent: { left: 360 + l * 360, hanging: 280 } }, run: { font: FONT } },
}));

const doc = new Document({
  creator: "ASTRA TECHNOLOGY", title: `KOPS — ${TITLE}`,
  styles: { default: { document: { run: { font: FONT, size: 20, color: C.ink } } } },
  numbering: { config: [{ reference: "bullets", levels: bulletLevels }, { reference: "nums", levels: numLevels }] },
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: 16838 }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN, header: 560, footer: 560 } }, titlePage: true },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: `KOPS · ${TITLE} · ${SEND}`, font: FONT, size: 16, color: C.ink3 })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
      new TextRun({ text: "ASTRA TECHNOLOGY  ·  Trang ", font: FONT, size: 16, color: C.ink3 }),
      new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: C.ink3 }),
      new TextRun({ text: " / ", font: FONT, size: 16, color: C.ink3 }),
      new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: 16, color: C.ink3 }),
    ] })] }) },
    children: [...cover, ...idx, ...body],
  }],
});
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT, buf.length); });
