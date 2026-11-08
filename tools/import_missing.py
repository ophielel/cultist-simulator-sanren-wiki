# 导入校验报告列出的缺失页面。
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
verification = json.loads((ROOT / "build/verification.json").read_text(encoding="utf-8"))
missing = set(verification["missing"])
manifest = [p for p in json.loads((ROOT / "build/pages.json").read_text(encoding="utf-8")) if p["title"] in missing]
failed=[]
for page in manifest:
    cmd=["docker","compose","-f",str(ROOT/"compose.yaml"),"exec","-T","mediawiki",
         "php","maintenance/run.php","edit.php","--user=WikiAdmin","--summary=新增导航与路线索引",
         "--no-rc","--",page["title"]]
    with (ROOT/"build/pages"/page["file"]).open("rb") as stream:
        result=subprocess.run(cmd,stdin=stream,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode:
        failed.append({"title":page["title"],"error":result.stderr.decode("utf-8",errors="replace")})
print(f"Missing-page import: {len(manifest)-len(failed)}/{len(manifest)} succeeded")
if failed:
    print(json.dumps(failed,ensure_ascii=False,indent=2))
    sys.exit(1)
(ROOT/"build/import-errors.json").write_text("[]",encoding="utf-8")
