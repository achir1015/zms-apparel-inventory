#!/bin/bash
# 資料助秘工具之服飾業進銷存系統 — macOS 打包（在 Mac 上執行）
#   需要：Homebrew 的 mariadb 與 dylibbundler（brew install mariadb dylibbundler）、.venv（flet、pyinstaller）
#   產出：dist-mac/ZMSInventory-<版本>-mac-<架構>.dmg
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH=/usr/local/bin:/opt/homebrew/bin:$PATH
# python.org 版 Python 沒有系統憑證：用 certifi（flet 要下載 macOS 用戶端）
export SSL_CERT_FILE=$(.venv/bin/python -m certifi 2>/dev/null || true)
VER=$(.venv/bin/python -c "import zms; print(zms.APP_VERSION)")
NAME=$(.venv/bin/python -c "import zms; print(zms.APP_NAME)")
ARCH=$(uname -m)
MDB=$(brew --prefix mariadb 2>/dev/null || echo /nonexistent)
OUT=dist-mac
STAGE=build-mac
rm -rf "$STAGE" dist "$OUT" && mkdir -p "$STAGE" "$OUT"
BUNDLE=0
[ -x "$MDB/bin/mariadbd" ] && command -v dylibbundler >/dev/null && BUNDLE=1

if [ "$BUNDLE" = 1 ]; then
echo "== 1. 準備內附 MariaDB（$MDB）"
M="$STAGE/mariadb"
mkdir -p "$M/bin" "$M/lib" "$M/share"
for f in mariadbd mariadb-install-db my_print_defaults mariadb-admin mariadb-dump mariadb resolveip; do
  [ -e "$MDB/bin/$f" ] && cp -L "$MDB/bin/$f" "$M/bin/"
done
SHARE="$MDB/share/mariadb"; [ -d "$SHARE" ] || SHARE="$MDB/share/mysql"
mkdir -p "$M/share/mariadb"
cp "$SHARE"/*.sql "$M/share/mariadb/" 2>/dev/null || true
for d in charsets english chinese; do [ -d "$SHARE/$d" ] && cp -R "$SHARE/$d" "$M/share/mariadb/"; done
cp "$MDB"/COPYING* "$M/" 2>/dev/null || true
# install-db 腳本裡寫死 Homebrew 路徑 → 改成以 --basedir 為準
sed -i '' "s#$MDB#\${basedir:-$MDB}#g" "$M/bin/mariadb-install-db" || true
chmod +x "$M/bin/"*
# 把 Homebrew 的 dylib 一起帶走，改成相對路徑
BIN_ARGS=()
for f in "$M"/bin/*; do file "$f" | grep -q Mach-O && BIN_ARGS+=(-x "$f"); done
dylibbundler -od -b "${BIN_ARGS[@]}" -d "$M/lib" -p @executable_path/../lib/ >/dev/null
for f in "$M"/bin/* "$M"/lib/*; do file "$f" | grep -q Mach-O && codesign --force -s - "$f" 2>/dev/null || true; done

echo "== 2. 驗證內附 MariaDB 可獨立建庫與啟動"
T=$(mktemp -d)
"$M/bin/mariadb-install-db" --no-defaults --basedir="$M" --datadir="$T/data" --auth-root-authentication-method=normal --skip-test-db >/dev/null
"$M/bin/mariadbd" --no-defaults --basedir="$M" --datadir="$T/data" --port=3399 --bind-address=127.0.0.1 \
  --socket="$T/s.sock" --lc-messages-dir="$M/share/mariadb" >"$T/log" 2>&1 &
PID=$!
for i in $(seq 1 40); do nc -z 127.0.0.1 3399 2>/dev/null && break; sleep 0.5; done
"$M/bin/mariadb" -h127.0.0.1 -P3399 -uroot -e "select version()"
"$M/bin/mariadb-admin" -h127.0.0.1 -P3399 -uroot shutdown
wait $PID || true
rm -rf "$T"
else
echo "== 1-2. 沒有 Homebrew 的 MariaDB：Mac 版不內附資料庫，開啟後連到其他電腦上的進銷存資料庫"
fi

echo "== 3. 圖示"
ICONSET="$STAGE/icon.iconset"; mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s assets/icon.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  sips -z $((s*2)) $((s*2)) assets/icon.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$STAGE/icon.icns"

echo "== 4. flet pack（PyInstaller）"
.venv/bin/flet pack main.py -y -n ZMSInventory -i "$STAGE/icon.icns" --distpath dist \
  --add-data "assets:assets" "zms/schema.sql:zms" --product-name "$NAME" --product-version "$VER" \
  --bundle-id com.achir.zmsinventory --copyright "© 2026 吳玉柱"
APP="dist/ZMSInventory.app"
[ "$BUNDLE" = 1 ] && cp -R "$M" "$APP/Contents/Resources/mariadb"
/usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName $NAME" "$APP/Contents/Info.plist" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string $NAME" "$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersion string 11.0" "$APP/Contents/Info.plist" 2>/dev/null || true
codesign --force --deep -s - "$APP"

echo "== 5. DMG"
DMGDIR="$STAGE/dmg"; mkdir -p "$DMGDIR"
cp -R "$APP" "$DMGDIR/$NAME.app"
ln -s /Applications "$DMGDIR/Applications"
DMG="$OUT/ZMSInventory-$VER-mac-$ARCH.dmg"
for i in 1 2 3; do hdiutil create -volname "$NAME" -srcfolder "$DMGDIR" -ov -format UDZO "$DMG" >/dev/null && break; sleep 3; done
ls -lh "$DMG"
echo "完成：$DMG"
