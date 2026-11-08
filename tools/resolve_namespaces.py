# 用 MediaWiki 的标题解析规则为生成页面设置正确命名空间。
import json
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent.parent
manifest = json.loads((ROOT / "build/pages.json").read_text(encoding="utf-8"))
titles = [p["title"] for p in manifest]
nsmap = {}
for i in range(0, len(titles), 50):
    chunk = titles[i:i+50]
    uri = "http://localhost:8090/api.php"
    import urllib.parse, urllib.request
    data = urllib.parse.urlencode({"action":"query","titles":"|".join(chunk),"format":"json"}).encode()
    with urllib.request.urlopen(uri,data=data,timeout=90) as response:
        obj = json.load(response)
    for page in obj["query"]["pages"].values():
        nsmap[page["title"]] = page["ns"]
for page in manifest:
    title = page["title"]
    ns = nsmap.get(title)
    if ns is None:
        # Canonicalization may replace underscores, but the file's exact title wins.
        ns = nsmap.get(title.replace("_", " "))
    if ns is None:
        raise ValueError(f"No namespace for {title}")
    page["ns"] = ns
    if ns == 10:
        page["content_model"] = "wikitext"
    elif title.startswith("原始数据:"):
        page["content_model"] = "wikitext"
    else:
        page["content_model"] = "wikitext"
(ROOT / "build/pages.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
print(f"Resolved {len(manifest)} namespaces: {len(nsmap)}")
