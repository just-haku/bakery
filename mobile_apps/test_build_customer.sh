#!/bin/bash
set -e
source /home/haku/android-env.sh

APP_DIR="/home/haku/bakery/mobile_apps/customer"
DIST_DIR="/home/haku/bakery/dist_apk"
mkdir -p "$DIST_DIR"
rm -rf "$APP_DIR/build"
mkdir -p "$APP_DIR/build/compiled_res" "$APP_DIR/build/gen" "$APP_DIR/build/bin"

echo "1. aapt2 compile..."
aapt2 compile --dir "$APP_DIR/res" -o "$APP_DIR/build/compiled_res.zip"

echo "2. aapt2 link..."
aapt2 link \
  -I "$ANDROID_HOME/platforms/android-34/android.jar" \
  --manifest "$APP_DIR/AndroidManifest.xml" \
  --java "$APP_DIR/build/gen" \
  -o "$APP_DIR/build/unaligned.apk" \
  "$APP_DIR/build/compiled_res.zip" \
  --auto-add-overlay

echo "3. javac..."
javac -encoding UTF-8 -source 1.8 -target 1.8 \
  -cp "$ANDROID_HOME/platforms/android-34/android.jar:$APP_DIR/build/gen" \
  -d "$APP_DIR/build/bin" \
  $(find "$APP_DIR/src" "$APP_DIR/build/gen" -name "*.java")

echo "4. d8..."
d8 --output "$APP_DIR/build/bin" \
  --lib "$ANDROID_HOME/platforms/android-34/android.jar" \
  $(find "$APP_DIR/build/bin" -name "*.class")

echo "5. add classes.dex using python zipfile..."
python3 -c "
import zipfile
apk = '$APP_DIR/build/unaligned.apk'
dex = '$APP_DIR/build/bin/classes.dex'
with zipfile.ZipFile(apk, 'a') as z:
    z.write(dex, 'classes.dex')
"

echo "6. zipalign..."
zipalign -p -f 4 "$APP_DIR/build/unaligned.apk" "$DIST_DIR/Artisan_Bakery_Customer.apk"

echo "7. apksigner..."
apksigner sign \
  --ks /home/haku/bakery/mobile_apps/keystore/artisan_bakery.keystore \
  --ks-pass pass:artisanbakery123 \
  --ks-key-alias artisan_key \
  "$DIST_DIR/Artisan_Bakery_Customer.apk"

echo "8. verify..."
apksigner verify "$DIST_DIR/Artisan_Bakery_Customer.apk"
echo "Build Customer APK SUCCESS!"
ls -lh "$DIST_DIR/Artisan_Bakery_Customer.apk"
