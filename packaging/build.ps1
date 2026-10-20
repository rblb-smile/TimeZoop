# 배포용 빌드: PyInstaller → 개인정보 검사 → Inno Setup 설치 파일
# 사용: powershell -ExecutionPolicy Bypass -File packaging\build.ps1 [-NoInstaller]
#   -NoInstaller: 오래 걸리는 설치 파일 압축 없이 exe만 만들고 검사까지
param([switch]$NoInstaller)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$py = Join-Path $root ".venv\Scripts\python.exe"
$dist = Join-Path $root "build\dist\TimeZoop"

Write-Host "1/3 실행 파일 만들기 (PyInstaller)"
if (Test-Path (Join-Path $root "build")) { Remove-Item (Join-Path $root "build") -Recurse -Force }
& $py -m PyInstaller packaging\TimeZoop.spec --noconfirm --distpath build\dist --workpath build\work --log-level WARN
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 실패" }

# llama.cpp(서버와 DLL만, 다른 도구 exe는 뺀다)와 ffmpeg는 빌드 뒤 그대로 복사한다 (spec 주석 참고)
$vendorOut = Join-Path $dist "_internal\vendor"
New-Item -ItemType Directory -Force "$vendorOut\llama.cpp", "$vendorOut\ffmpeg" | Out-Null
Copy-Item "vendor\llama.cpp\llama-server.exe", "vendor\llama.cpp\*.dll", "vendor\llama.cpp\LICENSE*" "$vendorOut\llama.cpp"
Copy-Item "vendor\ffmpeg\ffmpeg.exe", "vendor\ffmpeg\LICENSE.txt" "$vendorOut\ffmpeg"
if (Test-Path (Join-Path $dist "_internal\av.libs")) { throw "PyAV가 들어갔습니다 (spec의 excludes 확인)" }
"  크기: {0:N2} GB" -f ((Get-ChildItem $dist -Recurse -File | Measure-Object Length -Sum).Sum / 1GB)

Write-Host "2/3 개인정보 검사 (배포 파일에 만든 사람의 정보가 있으면 중단)"
# 들어가면 안 되는 폴더·파일
$forbidden = Get-ChildItem $dist -Recurse -Force | Where-Object {
    $_.FullName -match '\\(data|models|chat_raw)\\' -or $_.Name -match '^(settings\.json|session\.bin|uploads\.json|app\.log|meta\.json|transcript_.*\.json|.*\.m4a|.*\.gguf|model\.bin)$'
}
if ($forbidden) { $forbidden | ForEach-Object { Write-Host "  들어가면 안 되는 파일: $($_.FullName)" }; throw "개인 데이터가 섞여 있습니다" }
# 들어가면 안 되는 문자열: PC 사용자 이름 + packaging\privacy_words.txt (계정, 채널, 시험에 쓴 VOD 번호 등, git에 올리지 않음)
# UTF-8 / UTF-16 둘 다 검사
$secrets = @($env:USERNAME)
$wordsFile = Join-Path $PSScriptRoot "privacy_words.txt"
if (Test-Path $wordsFile) {
    $secrets += Get-Content $wordsFile -Encoding UTF8 | Where-Object { $_.Trim() -and -not $_.StartsWith("#") } | ForEach-Object { $_.Trim() }
} else { Write-Host "  (privacy_words.txt가 없어 PC 사용자 이름만 검사합니다)" }
$enc8 = [Text.Encoding]::UTF8; $enc16 = [Text.Encoding]::Unicode
$hits = @()
foreach ($f in Get-ChildItem $dist -Recurse -File) {
    $bytes = [IO.File]::ReadAllBytes($f.FullName)
    $t8 = $enc8.GetString($bytes); $t16 = $enc16.GetString($bytes)
    foreach ($s in $secrets) {
        if ($t8.Contains($s) -or $t16.Contains($s)) { $hits += "$($f.FullName.Substring($dist.Length + 1)) ← '$s'" }
    }
}
if ($hits) { $hits | ForEach-Object { Write-Host "  발견: $_" }; throw "배포 파일에 개인정보 문자열이 있습니다" }
Write-Host "  통과: 개인 데이터·문자열 없음"
if ($NoInstaller) { Write-Host "exe만 만들었습니다: $dist"; exit 0 }

Write-Host "3/3 설치 파일 만들기 (Inno Setup)"
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6이 없습니다 (winget install JRSoftware.InnoSetup)" }
& $iscc /Q packaging\installer.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup 실패" }
Get-ChildItem (Join-Path $root "build\installer") | ForEach-Object { "{0}  {1:N0} MB" -f $_.Name, ($_.Length / 1MB) }
