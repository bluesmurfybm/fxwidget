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

학교/회사망에서 네이버 API가 막힐 때 (Windows/Mac 공통)
--------------------------------------------------------
1. relay/fx.php 를 외부에서 접속 가능한 PHP 서버(회사 웹서버 등)에 업로드
2. 브라우저로 https://서버주소/경로/fx.php 열어 JSON이 나오는지 확인
3. 위젯 옆 fxwidget.json 을 열어 "relay_url": "https://서버주소/경로/fx.php" 입력 후 위젯 재시작
   → 위젯은 그 서버에만 접속하고, 서버가 대신 네이버에서 환율을 가져옵니다.
소스 우선순위: relay(설정 시) → 네이버 → open.er-api.com → api.frankfurter.app
