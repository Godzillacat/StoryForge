# StoryForge 构建脚本：前端 → PyInstaller → （提示）Inno 安装包
#
# 用法（在仓库根）：
#   powershell -ExecutionPolicy Bypass -File scripts/build.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/build.ps1 -SkipFrontend
#
# 产物：backend/dist/StoryForge/StoryForge.exe
# 安装包需要 Inno Setup 6（本脚本不会自动装），见 packaging/README.md。

param(
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

if (-not $SkipFrontend) {
    Write-Host "==> 构建前端" -ForegroundColor Cyan
    Push-Location (Join-Path $Root "frontend")
    try {
        pnpm build
        if ($LASTEXITCODE -ne 0) { throw "前端构建失败" }
    } finally {
        Pop-Location
    }
}

$index = Join-Path $Root "frontend\dist\index.html"
if (-not (Test-Path $index)) {
    throw "找不到 frontend/dist/index.html —— 前端没构建成功。"
}

Write-Host "==> 打包后端" -ForegroundColor Cyan
Push-Location (Join-Path $Root "backend")
try {
    uv run pyinstaller storyforge.spec --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败" }
} finally {
    Pop-Location
}

$exe = Join-Path $Root "backend\dist\StoryForge\StoryForge.exe"
if (-not (Test-Path $exe)) {
    throw "打包结束但没找到 $exe"
}

Write-Host "==> 产物自检" -ForegroundColor Cyan
& $exe --selftest
if ($LASTEXITCODE -ne 0) { throw "产物自检失败（退出码 $LASTEXITCODE）" }

Write-Host ""
Write-Host "构建完成：$exe" -ForegroundColor Green
Write-Host "数据仍然在 %LOCALAPPDATA%\StoryForge\，不在程序目录里。" -ForegroundColor DarkGray
Write-Host ""
Write-Host "要出安装包，先装 Inno Setup 6，然后：" -ForegroundColor DarkGray
Write-Host '  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss' -ForegroundColor DarkGray
