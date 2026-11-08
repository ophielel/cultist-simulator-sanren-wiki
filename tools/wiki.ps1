# Start, stop, back up and rebuild the local wiki.
param(
    [ValidateSet('start', 'stop', 'status', 'backup')]
    [string]$Action = 'start',
    [string]$Project = (Join-Path $PSScriptRoot '..')
)
$ErrorActionPreference = 'Stop'
$Project = [System.IO.Path]::GetFullPath($Project)
$compose = Join-Path $Project 'compose.yaml'

if ($Action -eq 'start') {
    & docker compose -f $compose up -d
    if ($LASTEXITCODE) { throw 'Unable to start the wiki.' }
    & docker compose -f $compose ps
    Write-Host "`n三刃使徒 Wiki：http://localhost:8090/"
}
elseif ($Action -eq 'stop') {
    & docker compose -f $compose stop
}
elseif ($Action -eq 'status') {
    & docker compose -f $compose ps
}
elseif ($Action -eq 'backup') {
    $backup = Join-Path $Project 'backups'
    if (-not (Test-Path -LiteralPath $backup)) {
        New-Item -ItemType Directory -Path $backup | Out-Null
    }
    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $archive = Join-Path $backup "sanren-$timestamp.tar"
    # Database export only; never print local passwords to the console.
    & docker compose -f $compose exec -T database sh -c 'mariadb-dump --single-transaction --user=root --password="$MARIADB_ROOT_PASSWORD" mediawiki > /tmp/sanren-backup.sql'
    if ($LASTEXITCODE) { throw 'Database export failed.' }
    & docker compose -f $compose cp "database:/tmp/sanren-backup.sql" (Join-Path $backup "sanren-$timestamp.sql")
    if ($LASTEXITCODE) { throw 'Unable to copy database export.' }
    & docker compose -f $compose exec -T database rm -f /tmp/sanren-backup.sql
    if ($LASTEXITCODE) { throw 'Unable to remove temporary export.' }
    if ($LASTEXITCODE) { throw 'Database export failed.' }
    Write-Host "备份：$backup\sanren-$timestamp.sql"
    Write-Host '图片保存在 wiki/images/，可通过常规文件备份一并保存。'
}
