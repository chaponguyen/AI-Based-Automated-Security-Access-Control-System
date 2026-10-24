# Tạo worktree riêng cho từng Agent để chạy song song (Windows PowerShell).
# Chạy từ thư mục gốc project:  powershell -File scripts\setup_worktrees.ps1
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $Root

git rev-parse --is-inside-work-tree *> $null
if ($LASTEXITCODE -ne 0) { throw "Chưa có git repo. Chạy: git init; git add -A; git commit -m init" }
git rev-parse HEAD *> $null
if ($LASTEXITCODE -ne 0) { throw "Repo chưa có commit nào. Chạy: git add -A; git commit -m init" }

$Parent = Split-Path $Root -Parent
$Agents = @(
  @{ Dir = "wt-ai"; Branch = "agent/a1-ai"; Weights = $true;  TestData = $true;  Env = $false },
  @{ Dir = "wt-be"; Branch = "agent/a2-be"; Weights = $true;  TestData = $false; Env = $true  },
  @{ Dir = "wt-fe"; Branch = "agent/a3-fe"; Weights = $false; TestData = $false; Env = $false }
)

foreach ($a in $Agents) {
  $Path = Join-Path $Parent $a.Dir
  if (-not (Test-Path $Path)) {
    git worktree add $Path -b $a.Branch
  } else {
    Write-Host "Đã có $Path, bỏ qua tạo mới"
  }
  if ($a.Env -and (Test-Path "$Root\backend\.env")) {
    Copy-Item "$Root\backend\.env" "$Path\backend\.env" -Force
  }
  if ($a.Weights -and (Test-Path "$Root\backend\ai\weights")) {
    robocopy "$Root\backend\ai\weights" "$Path\backend\ai\weights" /E /XF README.md /NFL /NDL /NJH /NJS | Out-Null
  }
  if ($a.TestData -and (Test-Path "$Root\test_data")) {
    robocopy "$Root\test_data" "$Path\test_data" /E /NFL /NDL /NJH /NJS | Out-Null
  }
  Write-Host "OK: $Path  (nhánh $($a.Branch))"
}
Write-Host "`nXong. Nhớ: cd ..\wt-fe\frontend; npm install   (node_modules không được copy)"
Write-Host "Dùng chung venv của thư mục gốc: $Root\venv\Scripts\activate"
