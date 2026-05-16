import sys
import os
import win32gui
import win32con
import win32api
import win32process
import subprocess
import time
import json
import logging
import ctypes
import threading
import pystray
from PIL import Image, ImageDraw

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable) # exe 파일이 있는 폴더
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # py 파일이 있는 폴더

MPV_PATH = os.path.join(BASE_DIR, "mpv", "mpv.exe")

def get_youtube_url():
    link_path = os.path.join(BASE_DIR, "link.txt")
    try:
        with open(link_path, "r", encoding="utf-8") as f:
            url = f.read().strip()
            if url.startswith("http"):
                return url
    except Exception as e:
        print(f"[LINK ERROR] {e}")

    return None

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "daemon_error.log"),
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)

# --- 설정 구간 ---
YOUTUBE_URL = get_youtube_url()
WINDOW_TITLE = "LiveWallpaper_MPV_Core"
IPC_PIPE = rf"\\.\pipe\mpv-wallpaper-socket-{os.getpid()}"
POLL_INTERVAL = 1.0
FULLSCREEN_ENTER_TICKS = 1
FULLSCREEN_EXIT_TICKS = 1
mpv_process = None
# ----------------


def get_workerw():
    progman = win32gui.FindWindow("Progman", None)

    win32gui.SendMessageTimeout(
        progman,
        0x052C,
        0,
        0,
        win32con.SMTO_NORMAL,
        1000
    )

    workerw = [0]

    def enum_windows(hwnd, lParam):
        if win32gui.FindWindowEx(
            hwnd,
            0,
            "SHELLDLL_DefView",
            None
        ) != 0:
            workerw[0] = win32gui.FindWindowEx(
                0,
                hwnd,
                "WorkerW",
                None
            )
        return True

    win32gui.EnumWindows(enum_windows, 0)

    return workerw[0]


def find_hwnd_by_pid(pid):

    def callback(hwnd, hwnds):

        if (
            win32gui.IsWindowVisible(hwnd)
            and win32gui.GetClassName(hwnd) == "mpv"
        ):
            _, found_pid = (
                win32process.GetWindowThreadProcessId(hwnd)
            )

            if found_pid == pid:
                hwnds.append(hwnd)

        return True

    hwnds = []

    win32gui.EnumWindows(callback, hwnds)

    return hwnds[0] if hwnds else None


def send_mpv_command(command_list):
    try:
        import win32file
        import win32pipe
        
        try:
            win32pipe.WaitNamedPipe(IPC_PIPE, 1000)
        except Exception:
            return False

        file_handle = win32file.CreateFile(
            IPC_PIPE,
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,
            0, None, win32file.OPEN_EXISTING, 0, None
        )

        msg = json.dumps({"command": command_list}) + "\n"
        win32file.WriteFile(file_handle, msg.encode())
        win32file.CloseHandle(file_handle)
        return True

    except Exception as e:
        print(f"[IPC ERROR] {e}")
        return False


def is_fullscreen():
    found = False

    def callback(hwnd, _):
        nonlocal found

        if found:
            return False

        try:
            # 1. 애초에 핸들이 살아있는지 선제 검사
            if not win32gui.IsWindow(hwnd):
                return True

            # 2. 기본 숨김 창 무시
            if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
                return True

            # 3. Windows 10/11 투명 망토(Cloaked) 앱 무시
            cloaked = ctypes.c_int(0)
            ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
            if cloaked.value != 0:
                return True

            # 4. 바탕화면 및 찌꺼기 UI 무시
            class_name = win32gui.GetClassName(hwnd)
            ignored = {
                "Progman", "WorkerW", "Shell_TrayWnd", 
                "DV2ControlHost", "Windows.UI.Core.CoreWindow",
                "TaskListThumbnailWnd", "mpv", 
                "DummyDWMWindow", "EdgeUiInputTopWnd"
            }
            if class_name in ignored:
                return True

            # 5. 최대화 상태 확인
            placement = win32gui.GetWindowPlacement(hwnd)
            if placement[1] == win32con.SW_SHOWMAXIMIZED:
                found = True
                return False

            # 6. 모니터 대비 창 크기 비율(Coverage) 계산 (95% 그림자 오차 허용)
            rect = win32gui.GetWindowRect(hwnd)
            monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
            
            if monitor:
                mon_rect = win32api.GetMonitorInfo(monitor)["Monitor"]

                win_w = rect[2] - rect[0]
                win_h = rect[3] - rect[1]
                mon_w = mon_rect[2] - mon_rect[0]
                mon_h = mon_rect[3] - mon_rect[1]

                if mon_w > 0 and mon_h > 0:
                    coverage_x = win_w / mon_w
                    coverage_y = win_h / mon_h

                    if coverage_x >= 0.95 and coverage_y >= 0.95:
                        found = True
                        return False

        except Exception:
            return True 

        return True 

    # EnumWindows 자체에서 튕기는 극단적인 경우까지 방어
    try:
        win32gui.EnumWindows(callback, None)
    except Exception:
        pass
        
    return found


def attach_window(hwnd, workerw):
    ex_style = win32gui.GetWindowLong(
        hwnd,
        win32con.GWL_EXSTYLE
    )
    if not (ex_style & win32con.WS_EX_TOOLWINDOW):
        win32gui.SetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE,
            ex_style | win32con.WS_EX_TOOLWINDOW
        )
    win32gui.SetParent(hwnd, workerw)
    win32gui.SetWindowPos(
        hwnd,
        win32con.HWND_BOTTOM,
        0,
        0,
        0,
        0,
        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
    )


def resize_window(hwnd, workerw):
    rect = win32gui.GetWindowRect(workerw)

    width = rect[2] - rect[0]
    height = rect[3] - rect[1]

    win32gui.SetWindowPos(
        hwnd,
        win32con.HWND_BOTTOM,
        0,
        0,
        width,
        height,
        win32con.SWP_NOACTIVATE
    )
    print(f"[Daemon] 해상도 동기화 ({width}x{height})")
    return rect


def run_wallpaper():
    global mpv_process, YOUTUBE_URL
    workerw = get_workerw()

    while True:
        mpv_cmd = [
            MPV_PATH,
            YOUTUBE_URL,
            f"--title={WINDOW_TITLE}",
            f"--input-ipc-server={IPC_PIPE}",
            "--force-window=yes",
            "--ytdl-format=bv*+ba/b",
            "--no-border",
            "--hwdec=auto-safe",
            "--profile=low-latency",
            "--idle=yes"
        ]
        mpv_process = subprocess.Popen(mpv_cmd, creationflags=subprocess.CREATE_NO_WINDOW)
        mpv_hwnd = None

        for _ in range(30):
            time.sleep(POLL_INTERVAL)
            mpv_hwnd = find_hwnd_by_pid(mpv_process.pid)
            if mpv_hwnd:
                break

        if not mpv_hwnd:
            mpv_process.kill()
            mpv_process.wait()
            continue

        attach_window(mpv_hwnd, workerw)
        last_rect = resize_window(mpv_hwnd, workerw)
        fs_ticks, ws_ticks = 0, 0
        is_paused = False

        while mpv_process.poll() is None:
            # explorer restart
            if not win32gui.IsWindow(workerw) or win32gui.FindWindowEx(workerw, 0, "SHELLDLL_DefView", None) != 0:
                workerw = get_workerw()
                if (mpv_hwnd and win32gui.IsWindow(mpv_hwnd)):
                    attach_window(mpv_hwnd, workerw)
                    last_rect = resize_window(mpv_hwnd, workerw)

            # resolution change
            if win32gui.IsWindow(workerw):
                current_rect = (win32gui.GetWindowRect(workerw))
                if current_rect != last_rect:
                    last_rect = resize_window(mpv_hwnd, workerw)
            
            if is_fullscreen():
                fs_ticks += 1
                ws_ticks = 0
            else:
                ws_ticks += 1
                fs_ticks = 0
            
            # fullscreen enter
            if not is_paused and fs_ticks >= FULLSCREEN_ENTER_TICKS:
                print("[Daemon] 🎮 전체화면 감지됨. 영상 일시정지(Pause) 요청.")
                if send_mpv_command(["set_property", "pause", True]):
                    is_paused = True
                fs_ticks = 0 
            elif is_paused and ws_ticks >= FULLSCREEN_EXIT_TICKS:
                print("[Daemon] 📺 바탕화면 복귀. 영상 재생(Unpause) 요청.")
                if send_mpv_command(["set_property", "pause", False]):
                    is_paused = False
                ws_ticks = 0
            time.sleep(POLL_INTERVAL)
        time.sleep(POLL_INTERVAL)

def restart_action(icon, item):
    global YOUTUBE_URL
    new_url = get_youtube_url()
    if not new_url:
        print("[Daemon] link.txt URL invalid")
        return
    if new_url != YOUTUBE_URL:
        YOUTUBE_URL = new_url
        send_mpv_command(["loadfile", YOUTUBE_URL, "replace"])
        send_mpv_command(["set_property", "pause", False])

def exit_action(icon, item):
    icon.stop()
    if mpv_process is not None:
        try: mpv_process.kill()
        except: pass
    os._exit(0)

def setup_tray():
    image = Image.new('RGB', (64, 64), color=(30, 30, 30))
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 16, 48, 48), fill=(0, 120, 255)) 

    menu = pystray.Menu(
        pystray.MenuItem('restart (새 링크 적용)', restart_action),
        pystray.MenuItem('Exit', exit_action)
    )
    icon = pystray.Icon("LiveWallpaper", image, "라이브 월페이퍼 데몬", menu)
    icon.run()

if __name__ == "__main__":
    wallpaper_thread = threading.Thread(target=run_wallpaper, daemon=True)
    wallpaper_thread.start()
    setup_tray()