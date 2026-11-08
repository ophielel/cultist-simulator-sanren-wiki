# 完成最终校验所需的链接更新和统计。
param([string]$Project = (Join-Path $PSScriptRoot '..'))
$ErrorActionPreference = 'Stop'
$Project = [System.IO.Path]::GetFullPath($Project)
$compose = Join-Path $Project 'compose.yaml'
& docker compose -f $compose exec -T mediawiki php maintenance/run.php runJobs.php --maxjobs=10000
if ($LASTEXITCODE) { throw 'Jobs failed.' }
& docker compose -f $compose exec -T mediawiki php maintenance/run.php rebuildtextindex.php
if ($LASTEXITCODE) { throw 'Search index failed.' }
& docker run --rm --network wiki_wiki --volumes-from wiki-mediawiki-1 --env-file (Join-Path $Project '.env') --mount "type=bind,source=$Project\build,target=/build" --mount "type=bind,source=$Project\tools\SanrenVerify.php,target=/tmp/verify.php,readonly" --entrypoint php mediawiki:1.43 /tmp/verify.php
if ($LASTEXITCODE) { throw 'Verification script failed.' }
