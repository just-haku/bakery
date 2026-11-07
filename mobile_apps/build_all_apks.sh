#!/bin/bash
# ==============================================================================
# Artisan Bakery - Universal 3-Role APK Build Script
# Builds signed, release-ready APKs for:
# 1. Customer (vn.haku.bakery.customer)
# 2. Admin (vn.haku.bakery.admin)
# 3. Employee (vn.haku.bakery.employee - with Niimbot Bluetooth Thermal Printer Bridge)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$PROJECT_ROOT/dist_apk"
KEYSTORE="$SCRIPT_DIR/keystore/artisan_bakery.keystore"
KEY_PASS="artisanbakery123"
KEY_ALIAS="artisan_key"

export JAVA_HOME="/home/haku/jdk17"
export ANDROID_HOME="/home/haku/android-sdk"
export ANDROID_SDK_ROOT="/home/haku/android-sdk"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/build-tools/34.0.0:$PATH"

mkdir -p "$DIST_DIR"

build_app() {
  local APP_NAME="$1"
  local APP_DIR="$SCRIPT_DIR/$APP_NAME"
  local APK_OUTPUT="$DIST_DIR/$2"

  echo "------------------------------------------------------------------------"
  echo "🚀 Building APK: $APP_NAME -> $2"
  echo "------------------------------------------------------------------------"

  rm -rf "$APP_DIR/build"
  mkdir -p "$APP_DIR/build/compiled_res" "$APP_DIR/build/gen" "$APP_DIR/build/bin"

  # 1. Compile Resources with AAPT2
  echo "[1/7] Compiling resources (aapt2)..."
  aapt2 compile --dir "$APP_DIR/res" -o "$APP_DIR/build/compiled_res.zip"

  # 2. Link Resources and Generate R.java
  echo "[2/7] Linking resources and AndroidManifest..."
  aapt2 link \
    -I "$ANDROID_HOME/platforms/android-34/android.jar" \
    --manifest "$APP_DIR/AndroidManifest.xml" \
    --java "$APP_DIR/build/gen" \
    -o "$APP_DIR/build/unaligned.apk" \
    "$APP_DIR/build/compiled_res.zip" \
    --auto-add-overlay

  # 3. Compile Java Sources
  echo "[3/7] Compiling Java source files..."
  javac -encoding UTF-8 -source 1.8 -target 1.8 \
    -cp "$ANDROID_HOME/platforms/android-34/android.jar:$APP_DIR/build/gen" \
    -d "$APP_DIR/build/bin" \
    $(find "$APP_DIR/src" "$APP_DIR/build/gen" -name "*.java")

  # 4. Convert .class files to classes.dex (D8)
  echo "[4/7] Generating Dalvik Executable (classes.dex via D8)..."
  d8 --output "$APP_DIR/build/bin" \
    --lib "$ANDROID_HOME/platforms/android-34/android.jar" \
    $(find "$APP_DIR/build/bin" -name "*.class")

  # 5. Package classes.dex into unaligned.apk
  echo "[5/7] Packaging classes.dex into APK..."
  python3 -c "
import zipfile
apk = '$APP_DIR/build/unaligned.apk'
dex = '$APP_DIR/build/bin/classes.dex'
with zipfile.ZipFile(apk, 'a') as z:
    z.write(dex, 'classes.dex')
"

  # 6. Zipalign (4-byte alignment)
  echo "[6/7] Optimizing APK alignment (zipalign 4)..."
  zipalign -p -f 4 "$APP_DIR/build/unaligned.apk" "$APK_OUTPUT"

  # 7. Sign APK with apksigner (v1, v2, v3 schemes)
  echo "[7/7] Signing APK with Artisan Release Key..."
  apksigner sign \
    --ks "$KEYSTORE" \
    --ks-pass "pass:$KEY_PASS" \
    --ks-key-alias "$KEY_ALIAS" \
    "$APK_OUTPUT"

  apksigner verify "$APK_OUTPUT"
  echo "✅ Successfully built and signed: $2"
}

# Build all 3 apps
build_app "customer" "Artisan_Bakery_Customer.apk"
build_app "admin" "Artisan_Bakery_Admin.apk"
build_app "employee" "Artisan_Bakery_Employee_POS.apk"

echo "========================================================================"
echo "🎉 ALL 3 APKS BUILT AND SIGNED SUCCESSFULLY!"
echo "Outputs located in: $DIST_DIR"
ls -lh "$DIST_DIR"/*.apk
echo "========================================================================"
