---
## 폴더구조

📁 LiveWallpaper/
 ├── 🚀 wallpaper.py
 ├── 📝 link.txt
 └── 📁 mpv/
      └── 🎬 mpv.exe
---

## 개발자 가이드

파워쉘(PowerShell)에서 스크립트로 구동하기 위한 세팅 방법입니다.

### 1. 필수 의존성 라이브러리 설치

```powershell
pip install pywin32 pystray pillow

```

### 2. 백그라운드 데몬 실행

```powershell
cd "wallpaper.py가 있는 경로"

```

```powershell
pythonw .\wallpaper.py

```

---

## 🚀 사용자 가이드

1. `link.txt` 파일을 열고 배경화면으로 지정하고 싶은 유튜브 라이브 스트리밍 주소를 한 줄로 적고 저장합니다. (예: `https://www.youtube.com/live/jfKfPfyJRdk?si=3GuG56_fwvf3HmS4`)
2. wallpaper.exe를 실행합니다. 
3. **링크 변경 방법:** 프로그램 실행중 `link.txt`의 주소를 수정한 후, 작업 표시줄 우측 하단의 **시스템 트레이 아이콘(파란색 네모)을 우클릭**하여 `restart (새 링크 적용)` 메뉴를 클릭합니다.
4. **프로그램 종료:** 트레이 아이콘 우클릭 후 `Exit`를 누르면 mpv 프로세스와 데몬이 완전하게 동시 종료됩니다.

---

## ⚖️ 라이선스 (License)

* 동영상 재생의 핵심 코어인 `mpv`는 **GNU GPLv2 (or later)** 라이선스를 따르는 독립된 프로젝트입니다. 본 프로그램은 `mpv` 코어를 수정하지 않고 외부 IPC 인터페이스로만 격리하여 통신하므로, 본 소스 코드의 전면 공개 의무(GPL 전염성)가 발생하지 않는 단순 집적(Mere Aggregation) 구조입니다.
* 

---
