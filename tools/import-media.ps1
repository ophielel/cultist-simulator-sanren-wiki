# 批量导入本地 Mod 资源。只读取源文件，不运行 Mod 中的代码。
param(
    [string]$Project = (Join-Path $PSScriptRoot '..')
)
$ErrorActionPreference = 'Stop'
$Project = [System.IO.Path]::GetFullPath($Project)
$compose = "$Project\compose.yaml"
# Sources are mounted read-only in a single temporary import container.
$sourceDir = 'D:\Steam\steamapps\workshop\content\718670'
$mounts = @(
    '-v', "${sourceDir}\3445157833:/mods/contemnant:ro",
    '-v', "${sourceDir}\3171408151:/mods/proterant:ro",
    '-v', "${sourceDir}\2944178812:/mods/obdurant:ro",
    '-v', "${Project}\wiki\images:/var/www/html/images",
    '-v', "${Project}\config\LocalSettings.php:/var/www/html/LocalSettings.php:ro",
    '-v', "${Project}\config\GeneratedSettings.php:/var/www/html/GeneratedSettings.php:ro",
    '-v', "${Project}\config\SanrenHooks.php:/var/www/html/SanrenHooks.php:ro"
)
$script = @'
set -eu
mkdir -p /tmp/sanren-media/Mod /tmp/sanren-covers
for source in /mods/contemnant /mods/proterant /mods/obdurant; do
    if [ -d "$source/images" ]; then
        find "$source/images" -type f -name '*.png' -exec cp -n '{}' /tmp/sanren-media/Mod/ \;
    fi
    if [ -d "$source/audio" ]; then
        find "$source/audio" -type f -name '*.mp3' -exec cp -n '{}' /tmp/sanren-media/Mod/ \;
    fi
done
cp /mods/contemnant/cover.png /tmp/sanren-covers/蔑世使徒_封面.png
cp /mods/proterant/cover.png /tmp/sanren-covers/破军使徒_封面.png
cp /mods/obdurant/cover.png /tmp/sanren-covers/坚毅使徒_封面.png
chown -R www-data:www-data /var/www/html/images
php maintenance/run.php importImages.php --extensions=png,mp3 --user=WikiAdmin --comment='来自本地 Mod 的美术或音频资源；版权归 Mod 作者及原权利人。' /tmp/sanren-media/Mod
php maintenance/run.php importImages.php --extensions=png --user=WikiAdmin --comment='Mod 本地封面；版权归 Mod 作者及原权利人。' /tmp/sanren-covers
'@
& docker run --rm --network 'wiki_wiki' @mounts --env-file "$Project\.env" --entrypoint sh mediawiki:1.43 -c $script
if ($LASTEXITCODE -ne 0) { throw "Media import failed ($LASTEXITCODE)" }
