# -*- coding: utf-8 -*-
"""Fast, restartable page importer using MediaWiki's page-updater API.

Every page is passed as a file through the CLI runner; shell quoting, XML
escaping and game HTML cannot change the source text.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import argparse
import json
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--new-only", action="store_true", help="Skip existing pages")
    ap.add_argument("--all", action="store_true", help="Import all pages, not only prior errors")
    args = ap.parse_args()
    manifest = json.loads((ROOT / "build/pages.json").read_text(encoding="utf-8"))
    if not args.all and (ROOT / "build/import-errors.json").exists():
        previous = json.loads((ROOT / "build/import-errors.json").read_text(encoding="utf-8"))
        failed_titles = {p["title"] for p in previous}
        if failed_titles:
            manifest = [p for p in manifest if p["title"] in failed_titles]
            print(f"Retrying {len(manifest)} previously failed pages",flush=True)
    if args.limit:
        manifest = manifest[:args.limit]
    count = 0
    failed = []
    lock = threading.Lock()
    started = time.time()
    compose = ["docker", "compose", "-f", str(ROOT / "compose.yaml"), "exec", "-T", "mediawiki"]

    def import_page(page):
        command = compose + ["php", "maintenance/run.php", "edit.php", "--user=WikiAdmin",
                             "--summary=" + page["comment"], "--no-rc"]
        if args.new_only:
            command.append("--createonly")
        command += ["--", page["title"]]
        with (ROOT / "build/pages" / page["file"]).open("rb") as data:
            return subprocess.run(command, stdin=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  cwd=ROOT, timeout=180)

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(import_page,page):page for page in manifest}
        for future in as_completed(futures):
            page = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                failed.append({"title":page["title"],"error":str(exc)})
                continue
            if result.returncode:
                failed.append({"title":page["title"],"error":result.stderr.decode("utf-8",errors="replace")[-1000:]})
            with lock:
                count += 1
                if count % 250 == 0:
                    print(f"{count}/{len(manifest)} pages; {count/(time.time()-started):.1f} pages/s; errors={len(failed)}",flush=True)
    (ROOT / "build/import-errors.json").write_text(json.dumps(failed,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Imported {count-len(failed)}/{len(manifest)}; errors={len(failed)}; elapsed={time.time()-started:.0f}s",flush=True)
    if failed:
        print(json.dumps(failed[:10],ensure_ascii=False,indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
