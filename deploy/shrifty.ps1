# Пересборка своих шрифтов (static/fonts/*.woff2 + static/css/fonts.css).
#
# Зачем свои: Google Fonts CDN отдаёт IP каждого посетителя в США, а мы обрабатываем
# персданные (152-ФЗ) — в ЕС за это уже штрафовали. Плюс шапка сайта больше не ждёт
# чужой сервер, и PWA работает офлайн со своими гарнитурами.
#
# Что делает: просит у Google CSS с UA Chrome (иначе отдаст ttf вместо woff2), берёт
# ВАРИАТИВНЫЕ начертания (один файл на все веса — 104 КБ против 377 статикой) и только
# подмножества cyrillic+latin (Google отдаёт семь, греческий и вьетнамский нам не нужны).
#
# Запуск из корня проекта:
#   powershell -File deploy/shrifty.ps1
# После — пересобрать Tailwind и collectstatic.
#
# Inter и Manrope распространяются по SIL Open Font License 1.1.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$fontsDir = Join-Path $root 'static\fonts'
New-Item -ItemType Directory -Force -Path $fontsDir | Out-Null
Get-ChildItem -LiteralPath $fontsDir -Filter *.woff2 -ErrorAction SilentlyContinue |
    ForEach-Object { [System.IO.File]::Delete($_.FullName) }

$ua  = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
$url = 'https://fonts.googleapis.com/css2?family=Inter:wght@400..700&family=Manrope:wght@600..800&display=swap'
$css = (Invoke-WebRequest -Uri $url -UserAgent $ua -UseBasicParsing).Content

$nuzhno = @('cyrillic', 'latin')
$out = New-Object System.Text.StringBuilder
@(
  ("{0} Свои шрифты вместо Google CDN (152-ФЗ: их CDN видит IP посетителя)." -f '/*'),
  '   Вариативные, подмножества cyrillic+latin. Inter и Manrope — SIL OFL 1.1.',
  ("   Не править руками — пересобирается deploy/shrifty.ps1 {0}" -f '*/')
) | ForEach-Object { [void]$out.AppendLine($_) }

$skachano = 0
foreach ($b in [regex]::Matches($css, '/\*\s*([a-z\-]+)\s*\*/\s*(@font-face\s*\{[^}]+\})')) {
    $subset = $b.Groups[1].Value
    if ($nuzhno -notcontains $subset) { continue }
    $blok = $b.Groups[2].Value
    $sem  = [regex]::Match($blok, "font-family: '([^']+)'").Groups[1].Value
    $src  = [regex]::Match($blok, 'url\((https://[^)]+)\)').Groups[1].Value
    $imya = ('{0}-{1}.woff2' -f $sem.ToLower(), $subset)
    Invoke-WebRequest -Uri $src -OutFile (Join-Path $fontsDir $imya) -UseBasicParsing
    [void]$out.AppendLine(($blok -replace 'url\(https://[^)]+\)', "url('../fonts/$imya')"))
    $skachano++
}
Set-Content -LiteralPath (Join-Path $root 'static\css\fonts.css') -Value $out.ToString() -Encoding UTF8

$kb = [math]::Round((Get-ChildItem -LiteralPath $fontsDir -Filter *.woff2 | Measure-Object Length -Sum).Sum / 1KB)
Write-Host "Готово: файлов $skachano, итого $kb КБ"
Write-Host 'Дальше: npx tailwindcss@3 -c tailwind.config.js -i static/css/tailwind.src.css -o static/css/app.css --minify'
Write-Host '        python manage.py collectstatic --noinput'
