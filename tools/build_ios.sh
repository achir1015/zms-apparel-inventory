#!/bin/bash
# 資料助秘工具之服飾業進銷存系統 — iPhone 版打包（在 Mac 上執行）
#   要在 Mac 畫面上的「終端機」執行（SSH 進來鑰匙圈是鎖的，簽章會 errSecInternalComponent）：
#     osascript -e 'tell application "Terminal" to do script "bash ~/Developer/zms-inventory/tools/build_ios.sh"'
#   產出：dist-ios/ZMSInventory-<版本>-ios.ipa（Ad Hoc，只能裝在開發者帳號登記過的 iPhone／iPad）
#   進度：dist-ios/build.log；完成會留下 dist-ios/done（內容 ok 或 fail）
#   SKIP_FLET=1 可略過 flet build（只重新簽章匯出）
cd "$(dirname "$0")/.."
OUT=dist-ios
mkdir -p "$OUT"
rm -f "$OUT/done"
exec > >(tee "$OUT/build.log") 2>&1
set -o pipefail
fail() { echo "fail" > "$OUT/done"; echo "== 失敗"; exit 1; }
export PATH=/usr/local/bin:/opt/homebrew/bin:$PATH
export SSL_CERT_FILE=$(.venv/bin/python -m certifi 2>/dev/null || true)
VER=$(.venv/bin/python -c "import zms; print(zms.APP_VERSION)")
TEAM=7BN6XJ59KP
IOS=build/flutter/ios

if [ "${SKIP_FLET:-0}" != 1 ]; then
  echo "== 1. flet build ipa（產生 Xcode 專案與未簽章封存）"
  # Flet 範本留有 Podfile，但外掛都已是 Swift Package；Mac 沒有 CocoaPods 時移開 Podfile 改走 SPM
  [ -f "$IOS/Podfile" ] && ! command -v pod >/dev/null && rm -f "$IOS/Podfile"
  if ! .venv/bin/flet build ipa --build-version "$VER" --yes; then
    if [ -f "$IOS/Podfile" ] && ! command -v pod >/dev/null; then
      echo "== 第一次產生的專案含 Podfile → 移開後重試"
      rm -f "$IOS/Podfile"
      .venv/bin/flet build ipa --build-version "$VER" --yes || fail
    else
      fail
    fi
  fi
fi

echo "== 2. Xcode 自動簽章封存"
ARCHIVE="$OUT/Runner.xcarchive"
rm -rf "$ARCHIVE" "$OUT/export"
xcodebuild -workspace "$IOS/Runner.xcworkspace" -scheme Runner -configuration Release \
  -destination 'generic/platform=iOS' -archivePath "$ARCHIVE" -allowProvisioningUpdates \
  DEVELOPMENT_TEAM=$TEAM CODE_SIGN_STYLE=Automatic CODE_SIGN_IDENTITY="Apple Development" \
  PROVISIONING_PROFILE_SPECIFIER= FLUTTER_BUILD_NAME="$VER" archive \
  | grep -E "error:|warning: .*[Ss]ign|ARCHIVE (SUCCEEDED|FAILED)" || fail
[ -d "$ARCHIVE" ] || fail

echo "== 3. 匯出 Ad Hoc .ipa"
cat > "$OUT/ExportOptions.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>method</key><string>release-testing</string>
  <key>teamID</key><string>$TEAM</string>
  <key>signingStyle</key><string>automatic</string>
  <key>compileBitcode</key><false/>
  <key>thinning</key><string>&lt;none&gt;</string>
</dict>
</plist>
EOF
xcodebuild -exportArchive -archivePath "$ARCHIVE" -exportPath "$OUT/export" \
  -exportOptionsPlist "$OUT/ExportOptions.plist" -allowProvisioningUpdates || fail
IPA=$(ls "$OUT"/export/*.ipa 2>/dev/null | head -1)
[ -f "$IPA" ] || fail
cp "$IPA" "$OUT/ZMSInventory-$VER-ios.ipa"
echo "== 可安裝的裝置（UDID）："
unzip -p "$OUT/ZMSInventory-$VER-ios.ipa" 'Payload/*.app/embedded.mobileprovision' | security cms -D \
  | plutil -extract ProvisionedDevices json -o - - || true
echo
ls -lh "$OUT/ZMSInventory-$VER-ios.ipa"
echo "ok" > "$OUT/done"
echo "== 完成"
