#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  RedAlertIDF — macOS build + PKG + DMG creator
#  Usage: ./build_mac.sh
#  Output: dist/RedAlertIDF-5.3.0.pkg   (מתקין רשמי)
#          dist/RedAlertIDF-5.3.0.dmg   (דיסק וירטואלי לגרירה)
# ─────────────────────────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

APP_NAME="RedAlertIDF"
APP_VERSION="5.3.0"
PKG_NAME="${APP_NAME}-${APP_VERSION}.pkg"
DMG_NAME="${APP_NAME}-${APP_VERSION}.dmg"
DIST_DIR="dist"
APP_BUNDLE="${DIST_DIR}/${APP_NAME}.app"

echo "══════════════════════════════════════════════════"
echo "  RedAlertIDF macOS Builder v${APP_VERSION}"
echo "══════════════════════════════════════════════════"

# ── 1. Install / upgrade dependencies ──────────────────────────────────────
echo ""
echo "▶ בדיקת תלויות..."
pip3 install --quiet --break-system-packages \
    pyinstaller PyQt5 PyQtWebEngine requests 2>/dev/null || \
pip3 install --quiet \
    pyinstaller PyQt5 PyQtWebEngine requests 2>/dev/null || true

# ── 2. Generate icon ───────────────────────────────────────────────────────
echo "▶ יוצר אייקון..."
python3 make_icon.py

# ── 3. Clean previous build ────────────────────────────────────────────────
echo "▶ מנקה build ישן..."
rm -rf build "${DIST_DIR}/${APP_NAME}" "${APP_BUNDLE}" \
       "${DIST_DIR}/${PKG_NAME}" "${DIST_DIR}/${DMG_NAME}"

# ── 4. PyInstaller build ───────────────────────────────────────────────────
echo "▶ בונה .app (אורך ~2-3 דקות)..."
pyinstaller --noconfirm red_alert.spec

# ── 5. Fix code signing ────────────────────────────────────────────────────
echo "▶ חותם קוד..."
xattr -cr "${APP_BUNDLE}"
# Sign each framework separately (QtWebEngineCore needs this)
find "${APP_BUNDLE}/Contents/Frameworks" -name "*.framework" | while read fw; do
    codesign -s - --force "$fw" 2>/dev/null || true
done
codesign -s - --force "${APP_BUNDLE}" 2>/dev/null || true

# ── 6. Smoke test ─────────────────────────────────────────────────────────
echo "▶ בדיקת תקינות..."
if [ ! -f "${APP_BUNDLE}/Contents/MacOS/${APP_NAME}" ]; then
    echo "❌ הבנייה נכשלה — הקובץ לא נמצא"
    exit 1
fi

# ── 7. Create .pkg installer ──────────────────────────────────────────────
echo "▶ יוצר .pkg..."
pkgbuild \
    --install-location /Applications \
    --component "${APP_BUNDLE}" \
    --identifier com.redalert.idf \
    --version "${APP_VERSION}" \
    "${DIST_DIR}/${PKG_NAME}"

# הסר quarantine כדי שהמתקין יפתח ישירות
xattr -d com.apple.quarantine "${DIST_DIR}/${PKG_NAME}" 2>/dev/null || true

# ── 8. Create DMG ─────────────────────────────────────────────────────────
echo "▶ יוצר DMG..."
STAGING_DIR=$(mktemp -d)
cp -r "${APP_BUNDLE}" "${STAGING_DIR}/"
ln -s /Applications "${STAGING_DIR}/Applications"

TMP_DMG="${DIST_DIR}/tmp_${APP_NAME}.dmg"
hdiutil create -volname "${APP_NAME}" -srcfolder "${STAGING_DIR}" \
    -ov -format UDRW "${TMP_DMG}" > /dev/null
hdiutil convert "${TMP_DMG}" -format UDZO -o "${DIST_DIR}/${DMG_NAME}" > /dev/null
rm -f "${TMP_DMG}"
rm -rf "${STAGING_DIR}"
xattr -d com.apple.quarantine "${DIST_DIR}/${DMG_NAME}" 2>/dev/null || true

# ── 9. Done ────────────────────────────────────────────────────────────────
PKG_SIZE=$(du -sh "${DIST_DIR}/${PKG_NAME}" | cut -f1)
DMG_SIZE=$(du -sh "${DIST_DIR}/${DMG_NAME}" | cut -f1)
echo ""
echo "══════════════════════════════════════════════════"
echo "  ✅ הצלחה!"
echo ""
echo "  📦 ${DIST_DIR}/${PKG_NAME}   (${PKG_SIZE})"
echo "     → לחץ פעמיים → התקן → RedAlertIDF ב-Applications"
echo ""
echo "  💿 ${DIST_DIR}/${DMG_NAME}  (${DMG_SIZE})"
echo "     → פתח → גרור RedAlertIDF.app אל Applications"
echo "══════════════════════════════════════════════════"
echo ""
echo "⚠  אם macOS חוסם פתיחה:"
echo "   הגדרות מערכת → פרטיות ואבטחה → 'פתח בכל זאת'"
echo "   או: Control+לחיצה על הקובץ → פתח"
echo ""
