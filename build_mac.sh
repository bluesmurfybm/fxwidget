#!/bin/bash
# macOS용 fxwidget.app 빌드 스크립트
# 사용법: 터미널에서  chmod +x build_mac.sh && ./build_mac.sh
set -e
cd "$(dirname "$0")"

echo "[1/3] 의존 패키지 설치"
python3 -m pip install --user --upgrade pip requests pyinstaller >/dev/null

echo "[2/3] tkinter 확인"
python3 -c "import tkinter" || { echo "tkinter 없음. python.org 배포판 Python 설치 후 다시 실행하세요 (brew python은 'brew install python-tk' 필요)"; exit 1; }

echo "[3/3] .app 빌드"
rm -rf build_mac dist_mac
python3 -m PyInstaller --onefile --windowed --name fxwidget \
  --distpath dist_mac --workpath build_mac --specpath build_mac fxwidget.py

echo
echo "완료: $(pwd)/dist_mac/fxwidget.app"
echo "Finder에서 dist_mac/fxwidget.app 을 응용 프로그램 폴더로 옮겨 실행하세요."
echo "처음 실행 시 '확인되지 않은 개발자' 경고가 뜨면: 시스템 설정 > 개인정보 보호 및 보안 > '그래도 열기'"
