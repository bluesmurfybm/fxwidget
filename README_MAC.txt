fxwidget macOS 빌드 안내
========================

1. 맥에 Python 3 설치 (python.org 배포판 권장, tkinter 포함)
   https://www.python.org/downloads/macos/

2. fxwidget.py 와 build_mac.sh 두 파일을 맥의 한 폴더에 복사

3. 터미널에서:
   cd <복사한 폴더>
   chmod +x build_mac.sh
   ./build_mac.sh

4. dist_mac/fxwidget.app 생성됨. 응용 프로그램 폴더로 옮겨 실행.

첫 실행 경고
- "확인되지 않은 개발자" → 시스템 설정 > 개인정보 보호 및 보안 > 아래쪽 "그래도 열기"
- 또는 Finder에서 앱 우클릭 > 열기

빌드 없이 바로 실행하려면
   python3 -m pip install requests
   python3 fxwidget.py

Windows와 다른 점
- 우클릭 = 트랙패드 두 손가락 탭 / Ctrl+클릭. Command+Q 로도 종료 가능
- 자동 실행은 ~/Library/LaunchAgents/kr.bluesoft.fxwidget.plist 로 등록
- 설정 파일 fxwidget.json 은 .app 내부(Contents/MacOS)에 저장됨
