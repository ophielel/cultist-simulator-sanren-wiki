# 更新现有 wiki 的全部生成页面。旧版同名内容会由新的修订覆盖。
param(
    [string]$Project = (Join-Path $PSScriptRoot '..'),
    [switch]$WithMedia
)
$ErrorActionPreference = 'Stop'
$Project = [System.IO.Path]::GetFullPath($Project)
& python -I (Join-Path $Project 'tools\build_wiki.py')
if ($LASTEXITCODE) { throw 'Page generation failed.' }
& docker run --rm --network wiki_wiki --volumes-from wiki-mediawiki-1 --env-file (Join-Path $Project '.env') --mount "type=bind,source=$Project\build,target=/build" --mount "type=bind,source=$Project\tools\ResolveNamespaces.php,target=/tmp/resolve.php,readonly" --entrypoint php mediawiki:1.43 /tmp/resolve.php
if ($LASTEXITCODE) { throw 'Namespace resolution failed.' }
& docker compose -f (Join-Path $Project 'compose.yaml') up -d
if ($LASTEXITCODE) { throw 'Wiki startup failed.' }
& docker run --rm --network wiki_wiki --volumes-from wiki-mediawiki-1 --env-file (Join-Path $Project '.env') --mount "type=bind,source=$Project\build,target=/build,readonly" --mount "type=bind,source=$Project\tools\SanrenImportChanged.php,target=/tmp/import-changed.php,readonly" --entrypoint php mediawiki:1.43 /tmp/import-changed.php
if ($LASTEXITCODE) { throw 'Changed-page import failed.' }
# Optional resumable CLI importer for very large initial imports:
# python -I tools/import_pages.py --all
if ($WithMedia) {
    & pwsh -NoProfile -File (Join-Path $Project 'tools\import-media.ps1')
    if ($LASTEXITCODE) { throw 'Media import failed.' }
}
& docker run --rm --network wiki_wiki --volumes-from wiki-mediawiki-1 --env-file (Join-Path $Project '.env') --mount "type=bind,source=$Project\build,target=/build" --mount "type=bind,source=$Project\tools\SanrenVerify.php,target=/tmp/verify.php,readonly" --entrypoint php mediawiki:1.43 /tmp/verify.php
if ($LASTEXITCODE) { throw 'Verification failed.' }
& docker compose -f (Join-Path $Project 'compose.yaml') exec -T mediawiki php maintenance/run.php runJobs.php --maxjobs=10000
if ($LASTEXITCODE) { throw 'Link table update failed.' }
& docker compose -f (Join-Path $Project 'compose.yaml') exec -T mediawiki php maintenance/run.php rebuildall.php
if ($LASTEXITCODE) { throw 'Index rebuild failed.' }
