# 启动本地三刃使徒 Wiki（需要 Docker Desktop）。
$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot
$docker = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
if (-not (Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue) -and (Test-Path $docker)) {
    Start-Process -FilePath $docker
    Write-Host "正在等待 Docker Desktop 启动..."
    for ($i = 0; $i -lt 30; $i++) {
        docker info 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { break }
        Start-Sleep -Seconds 2
    }
}
& docker compose -f (Join-Path $project 'compose.yaml') up -d
Start-Process 'http://localhost:8090/'
