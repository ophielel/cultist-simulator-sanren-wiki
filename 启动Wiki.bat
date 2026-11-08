@echo off
chcp 65001 >nul
title 三刃使徒 Wiki 启动器
cd /d "%~dp0"

echo 正在检查 Docker 运行状态...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Docker 尚未运行，正在尝试启动 Docker Desktop...
    if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
        start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    ) else (
        echo [错误] 未在默认路径找到 Docker Desktop，请先手动启动 Docker Desktop。
        pause
        exit /b 1
    )

    echo 正在等待 Docker 引擎就绪...
    set /a attempts=0
    :wait_docker
    timeout /t 3 /nobreak >nul
    docker info >nul 2>&1
    if %errorlevel% neq 0 (
        set /a attempts+=1
        if %attempts% geq 20 (
            echo [错误] 等待 Docker 启动超时，请确保 Docker Desktop 已正常启动后再试。
            pause
            exit /b 1
        )
        goto wait_docker
    )
    echo Docker 引擎已就绪！
)

echo 正在启动 Wiki 容器...
docker compose up -d
if %errorlevel% neq 0 (
    echo [错误] Wiki 启动失败，请检查 Docker 状态。
    pause
    exit /b 1
)

echo.
echo ============================================
echo   三刃使徒 Wiki 已成功启动！
echo   访问地址: http://localhost:8090/
echo ============================================
echo.

start "" "http://localhost:8090/"

echo 浏览器已打开，本窗口将在 3 秒后自动关闭...
timeout /t 3 /nobreak >nul
