# -*- coding: utf-8 -*-
"""Parallel maintenance runner for the local, generated wiki pages."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent.parent


def run_in_container(script, page):
    command = ["docker", "run", "--rm", "--network", "wiki_wiki",
               "--volumes-from", "wiki-mediawiki-1", "--env-file", str(ROOT / ".env"),
               "--mount", f"type=bind,source={ROOT / 'tools' / script},target=/tmp/sanren-job.php,readonly",
               "--mount", f"type=bind,source={ROOT / 'build/pages.json'},target=/build/pages.json,readonly",
               "--entrypoint", "php", "mediawiki:1.43", "/tmp/sanren-job.php", str(page['ns'])]
    return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script", choices=["SanrenNamespaceFix.php", "SanrenRawModel.php"])
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    pages = json.loads((ROOT / "build/pages.json").read_text(encoding="utf-8"))
    by_ns = {}
    for page in pages:
        if args.script == "SanrenRawModel.php" and page["ns"] != 3000:
            continue
        by_ns.setdefault(page["ns"], page)
    started = time.time()
    errors = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_in_container,args.script,page):page for page in by_ns.values()}
        for future in as_completed(futures):
            page=futures[future]
            try:
                result=future.result()
            except Exception as exc:
                errors.append(str(exc))
                continue
            if result.returncode:
                errors.append(result.stderr.decode("utf-8",errors="replace")[-2000:])
            print(f"{page['ns']}: {result.stdout.decode('utf-8',errors='replace')[-3000:]}",flush=True)
    if errors:
        print(json.dumps(errors,ensure_ascii=False,indent=2))
        sys.exit(1)
    print(f"Done {len(by_ns)} namespaces in {time.time()-started:.0f}s",flush=True)

if __name__ == "__main__":
    main()
