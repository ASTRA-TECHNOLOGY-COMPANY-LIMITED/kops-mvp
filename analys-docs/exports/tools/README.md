# Export open_questions -> DOCX/PDF

Regenerate whenever `analys-docs/open_questions.md` changes. The internal appendix (`# Phụ lục`) is excluded automatically. Priority chips come from the `# Ưu tiên 1/2/3` headings.

```bash
cd analys-docs/exports
python3 tools/parse.py ../open_questions.md /tmp/blocks.json
SEND_DATE=19/10/2026 node tools/render.js /tmp/blocks.json KOPS_Tai_lieu_cau_hoi_nghiep_vu_2026-10-19.docx   # needs: npm i docx; SEND_DATE defaults to today
soffice --headless --convert-to pdf KOPS_Tai_lieu_cau_hoi_nghiep_vu_2026-10-19.docx
```
