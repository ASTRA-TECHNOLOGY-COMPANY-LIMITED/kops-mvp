import json,pathlib
S=pathlib.Path('src')
data=json.loads(pathlib.Path('proto_data.json').read_text())
dj=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
html=f'''<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KOPS Prototype</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700;800&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;600&family=Noto+Sans+KR:wght@400;600;700&display=swap" rel="stylesheet">
<style>
{(S/'styles.css').read_text()}
</style>
</head>
<body>
{(S/'body.html').read_text()}
<script id="kops-data" type="application/json">{dj}</script>
<script>
{(S/'core.js').read_text()}
{(S/'landing.js').read_text()}
{(S/'dw.js').read_text()}
{(S/'qc.js').read_text()}
</script>
</body>
</html>'''
out=pathlib.Path('KOPS_prototype.html'); out.write_text(html); print(out.stat().st_size)
