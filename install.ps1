# Windows 安装：建 venv、装依赖、找引擎、写插件配置、登记 marketplace。
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$Root = (Get-Location).Path

Write-Host "==> 1/4 建虚拟环境"
if (-not (Test-Path ".venv\Scripts\python.exe")) { py -3 -m venv .venv }
$Py = Join-Path $Root ".venv\Scripts\python.exe"

Write-Host "==> 2/4 装依赖（python-chess）"
& $Py -m pip install --quiet --disable-pip-version-check -r requirements.txt

Write-Host "==> 3/4 找 Stockfish"
$engine = (& $Py -c "from tools.engines import find_engine; print(find_engine(required=False) or '')")
if ([string]::IsNullOrWhiteSpace($engine)) {
  Write-Host "    没找到。装一下（winget install stockfish），或把 stockfish.exe 放进 engines\。"
} else { Write-Host "    找到：$engine" }

Write-Host "==> 4/4 写插件配置并登记 marketplace"
$cfg = @{ mcpServers = @{ chess = @{ command = $Py; args = @((Join-Path $Root "mcp\server.py")) } } }
$cfg | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 ".mcp.json"
Write-Host "    已写 .mcp.json（指向本机绝对路径）"

$marketDir = Join-Path $env:USERPROFILE ".agents\plugins"
$market = Join-Path $marketDir "marketplace.json"
New-Item -ItemType Directory -Force -Path $marketDir | Out-Null
if (Test-Path $market) { $data = Get-Content $market -Raw | ConvertFrom-Json }
else { $data = [pscustomobject]@{ name = "personal"; interface = @{ displayName = "Personal" }; plugins = @() } }
$entry = [pscustomobject]@{
  name = "chess"
  source = @{ source = "local"; path = $Root }
  policy = @{ installation = "AVAILABLE"; authentication = "ON_INSTALL" }
  category = "Productivity"
}
$keep = @($data.plugins | Where-Object { $_.name -ne "chess" })
$data.plugins = @($keep) + @($entry)
$data | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $market
Write-Host "    已登记到 $market"

Write-Host ""
Write-Host "完成。重启 Codex 后，在 Personal 里启用 chess 插件即可。"
