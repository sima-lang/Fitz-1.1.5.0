#!/bin/bash
set -e

APP_NAME="fitz14"
APP_DIR="/opt/$APP_NAME"
BUILD_DIR="build_deb"

echo "🧹 Очистка старой сборки..."
rm -rf "$BUILD_DIR"

echo "📁 Создание структуры..."
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$BUILD_DIR/usr/share/applications"
mkdir -p "$BUILD_DIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$BUILD_DIR$APP_DIR"

echo "📦 Копирование файлов проекта..."
rsync -av --exclude="$BUILD_DIR" --exclude="venv" --exclude="__pycache__" --exclude=".git" --exclude="build_deb.sh" ./ "$BUILD_DIR$APP_DIR/"

echo "📜 Создание скрипта запуска..."
cat > "$BUILD_DIR$APP_DIR/run_fitz.sh" << 'INNER_EOF'
#!/bin/bash
cd /opt/fitz14
source venv/bin/activate
exec python3 ui.py
INNER_EOF
chmod +x "$BUILD_DIR$APP_DIR/run_fitz.sh"

echo "📝 Создание control файла..."
cat > "$BUILD_DIR/DEBIAN/control" << 'INNER_EOF'
Package: fitz-guardian
Version: 1.4.0
Architecture: all
Maintainer: Ishira <ishira@example.com>
Depends: python3 (>= 3.8), python3-tk, python3-venv, espeak-ng, tesseract-ocr, tesseract-ocr-rus, xdotool, wmctrl
Description: Fitz Guardian - Digital Companion
 An AI assistant with voice, memory, and a graphical interface.
INNER_EOF

echo "🖥️ Создание ярлыка..."
cat > "$BUILD_DIR/usr/share/applications/fitz14.desktop" << 'INNER_EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Фитц 1.1.5.0
Comment=Digital Companion
Exec=/opt/fitz14/run_fitz.sh
Icon=/usr/share/icons/hicolor/256x256/apps/fitz14.png
Terminal=false
Categories=Utility;
INNER_EOF

echo "🔨 Сборка .deb..."
dpkg-deb --build "$BUILD_DIR" "fitz-guardian_1.4.0_all.deb"

echo "✅ Готово! Файл: fitz-guardian_1.4.0_all.deb"
