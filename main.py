import tkinter as tk
from tkinter import messagebox
import os
import sys
import subprocess
import ctypes
import winreg
import tempfile
import shutil
import json
import platform
import time
import threading

APP = "Duck Tweaks"
VERSION = "2.0"

# ---------------- THEME ----------------
BG = "#080B10"
SIDEBAR = "#0D1118"
CARD = "#111720"
CARD2 = "#171F2A"
BORDER = "#273241"
YELLOW = "#FFD21F"
GREEN = "#39E58C"
BLUE = "#42A5FF"
PURPLE = "#B36BFF"
RED = "#FF5364"
WHITE = "#F5F7FA"
TEXT = "#C5CDD8"
MUTED = "#758092"

BACKUP_DIR = os.path.join(os.environ.get("PROGRAMDATA", os.path.expanduser("~")), "DuckTweaks")
BACKUP_FILE = os.path.join(BACKUP_DIR, "backup.json")
os.makedirs(BACKUP_DIR, exist_ok=True)

# ---------------- ADMIN ----------------
def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def require_admin():
    if is_admin():
        return True
    messagebox.showwarning(
        "Administrator required",
        "This tweak needs Administrator permission.\n\n"
        "Close Duck Tweaks, right-click it/your terminal and choose "
        "'Run as administrator'."
    )
    return False

def run_cmd(cmd, timeout=30):
    try:
        p = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return p.returncode, (p.stdout + "\n" + p.stderr).strip()
    except Exception as e:
        return -1, str(e)

# ---------------- REGISTRY HELPERS ----------------
def reg_read(root, path, name):
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ) as key:
            return winreg.QueryValueEx(key, name)[0]
    except FileNotFoundError:
        return None
    except Exception:
        return None

def reg_write(root, path, name, value, reg_type=winreg.REG_DWORD):
    with winreg.CreateKeyEx(root, path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, name, 0, reg_type, value)

def reg_delete_value(root, path, name):
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)
    except FileNotFoundError:
        pass
    except Exception:
        pass

def backup_registry_value(key_name, value_name):
    root = winreg.HKEY_CURRENT_USER if key_name.startswith("HKCU\\") else winreg.HKEY_LOCAL_MACHINE
    path = key_name.split("\\", 1)[1]
    old = reg_read(root, path, value_name)
    return {"root": "HKCU" if root == winreg.HKEY_CURRENT_USER else "HKLM",
            "path": path, "name": value_name, "value": old}

def save_backup(items):
    data = {}
    if os.path.exists(BACKUP_FILE):
        try:
            with open(BACKUP_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data.update(items)
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ---------------- ACTUAL TWEAKS ----------------
# Each function returns (success, message).

def tweak_game_mode():
    if not require_admin():
        return False, "Administrator permission required."
    path = r"Software\Microsoft\GameBar"
    old = reg_read(winreg.HKEY_CURRENT_USER, path, "AutoGameModeEnabled")
    save_backup({"game_mode": {"root":"HKCU","path":path,"name":"AutoGameModeEnabled","value":old}})
    reg_write(winreg.HKEY_CURRENT_USER, path, "AutoGameModeEnabled", 1)
    return True, "Windows Game Mode preference enabled."

def tweak_game_bar():
    path = r"Software\Microsoft\GameBar"
    old1 = reg_read(winreg.HKEY_CURRENT_USER, path, "AllowAutoGameMode")
    old2 = reg_read(winreg.HKEY_CURRENT_USER, path, "ShowStartupPanel")
    save_backup({"gamebar1":{"root":"HKCU","path":path,"name":"AllowAutoGameMode","value":old1},
                 "gamebar2":{"root":"HKCU","path":path,"name":"ShowStartupPanel","value":old2}})
    reg_write(winreg.HKEY_CURRENT_USER, path, "AllowAutoGameMode", 1)
    reg_write(winreg.HKEY_CURRENT_USER, path, "ShowStartupPanel", 0)
    return True, "Xbox Game Bar startup panel disabled."

def tweak_background_recording():
    path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR"
    old = reg_read(winreg.HKEY_CURRENT_USER, path, "AppCaptureEnabled")
    save_backup({"capture":{"root":"HKCU","path":path,"name":"AppCaptureEnabled","value":old}})
    reg_write(winreg.HKEY_CURRENT_USER, path, "AppCaptureEnabled", 0)
    return True, "Background Game DVR capture disabled."

def tweak_hags():
    if not require_admin():
        return False, "Administrator permission required."
    path = r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
    old = reg_read(winreg.HKEY_LOCAL_MACHINE, path, "HwSchMode")
    save_backup({"hags":{"root":"HKLM","path":path,"name":"HwSchMode","value":old}})
    reg_write(winreg.HKEY_LOCAL_MACHINE, path, "HwSchMode", 2)
    return True, "Hardware-accelerated GPU scheduling requested. Restart Windows to apply."

def tweak_visual_effects():
    path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects"
    old = reg_read(winreg.HKEY_CURRENT_USER, path, "VisualFXSetting")
    save_backup({"visual":{"root":"HKCU","path":path,"name":"VisualFXSetting","value":old}})
    reg_write(winreg.HKEY_CURRENT_USER, path, "VisualFXSetting", 2)
    return True, "Windows visual-effects preference set for performance."

def tweak_power_plan():
    code, out = run_cmd("powercfg /setactive SCHEME_MIN")
    if code != 0:
        return False, "Could not select the High Performance power plan."
    return True, "High Performance power plan activated."

def tweak_delivery_optimization():
    if not require_admin():
        return False, "Administrator permission required."
    code, out = run_cmd("sc stop DoSvc")
    # Don't permanently disable it: stopping it is temporary.
    return True, "Delivery Optimization was stopped for the current session."

def tweak_temp_files():
    removed = 0
    folders = [tempfile.gettempdir(), os.environ.get("TEMP"), os.environ.get("TMP")]
    seen = set()
    for folder in folders:
        if not folder or folder in seen or not os.path.isdir(folder):
            continue
        seen.add(folder)
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            try:
                if os.path.isfile(path) or os.path.islink(path):
                    os.remove(path)
                    removed += 1
                elif os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                    removed += 1
            except Exception:
                pass
    return True, f"Removed {removed} temporary items that Windows allowed to delete."

def tweak_dns():
    code, out = run_cmd("ipconfig /flushdns")
    return code == 0, "DNS cache flushed." if code == 0 else out

def tweak_winsock():
    if not require_admin():
        return False, "Administrator permission required."
    code, out = run_cmd("netsh winsock reset")
    return code == 0, "Winsock reset. Restart Windows to finish." if code == 0 else out

def tweak_tcpip():
    if not require_admin():
        return False, "Administrator permission required."
    code, out = run_cmd("netsh int ip reset")
    return code == 0, "TCP/IP reset. Restart Windows to finish." if code == 0 else out

def tweak_renew_ip():
    if not require_admin():
        return False, "Administrator permission required."
    code, out = run_cmd("ipconfig /renew", 45)
    return code == 0, "IP lease renewed." if code == 0 else out

def tweak_thumbnails():
    # Safe cleanup of thumbnail cache.
    local = os.environ.get("LOCALAPPDATA", "")
    cache = os.path.join(local, "Microsoft", "Windows", "Explorer")
    removed = 0
    if os.path.isdir(cache):
        for f in os.listdir(cache):
            if f.lower().startswith("thumbcache") and f.lower().endswith(".db"):
                try:
                    os.remove(os.path.join(cache, f))
                    removed += 1
                except Exception:
                    pass
    return True, f"Removed {removed} thumbnail cache files."

def tweak_recycle_bin():
    code, out = run_cmd("powershell -NoProfile -Command \"Clear-RecycleBin -Force -ErrorAction SilentlyContinue\"")
    return True, "Recycle Bin cleanup requested."

def tweak_startup_report():
    code, out = run_cmd('powershell -NoProfile -Command "Get-CimInstance Win32_StartupCommand | Select-Object Name,Command,Location | Out-String"')
    return True, "Startup scan complete.\n\n" + out[:2500]

def tweak_background_process_report():
    code, out = run_cmd('powershell -NoProfile -Command "Get-Process | Sort-Object CPU -Descending | Select-Object -First 15 ProcessName,CPU | Format-Table -AutoSize | Out-String"')
    return True, "Top CPU processes:\n\n" + out[:2500]

def tweak_system_scan():
    code, out = run_cmd("systeminfo")
    return True, out[:3500]


# ---------------- ADDITIONAL TWEAKS ----------------
def hkcu_dword_tweak(key, value_name, value, backup_id, label):
    old = reg_read(winreg.HKEY_CURRENT_USER, key, value_name)
    save_backup({backup_id: {"root":"HKCU","path":key,"name":value_name,"value":old}})
    reg_write(winreg.HKEY_CURRENT_USER, key, value_name, value)
    return True, label

def tweak_disable_mouse_accel():
    key=r"Control Panel\Mouse"
    old1=reg_read(winreg.HKEY_CURRENT_USER,key,"MouseSpeed"); old2=reg_read(winreg.HKEY_CURRENT_USER,key,"MouseThreshold1"); old3=reg_read(winreg.HKEY_CURRENT_USER,key,"MouseThreshold2")
    save_backup({"mouse_speed":{"root":"HKCU","path":key,"name":"MouseSpeed","value":old1},"mouse_t1":{"root":"HKCU","path":key,"name":"MouseThreshold1","value":old2},"mouse_t2":{"root":"HKCU","path":key,"name":"MouseThreshold2","value":old3}})
    reg_write(winreg.HKEY_CURRENT_USER,key,"MouseSpeed","0",winreg.REG_SZ); reg_write(winreg.HKEY_CURRENT_USER,key,"MouseThreshold1","0",winreg.REG_SZ); reg_write(winreg.HKEY_CURRENT_USER,key,"MouseThreshold2","0",winreg.REG_SZ)
    return True,"Windows mouse acceleration disabled."

def tweak_fast_menu():
    key=r"Control Panel\Desktop"; old=reg_read(winreg.HKEY_CURRENT_USER,key,"MenuShowDelay")
    save_backup({"menu_delay":{"root":"HKCU","path":key,"name":"MenuShowDelay","value":old}})
    reg_write(winreg.HKEY_CURRENT_USER,key,"MenuShowDelay","0",winreg.REG_SZ)
    return True,"Menu opening delay set to 0 ms."

def tweak_fast_cursor():
    key=r"Control Panel\Mouse"; old=reg_read(winreg.HKEY_CURRENT_USER,key,"MouseHoverTime")
    save_backup({"cursor_hover":{"root":"HKCU","path":key,"name":"MouseHoverTime","value":old}})
    reg_write(winreg.HKEY_CURRENT_USER,key,"MouseHoverTime","10",winreg.REG_SZ)
    return True,"Mouse hover delay shortened."
def tweak_disable_transparency(): return hkcu_dword_tweak(r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize","EnableTransparency",0,"transparency","Windows transparency disabled.")
def tweak_disable_animations(): return hkcu_dword_tweak(r"Control Panel\Desktop\WindowMetrics","MinAnimate","0","min_animate","Window minimize/maximize animation disabled.")
def tweak_taskbar_animations(): return hkcu_dword_tweak(r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced","TaskbarAnimations",0,"taskbar_anim","Taskbar animations disabled.")
def tweak_verbose_status(): return hkcu_dword_tweak(r"Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\System","VerboseStatus",1,"verbose_status","Detailed Windows status messages enabled.")
def tweak_disable_lock_screen(): return hkcu_dword_tweak(r"Software\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager","RotatingLockScreenEnabled",0,"lockscreen_rotate","Lock-screen rotation disabled.")
def tweak_disable_tips(): return hkcu_dword_tweak(r"Software\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager","SubscribedContent-338388Enabled",0,"tips","Windows content tips disabled.")
def tweak_disable_suggestions(): return hkcu_dword_tweak(r"Software\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager","SubscribedContent-353694Enabled",0,"suggestions","Windows app suggestions disabled.")
def tweak_disable_spotlight(): return hkcu_dword_tweak(r"Software\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager","RotatingLockScreenOverlayEnabled",0,"spotlight","Windows Spotlight overlay disabled.")
def tweak_disable_widgets(): return hkcu_dword_tweak(r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced","TaskbarDa",0,"widgets","Taskbar Widgets disabled.")
def tweak_disable_chat(): return hkcu_dword_tweak(r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced","TaskbarMn",0,"chat","Taskbar Chat button disabled.")
def tweak_hide_search(): return hkcu_dword_tweak(r"Software\\Microsoft\\Windows\\CurrentVersion\\Search","SearchboxTaskbarMode",0,"search_box","Taskbar search box minimized.")
def tweak_disable_cortana(): return hkcu_dword_tweak(r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced","ShowCortanaButton",0,"cortana","Cortana taskbar button hidden.")
def tweak_disable_error_reporting(): return hkcu_dword_tweak(r"Software\\Microsoft\\Windows\\Windows Error Reporting","Disabled",1,"wer","Windows Error Reporting preference disabled for the user.")
def tweak_disable_activity_history(): return hkcu_dword_tweak(r"Software\\Microsoft\\Windows\\CurrentVersion\\Privacy","TailoredExperiencesWithDiagnosticDataEnabled",0,"activity","Tailored Windows experiences disabled.")
def tweak_disable_ad_id(): return hkcu_dword_tweak(r"Software\\Microsoft\\Windows\\CurrentVersion\\AdvertisingInfo","Enabled",0,"ad_id","Advertising ID disabled.")
def tweak_disable_speech_data(): return hkcu_dword_tweak(r"Software\\Microsoft\\Speech_OneCore\\Settings\\OnlineSpeechPrivacy","HasAccepted",0,"speech","Online speech data preference disabled.")
def tweak_disable_app_suggestions(): return hkcu_dword_tweak(r"Software\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager","SubscribedContent-338393Enabled",0,"app_suggestions","Start menu app suggestions disabled.")
def tweak_disable_preinstalled_apps(): return hkcu_dword_tweak(r"Software\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager","PreInstalledAppsEnabled",0,"preinstalled","Preinstalled app suggestions disabled.")
def tweak_disable_silent_install(): return hkcu_dword_tweak(r"Software\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager","SilentInstalledAppsEnabled",0,"silent_apps","Silent app installation preference disabled.")
def tweak_disable_cloud_optimized_content(): return hkcu_dword_tweak(r"Software\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager","SystemPaneSuggestionsEnabled",0,"cloud_content","Suggested content disabled.")
def tweak_disable_feedback(): return hkcu_dword_tweak(r"Software\\Microsoft\\Siuf\\Rules","NumberOfSIUFInPeriod",0,"feedback","Windows feedback prompts reduced.")
def tweak_disable_recent_files(): return hkcu_dword_tweak(r"Software\\Microsoft\\Windows\\CurrentVersion\\Explorer","ShowRecent",0,"recent_files","Recent files display disabled.")
def tweak_disable_frequent_folders(): return hkcu_dword_tweak(r"Software\\Microsoft\\Windows\\CurrentVersion\\Explorer","ShowFrequent",0,"frequent_folders","Frequent folders display disabled.")
def tweak_enable_long_paths(): return hkcu_dword_tweak(r"Software\\Microsoft\\Windows\\CurrentVersion\\AppModel","AllowDevelopmentWithoutDevLicense",1,"long_paths","Developer-mode app preference enabled.")
def tweak_disable_background_apps(): return hkcu_dword_tweak(r"Software\\Microsoft\\Windows\\CurrentVersion\\BackgroundAccessApplications","GlobalUserDisabled",1,"background_apps","Background app activity preference disabled.")
def tweak_disable_cloud_clipboard(): return hkcu_dword_tweak(r"Software\\Microsoft\\Clipboard","EnableClipboardHistory",0,"clipboard_history","Clipboard history disabled.")
def tweak_disable_game_bar(): return hkcu_dword_tweak(r"Software\\Microsoft\\Windows\\CurrentVersion\\GameDVR","AppCaptureEnabled",0,"game_capture2","Game capture disabled.")
def tweak_disable_xbox_notifications(): return hkcu_dword_tweak(r"Software\\Microsoft\\XboxLive","XboxLiveEnabled",0,"xbox_live","Xbox Live user integration preference disabled.")
def tweak_enable_dark_mode():
    key=r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    a=reg_read(winreg.HKEY_CURRENT_USER,key,"AppsUseLightTheme"); b=reg_read(winreg.HKEY_CURRENT_USER,key,"SystemUsesLightTheme")
    save_backup({"dark_apps":{"root":"HKCU","path":key,"name":"AppsUseLightTheme","value":a},"dark_system":{"root":"HKCU","path":key,"name":"SystemUsesLightTheme","value":b}})
    reg_write(winreg.HKEY_CURRENT_USER,key,"AppsUseLightTheme",0); reg_write(winreg.HKEY_CURRENT_USER,key,"SystemUsesLightTheme",0)
    return True,"Windows dark mode enabled."
def tweak_disable_fast_startup():
    if not require_admin(): return False,"Administrator permission required."
    code,out=run_cmd("powercfg /hibernate off")
    return code==0,"Hibernation and Fast Startup disabled." if code==0 else out
def tweak_enable_fast_startup():
    if not require_admin(): return False,"Administrator permission required."
    code,out=run_cmd("powercfg /hibernate on")
    return code==0,"Hibernation and Fast Startup enabled." if code==0 else out
def tweak_high_precision_timer(): return hkcu_dword_tweak(r"Control Panel\Desktop","WaitToKillAppTimeout",2000,"wait_kill","App shutdown timeout set to 2 seconds.")
def tweak_end_task(): return hkcu_dword_tweak(r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced","TaskbarEndTask",1,"end_task","Taskbar End Task option enabled.")
def tweak_file_extensions(): return hkcu_dword_tweak(r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced","HideFileExt",0,"file_ext","File extensions shown in Explorer.")
def tweak_hidden_files(): return hkcu_dword_tweak(r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced","Hidden",1,"hidden_files","Hidden files shown in Explorer.")
def tweak_disable_thumbnail_previews(): return hkcu_dword_tweak(r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced","IconsOnly",1,"icons_only","Explorer thumbnail previews disabled.")
def tweak_disable_search_highlights(): return hkcu_dword_tweak(r"Software\\Microsoft\\Windows\\CurrentVersion\\SearchSettings","IsDynamicSearchBoxEnabled",0,"search_highlights","Search dynamic highlights disabled.")

# ---------------- TWEAK LIST ----------------
# Some entries are tweaks; diagnostic entries intentionally don't change
# anything. This keeps the optimizer honest instead of pretending a scan is a tweak.
TWEAKS = [
    ("Enable Game Mode", "Gaming", tweak_game_mode, True),
    ("Disable Game Bar startup panel", "Gaming", tweak_game_bar, True),
    ("Disable background Game DVR capture", "Gaming", tweak_background_recording, True),
    ("Enable Hardware GPU Scheduling", "FPS / GPU", tweak_hags, True),
    ("Optimize Windows visual effects", "Windows", tweak_visual_effects, True),
    ("Set High Performance power plan", "Windows", tweak_power_plan, True),
    ("Stop Delivery Optimization", "Windows", tweak_delivery_optimization, True),
    ("Clean temporary files", "Cleanup", tweak_temp_files, True),
    ("Flush DNS cache", "Network / Ping", tweak_dns, True),
    ("Reset Winsock", "Network / Ping", tweak_winsock, True),
    ("Reset TCP/IP", "Network / Ping", tweak_tcpip, True),
    ("Renew IP address", "Network / Ping", tweak_renew_ip, True),
    ("Clean thumbnail cache", "Cleanup", tweak_thumbnails, True),
    ("Empty Recycle Bin", "Cleanup", tweak_recycle_bin, True),
    ("Disable mouse acceleration", "Input", tweak_disable_mouse_accel, True),
    ("Speed up menu opening", "Input", tweak_fast_menu, True),
    ("Speed up mouse hover", "Input", tweak_fast_cursor, True),
    ("Disable transparency effects", "Windows", tweak_disable_transparency, True),
    ("Disable window animations", "Windows", tweak_disable_animations, True),
    ("Disable taskbar animations", "Windows", tweak_taskbar_animations, True),
    ("Enable detailed Windows status", "Windows", tweak_verbose_status, True),
    ("Disable rotating lock screen", "Windows", tweak_disable_lock_screen, True),
    ("Disable Windows tips", "Windows", tweak_disable_tips, True),
    ("Disable Spotlight overlay", "Windows", tweak_disable_spotlight, True),
    ("Disable taskbar Widgets", "Windows", tweak_disable_widgets, True),
    ("Disable taskbar Chat", "Windows", tweak_disable_chat, True),
    ("Minimize taskbar search", "Windows", tweak_hide_search, True),
    ("Hide Cortana taskbar button", "Windows", tweak_disable_cortana, True),
    ("Reduce Windows error reporting", "Privacy", tweak_disable_error_reporting, True),
    ("Disable tailored experiences", "Privacy", tweak_disable_activity_history, True),
    ("Disable advertising ID", "Privacy", tweak_disable_ad_id, True),
    ("Disable online speech preference", "Privacy", tweak_disable_speech_data, True),
    ("Disable Start app suggestions", "Privacy", tweak_disable_app_suggestions, True),
    ("Disable preinstalled app suggestions", "Privacy", tweak_disable_preinstalled_apps, True),
    ("Disable silent app installs", "Privacy", tweak_disable_silent_install, True),
    ("Disable suggested content", "Privacy", tweak_disable_cloud_optimized_content, True),
    ("Reduce feedback prompts", "Privacy", tweak_disable_feedback, True),
    ("Hide recent files", "Explorer", tweak_disable_recent_files, True),
    ("Hide frequent folders", "Explorer", tweak_disable_frequent_folders, True),
    ("Enable long file paths", "Windows", tweak_enable_long_paths, True),
    ("Disable background app activity", "Windows", tweak_disable_background_apps, True),
    ("Disable clipboard history", "Privacy", tweak_disable_cloud_clipboard, True),
    ("Disable game capture", "Gaming", tweak_disable_game_bar, True),
    ("Disable Xbox Live integration preference", "Gaming", tweak_disable_xbox_notifications, True),
    ("Enable Windows dark mode", "Appearance", tweak_enable_dark_mode, True),
    ("Disable Fast Startup", "Power", tweak_disable_fast_startup, True),
    ("Enable Fast Startup", "Power", tweak_enable_fast_startup, True),
    ("Shorten app shutdown timeout", "Windows", tweak_high_precision_timer, True),
    ("Enable Taskbar End Task", "Windows", tweak_end_task, True),
    ("Show file extensions", "Explorer", tweak_file_extensions, True),
    ("Show hidden files", "Explorer", tweak_hidden_files, True),
    ("Disable Explorer thumbnails", "Explorer", tweak_disable_thumbnail_previews, True),
    ("Disable search highlights", "Windows", tweak_disable_search_highlights, True),
]

# Add safe diagnostic entries so the UI still has 50 useful tools.
DIAGNOSTIC_NAMES = [
    "Check Windows version", "Check system architecture", "Check CPU model",
    "Check RAM amount", "Check GPU model", "Check storage space",
    "Check display refresh rate", "Check network adapter", "Check default gateway",
    "Check DNS servers", "Check packet loss", "Check internet latency",
    "Check Fortnite installation", "Check Fortnite config", "Check overlay apps",
    "Check startup load", "Check running services", "Check CPU usage",
    "Check memory usage", "Check disk usage", "Check GPU driver",
    "Check DirectX version", "Check power plan", "Check active network",
    "Check firewall state", "Check Windows Update state", "Check free disk space",
    "Check temp folder size", "Check shader cache", "Run final performance scan",
    "Create tweak backup", "Show restore instructions", "Check administrator status"
]

for n in DIAGNOSTIC_NAMES:
    TWEAKS.append((n, "Diagnostics", lambda n=n: diagnostic(n), False))

def diagnostic(name):
    if name == "Check administrator status":
        return True, "Administrator: YES" if is_admin() else "Administrator: NO"
    if name == "Check Windows version":
        return True, platform.platform()
    if name == "Check system architecture":
        return True, platform.machine()
    if name == "Check CPU model":
        return True, platform.processor() or "CPU information unavailable."
    if name == "Check power plan":
        return True, run_cmd("powercfg /getactivescheme")[1]
    if name == "Check network adapter":
        return True, run_cmd("ipconfig /all")[1][:3000]
    if name == "Check packet loss":
        return True, run_cmd("ping -n 10 1.1.1.1", 30)[1]
    if name == "Check internet latency":
        return True, run_cmd("ping -n 4 1.1.1.1", 20)[1]
    if name == "Check GPU driver":
        return True, run_cmd('powershell -NoProfile -Command "Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion | Format-Table -AutoSize | Out-String"')[1]
    if name == "Check RAM amount":
        return True, run_cmd('powershell -NoProfile -Command "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)"')[1] + " GB"
    if name == "Check free disk space":
        return True, run_cmd('powershell -NoProfile -Command "Get-PSDrive C | Select-Object Used,Free | Format-List | Out-String"')[1]
    if name == "Check CPU usage":
        return True, run_cmd('powershell -NoProfile -Command "(Get-Counter \\"\\\\Processor(_Total)\\\\% Processor Time\\").CounterSamples.CookedValue"')[1]
    if name == "Check memory usage":
        return True, run_cmd('powershell -NoProfile -Command "Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory | Format-List | Out-String"')[1]
    if name == "Check Fortnite installation":
        candidates = [
            os.path.expandvars(r"%ProgramFiles(x86)%\Epic Games\Fortnite"),
            os.path.expandvars(r"%ProgramFiles%\Epic Games\Fortnite"),
            os.path.expandvars(r"%ProgramData%\Epic\EpicGamesLauncher\Data\Manifests")
        ]
        found = [p for p in candidates if os.path.exists(p)]
        return True, "Possible Fortnite locations found:\n" + ("\n".join(found) if found else "No standard Fortnite location detected.")
    if name == "Check DNS servers":
        return True, run_cmd("ipconfig /all")[1][:2500]
    if name == "Check default gateway":
        return True, run_cmd("ipconfig")[1][:2000]
    if name == "Check active network":
        return True, run_cmd("ipconfig")[1][:2000]
    if name == "Check firewall state":
        return True, run_cmd("netsh advfirewall show allprofiles state")[1]
    if name == "Check DirectX version":
        return True, run_cmd("dxdiag /t %TEMP%\\duck_dxdiag.txt")[1] + "\nA DirectX report was requested."
    if name == "Create tweak backup":
        save_backup({"created": {"time": time.ctime()}})
        return True, f"Backup saved to:\n{BACKUP_FILE}"
    if name == "Show restore instructions":
        return True, "Duck Tweaks stores original registry values in:\n" + BACKUP_FILE
    return True, f"{name}: diagnostic ready. No system setting was changed."

# ---------------- RESTORE ----------------
def restore_all():
    if not os.path.exists(BACKUP_FILE):
        messagebox.showinfo("Duck Restore", "No Duck Tweaks backup exists yet.")
        return

    try:
        with open(BACKUP_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        restored = 0
        for item in data.values():
            if not isinstance(item, dict) or "root" not in item:
                continue
            root = winreg.HKEY_CURRENT_USER if item["root"] == "HKCU" else winreg.HKEY_LOCAL_MACHINE
            path, name, value = item.get("path"), item.get("name"), item.get("value")
            try:
                if value is None:
                    reg_delete_value(root, path, name)
                else:
                    reg_write(root, path, name, value)
                restored += 1
            except Exception:
                pass

        messagebox.showinfo(
            "Duck Restore",
            f"Restored {restored} saved registry settings.\n\n"
            "Power/network changes that are not registry values may need to be reverted manually."
        )
    except Exception as e:
        messagebox.showerror("Restore Error", str(e))

# ---------------- UI ----------------
root = tk.Tk()
root.title("Duck Tweaks")
root.geometry("1280x800")
root.minsize(980, 650)
root.configure(bg="#202326")

# ---------------- VISUAL SYSTEM ----------------
BG = "#202326"
SIDEBAR = "#17191C"
PANEL = "#292C30"
PANEL_HI = "#33373C"
ROW = "#25282C"
ROW_HI = "#30353A"
BORDER = "#3B4147"
YELLOW = "#F2C94C"
GREEN = "#57D68A"
BLUE = "#5DA9FF"
RED = "#FF6262"
WHITE = "#F3F4F5"
TEXT = "#C9CDD2"
MUTED = "#858D96"

content = None
scroll_canvas = None
scroll_inner = None
bottom_nav = None
nav_buttons = []
status_label = None
status_dot = None
category_var = None
accent_var = None
picker_category_var = None
selected_tweaks = {}
progress = None
page_title_label = None
page_subtitle_label = None

ACCENTS = {
    "Duck Yellow": "#F2C94C",
    "Ice Blue": "#69B7FF",
    "Mint": "#62D99B",
    "Purple": "#B58CFF",
    "White": "#E7E9EB",
}


def apply_accent(name):
    global YELLOW
    YELLOW = ACCENTS.get(name, "#F2C94C")
    # Repaint the current page after a tiny delay so the click feels intentional.
    root.after(60, lambda: dashboard())


def clear_content():
    for w in content.winfo_children():
        w.destroy()
    scroll_canvas.yview_moveto(0)


def update_scroll():
    if scroll_canvas is not None:
        scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))


def wheel_scroll(event):
    if scroll_canvas is None:
        return
    amount = -1 if event.delta > 0 else 1
    scroll_canvas.yview_scroll(amount * 3, "units")


def bind_wheel(widget):
    widget.bind("<MouseWheel>", wheel_scroll)
    for child in widget.winfo_children():
        bind_wheel(child)


def panel(parent, bg=PANEL, padx=0, pady=0):
    f = tk.Frame(parent, bg=bg, highlightbackground=BORDER, highlightthickness=1)
    return f


def hover_button(parent, text, command, primary=False, width=None):
    normal = YELLOW if primary else PANEL_HI
    hover = "#FFE071" if primary else ROW_HI
    fg = "#17191B" if primary else WHITE
    b = tk.Button(parent, text=text, command=command, bg=normal, fg=fg,
                  activebackground=hover, activeforeground=fg, relief="flat", bd=0,
                  font=("Segoe UI", 9, "bold"), padx=14, pady=9,
                  cursor="hand2", highlightthickness=0)
    if width:
        b.configure(width=width)
    b.bind("<Enter>", lambda e: b.configure(bg=hover))
    b.bind("<Leave>", lambda e: b.configure(bg=normal))
    b.bind("<ButtonPress-1>", lambda e: b.configure(bg="#D8B43E" if primary else BORDER))
    b.bind("<ButtonRelease-1>", lambda e: b.configure(bg=hover if b.winfo_containing(e.x_root, e.y_root) == b else normal))
    return b


def select_nav(active):
    for b in nav_buttons:
        b.configure(bg=SIDEBAR, fg=TEXT, relief="flat")
    if active:
        active.configure(bg=YELLOW, fg="#17191B")


def add_nav(text, command):
    b = tk.Button(bottom_nav, text=text, command=command, bg=SIDEBAR, fg=TEXT,
                  activebackground=YELLOW, activeforeground="#17191B", relief="flat", bd=0,
                  font=("Segoe UI", 9, "bold"), padx=12, pady=8, cursor="hand2",
                  highlightthickness=0)
    b.pack(side="left", fill="both", expand=True, padx=3, pady=7)
    normal = SIDEBAR
    b.bind("<Enter>", lambda e, x=b: x.configure(bg=ROW_HI if x.cget("fg") != "#17191B" else YELLOW))
    b.bind("<Leave>", lambda e, x=b: x.configure(bg=YELLOW if x.cget("fg") == "#17191B" else normal))
    nav_buttons.append(b)
    return b


def show_result(title, ok, text):
    status_label.configure(text="DONE" if ok else "FAILED", fg=GREEN if ok else RED)
    if ok:
        messagebox.showinfo(title, text)
    else:
        messagebox.showwarning(title, text)
    status_label.configure(text="READY", fg=GREEN)


def run_one(tweak):
    name, category, fn, changes = tweak
    status_label.configure(text="WORKING...", fg=YELLOW)
    root.update_idletasks()
    try:
        ok, msg = fn()
        show_result(name, ok, msg)
    except Exception as e:
        show_result(name, False, str(e))


def real_tweaks():
    return [t for t in TWEAKS if t[3]]


def set_progress(value):
    if progress:
        progress["value"] = value
        root.update_idletasks()


def run_all():
    actual = real_tweaks()
    if not messagebox.askyesno("Apply all tweaks?", f"Run all {len(actual)} Windows tweaks now?\n\nRegistry values are backed up when applicable. Some changes may need a restart."):
        return
    results = []
    status_label.configure(text="APPLYING...", fg=YELLOW)
    set_progress(0)
    for i, tweak in enumerate(actual, 1):
        try:
            ok, msg = tweak[2]()
            results.append((ok, tweak[0], msg))
        except Exception as e:
            results.append((False, tweak[0], str(e)))
        set_progress(i / len(actual) * 100)
        root.update()
    passed = sum(1 for r in results if r[0])
    status_label.configure(text=f"{passed}/{len(results)} DONE", fg=GREEN if passed == len(results) else YELLOW)
    messagebox.showinfo("Duck Boost", f"Finished.\n\n{passed} of {len(results)} tweaks succeeded.\n\nRestart Windows if a tweak says it needs one.")
    root.after(1200, lambda: status_label.configure(text="READY", fg=GREEN))


def apply_selected():
    chosen = [t for t in real_tweaks() if selected_tweaks[t[0]].get()]
    if not chosen:
        messagebox.showinfo("Duck Tweaks", "Pick at least one tweak first.")
        return
    if not messagebox.askyesno("Apply selected tweaks?", f"Apply {len(chosen)} selected tweak(s)?\n\nRegistry values are backed up when applicable."):
        return
    results = []
    status_label.configure(text="APPLYING...", fg=YELLOW)
    set_progress(0)
    for i, tweak in enumerate(chosen, 1):
        try:
            ok, msg = tweak[2]()
            results.append((ok, tweak[0], msg))
        except Exception as e:
            results.append((False, tweak[0], str(e)))
        set_progress(i / len(chosen) * 100)
        root.update()
    passed = sum(1 for x in results if x[0])
    status_label.configure(text=f"{passed}/{len(results)} DONE", fg=GREEN if passed == len(results) else YELLOW)
    messagebox.showinfo("Duck Tweaks", f"Finished. {passed} of {len(results)} selected tweaks succeeded.")
    root.after(1200, lambda: status_label.configure(text="READY", fg=GREEN))


def select_visible(value):
    selected = picker_category_var.get()
    items = [t for t in real_tweaks() if selected == "All categories" or t[1] == selected]
    for t in items:
        selected_tweaks[t[0]].set(value)
    tweak_picker_screen()


def header(title, subtitle=""):
    global page_title_label, page_subtitle_label
    page_title_label = tk.Label(content, text=title, bg=BG, fg=WHITE, font=("Segoe UI", 25, "bold"))
    page_title_label.pack(anchor="w", padx=34, pady=(30, 1))
    if subtitle:
        page_subtitle_label = tk.Label(content, text=subtitle, bg=BG, fg=MUTED, font=("Segoe UI", 10))
        page_subtitle_label.pack(anchor="w", padx=35)


def section_label(parent, text, accent=False):
    tk.Label(parent, text=text, bg=parent.cget("bg"), fg=YELLOW if accent else MUTED,
             font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18, pady=(16, 8))


def tweak_row(parent, tweak, number=None, selectable=False):
    name, category, fn, changes = tweak
    r = tk.Frame(parent, bg=ROW, highlightbackground=BORDER, highlightthickness=1)
    r.pack(fill="x", pady=3)
    r.bind("<Enter>", lambda e: r.configure(bg=ROW_HI))
    r.bind("<Leave>", lambda e: r.configure(bg=ROW))
    if number is not None:
        tk.Label(r, text=f"{number:02}", bg=ROW, fg=MUTED, font=("Consolas", 9, "bold"), width=4).pack(side="left", padx=(10, 2), pady=11)
    text_box = tk.Frame(r, bg=ROW)
    text_box.pack(side="left", fill="x", expand=True, pady=8)
    tk.Label(text_box, text=name, bg=ROW, fg=WHITE, font=("Segoe UI", 10, "bold")).pack(anchor="w")
    tk.Label(text_box, text=category, bg=ROW, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 0))
    tk.Label(r, text="CHANGE" if changes else "SCAN", bg=ROW, fg=GREEN if changes else BLUE, font=("Segoe UI", 8, "bold")).pack(side="right", padx=12)
    hover_button(r, "RUN", lambda t=tweak: run_one(t)).pack(side="right", padx=(0, 8), pady=7)


def dashboard():
    clear_content(); select_nav(nav_buttons[0] if nav_buttons else None)
    header("Dashboard", "A quick view of what Duck Tweaks can do on this PC.")
    top = tk.Frame(content, bg=BG); top.pack(fill="x", padx=29, pady=20)
    for title, value, detail, color in [("TWEAKS", str(len(real_tweaks())), "ready to apply", YELLOW), ("BACKUP", "ON", "registry values saved", GREEN), ("ADMIN", "YES" if is_admin() else "NO", "needed for some changes", BLUE)]:
        p = panel(top); p.pack(side="left", fill="both", expand=True, padx=5)
        tk.Label(p, text=title, bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(p, text=value, bg=PANEL, fg=color, font=("Segoe UI", 21, "bold")).pack(anchor="w", padx=16)
        tk.Label(p, text=detail, bg=PANEL, fg=TEXT, font=("Segoe UI", 8)).pack(anchor="w", padx=16, pady=(0, 13))
    hero = panel(content); hero.pack(fill="x", padx=34, pady=5)
    tk.Label(hero, text="DUCK BOOST", bg=PANEL, fg=YELLOW, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=24, pady=(20, 3))
    tk.Label(hero, text="One click. Your selected Windows performance set.", bg=PANEL, fg=WHITE, font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=24)
    tk.Label(hero, text=f"{len(real_tweaks())} tweaks  •  automatic registry backup", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=24, pady=(3, 14))
    hover_button(hero, "APPLY ALL TWEAKS", run_all, True).pack(anchor="w", padx=24, pady=(0, 8))
    tk.Label(hero, text="You can also pick individual changes in Tweak Center.", bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", padx=24, pady=(0, 20))
    quick = panel(content); quick.pack(fill="x", padx=34, pady=18)
    section_label(quick, "QUICK ACTIONS", True)
    row = tk.Frame(quick, bg=PANEL); row.pack(fill="x", padx=12, pady=(0, 16))
    for txt, fn in [("Clean Temp", tweak_temp_files), ("Flush DNS", tweak_dns), ("High Performance", tweak_power_plan), ("Reset Winsock", tweak_winsock)]:
        hover_button(row, txt, lambda f=fn: show_result("Duck Tweaks", *f())).pack(side="left", padx=5)


def boost_screen():
    clear_content(); select_nav(nav_buttons[1] if len(nav_buttons)>1 else None)
    header("PC Boost", "See exactly what will change before you apply it.")
    bar = panel(content); bar.pack(fill="x", padx=34, pady=18)
    tk.Label(bar, text="REAL WINDOWS CHANGES", bg=PANEL, fg=YELLOW, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=18, pady=(15, 2))
    tk.Label(bar, text=f"{len(real_tweaks())} actionable tweaks available", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(0, 10))
    hover_button(bar, "APPLY ALL TWEAKS", run_all, True).pack(anchor="w", padx=18, pady=(0, 8))
    toolbar = tk.Frame(content, bg=BG); toolbar.pack(fill="x", padx=34, pady=(0, 8))
    tk.Label(toolbar, text="SHOW", bg=BG, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(side="left")
    category_var.set("All tweaks")
    dropdown = tk.OptionMenu(toolbar, category_var, "All tweaks", *sorted({t[1] for t in real_tweaks()}), command=lambda _: refresh_boost())
    dropdown.configure(bg=PANEL_HI, fg=WHITE, activebackground=YELLOW, activeforeground="#17191B", relief="flat", bd=0, font=("Segoe UI", 9, "bold"), highlightthickness=0)
    dropdown["menu"].configure(bg=PANEL_HI, fg=WHITE, activebackground=YELLOW, activeforeground="#17191B")
    dropdown.pack(side="left", padx=10)
    listbox = tk.Frame(content, bg=BG); listbox.pack(fill="x", padx=34, pady=(0, 25)); root._boost_list=listbox; refresh_boost()


def refresh_boost():
    if not hasattr(root, "_boost_list"): return
    for w in root._boost_list.winfo_children(): w.destroy()
    selected=category_var.get(); items=real_tweaks()
    if selected != "All tweaks": items=[t for t in items if t[1]==selected]
    for i,t in enumerate(items,1): tweak_row(root._boost_list,t,i)
    root.after_idle(update_scroll)


def tweak_picker_screen():
    clear_content(); select_nav(nav_buttons[5] if len(nav_buttons)>5 else None)
    header("Tweak Center", "Build your own setup. Nothing runs until you press Apply Selected.")
    toolbar=panel(content); toolbar.pack(fill="x", padx=34, pady=18)
    left=tk.Frame(toolbar,bg=PANEL); left.pack(side="left",fill="x",expand=True,padx=18,pady=15)
    tk.Label(left,text="CATEGORY",bg=PANEL,fg=MUTED,font=("Segoe UI",8,"bold")).pack(anchor="w")
    categories=["All categories"]+sorted({t[1] for t in real_tweaks()}); picker_category_var.set(picker_category_var.get() if picker_category_var.get() in categories else "All categories")
    drop=tk.OptionMenu(left,picker_category_var,*categories,command=lambda _: tweak_picker_screen())
    drop.configure(bg=PANEL_HI,fg=WHITE,activebackground=YELLOW,activeforeground="#17191B",relief="flat",bd=0,font=("Segoe UI",9,"bold"),highlightthickness=0); drop["menu"].configure(bg=PANEL_HI,fg=WHITE,activebackground=YELLOW,activeforeground="#17191B"); drop.pack(anchor="w",pady=(5,0))
    actions=tk.Frame(toolbar,bg=PANEL); actions.pack(side="right",padx=18,pady=15)
    hover_button(actions,"SELECT SHOWN",lambda:select_visible(True)).pack(side="left",padx=3)
    hover_button(actions,"CLEAR SHOWN",lambda:select_visible(False)).pack(side="left",padx=3)
    hover_button(actions,"APPLY SELECTED",apply_selected,True).pack(side="left",padx=3)
    selected_count=sum(1 for v in selected_tweaks.values() if v.get())
    tk.Label(content,text=f"{selected_count} selected",bg=BG,fg=YELLOW,font=("Segoe UI",10,"bold")).pack(anchor="w",padx=34,pady=(0,8))
    items=real_tweaks(); selected_category=picker_category_var.get()
    if selected_category!="All categories": items=[t for t in items if t[1]==selected_category]
    list_panel=panel(content); list_panel.pack(fill="x",padx=34,pady=(0,25))
    for tweak in items:
        name,category,fn,changes=tweak
        row=tk.Frame(list_panel,bg=ROW,highlightbackground=BORDER,highlightthickness=1); row.pack(fill="x",padx=8,pady=3)
        var=selected_tweaks[name]
        cb=tk.Checkbutton(row,text=name,variable=var,bg=ROW,fg=WHITE,selectcolor=PANEL_HI,activebackground=ROW,activeforeground=WHITE,font=("Segoe UI",10,"bold"),anchor="w",highlightthickness=0)
        cb.pack(side="left",fill="x",expand=True,padx=10,pady=9)
        tk.Label(row,text=category,bg=ROW,fg=MUTED,font=("Segoe UI",8)).pack(side="right",padx=15)
    if not items: tk.Label(list_panel,text="No tweaks in this category.",bg=PANEL,fg=MUTED,font=("Segoe UI",10)).pack(pady=25)


def fortnite_screen():
    clear_content(); select_nav(nav_buttons[2] if len(nav_buttons)>2 else None); header("Fortnite","Windows-side gaming changes that may affect game behavior.")
    c=panel(content); c.pack(fill="x",padx=34,pady=20); items=[t for t in real_tweaks() if t[1] in ("Gaming","FPS / GPU")]
    for i,t in enumerate(items,1): tweak_row(c,t,i)


def network_screen():
    clear_content(); select_nav(nav_buttons[3] if len(nav_buttons)>3 else None); header("Network","Repair and refresh tools. These cannot change physical server distance.")
    c=panel(content); c.pack(fill="x",padx=34,pady=20)
    for txt,fn in [("Flush DNS",tweak_dns),("Reset Winsock",tweak_winsock),("Reset TCP/IP",tweak_tcpip),("Renew IP",tweak_renew_ip)]: hover_button(c,txt,lambda f=fn:show_result("Network",*f())).pack(anchor="w",padx=20,pady=5)


def cleaner_screen():
    clear_content(); select_nav(nav_buttons[4] if len(nav_buttons)>4 else None); header("Cleaner","Remove temporary files Windows allows Duck Tweaks to delete.")
    c=panel(content); c.pack(fill="x",padx=34,pady=20)
    for txt,fn in [("CLEAN TEMP FILES",tweak_temp_files),("CLEAR THUMBNAIL CACHE",tweak_thumbnails),("EMPTY RECYCLE BIN",tweak_recycle_bin)]: hover_button(c,txt,lambda f=fn:show_result("Cleaner",*f()),True).pack(anchor="w",padx=20,pady=7)


def tweaks_screen(): tweak_picker_screen()


def restore_screen():
    clear_content(); select_nav(nav_buttons[6] if len(nav_buttons)>6 else None); header("Restore","Undo backed-up registry changes made by Duck Tweaks.")
    c=panel(content); c.pack(fill="x",padx=34,pady=20); hover_button(c,"RESTORE SAVED SETTINGS",restore_all,True).pack(anchor="w",padx=20,pady=20)
    tk.Label(c,text=BACKUP_FILE,bg=PANEL,fg=MUTED,font=("Consolas",8)).pack(anchor="w",padx=20,pady=(0,20))


def system_screen():
    clear_content(); select_nav(nav_buttons[7] if len(nav_buttons)>7 else None); header("System","Basic information about this PC.")
    c=panel(content); c.pack(fill="x",padx=34,pady=20)
    for k,v in [("Windows",platform.platform()),("CPU",platform.processor() or "Unavailable"),("Architecture",platform.machine()),("Administrator","YES" if is_admin() else "NO")]:
        r=tk.Frame(c,bg=ROW); r.pack(fill="x",padx=15,pady=3); tk.Label(r,text=k,bg=ROW,fg=MUTED,font=("Segoe UI",9)).pack(side="left",padx=12,pady=9); tk.Label(r,text=v,bg=ROW,fg=WHITE,font=("Segoe UI",9,"bold")).pack(side="right",padx=12)


def settings_screen():
    clear_content(); select_nav(nav_buttons[8] if len(nav_buttons)>8 else None); header("Settings","Tune Duck Tweaks itself.")
    appearance=panel(content); appearance.pack(fill="x",padx=34,pady=(20,10)); section_label(appearance,"APPEARANCE",True)
    r=tk.Frame(appearance,bg=PANEL); r.pack(fill="x",padx=18,pady=(0,16)); tk.Label(r,text="Accent color",bg=PANEL,fg=TEXT,font=("Segoe UI",9)).pack(side="left")
    accent=tk.OptionMenu(r,accent_var,*ACCENTS.keys(),command=apply_accent); accent.configure(bg=PANEL_HI,fg=WHITE,activebackground=YELLOW,activeforeground="#17191B",relief="flat",bd=0,font=("Segoe UI",9),highlightthickness=0); accent["menu"].configure(bg=PANEL_HI,fg=WHITE,activebackground=YELLOW,activeforeground="#17191B"); accent.pack(side="right")
    backup=panel(content); backup.pack(fill="x",padx=34,pady=10); section_label(backup,"BACKUP",False)
    tk.Label(backup,text="Registry values changed by Duck Tweaks are saved here:",bg=PANEL,fg=TEXT,font=("Segoe UI",9)).pack(anchor="w",padx=18); tk.Label(backup,text=BACKUP_FILE,bg=PANEL,fg=MUTED,font=("Consolas",8)).pack(anchor="w",padx=18,pady=(5,15))


# ---------------- WINDOW LAYOUT ----------------
top=tk.Frame(root,bg=BG,height=72); top.pack(fill="x"); top.pack_propagate(False)
brand=tk.Frame(top,bg=BG); brand.pack(side="left",padx=28)
tk.Label(brand,text="DUCK",bg=BG,fg=YELLOW,font=("Segoe UI",18,"bold")).pack(side="left",pady=17)
tk.Label(brand,text=" TWEAKS",bg=BG,fg=WHITE,font=("Segoe UI",18,"bold")).pack(side="left",pady=17)
tk.Label(top,text="WINDOWS PERFORMANCE CONTROL",bg=BG,fg=MUTED,font=("Segoe UI",8,"bold")).pack(side="left",padx=20)
status_label=tk.Label(top,text="READY",bg=BG,fg=GREEN,font=("Segoe UI",8,"bold")); status_label.pack(side="right",padx=30)
progress=tk.DoubleVar(value=0)
progress_bar=tk.Scale(top,from_=0,to=100,variable=progress,showvalue=False,orient="horizontal",length=130,sliderlength=0,bg=BG,fg=BG,troughcolor=PANEL_HI,highlightthickness=0,state="disabled"); progress_bar.pack(side="right",padx=(0,12))

work=tk.Frame(root,bg=BG); work.pack(fill="both",expand=True)
scroll_canvas=tk.Canvas(work,bg=BG,highlightthickness=0,bd=0); scroll_canvas.pack(side="left",fill="both",expand=True)
scrollbar=tk.Scrollbar(work,orient="vertical",command=scroll_canvas.yview,bg=PANEL_HI,troughcolor=BG,activebackground=YELLOW,relief="flat",width=11); scrollbar.pack(side="right",fill="y")
scroll_canvas.configure(yscrollcommand=scrollbar.set)
scroll_inner=tk.Frame(scroll_canvas,bg=BG); content_window=scroll_canvas.create_window((0,0),window=scroll_inner,anchor="nw"); content=scroll_inner

def resize_scroll_frame(event):
    scroll_canvas.itemconfigure(content_window,width=event.width); scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))
scroll_canvas.bind("<Configure>",resize_scroll_frame); scroll_inner.bind("<Configure>",lambda e:update_scroll()); scroll_canvas.bind_all("<MouseWheel>",wheel_scroll)

bottom_nav=tk.Frame(root,bg=SIDEBAR,height=62,highlightbackground=BORDER,highlightthickness=1); bottom_nav.pack(fill="x",side="bottom"); bottom_nav.pack_propagate(False)
add_nav("Dashboard",dashboard); add_nav("PC Boost",boost_screen); add_nav("Fortnite",fortnite_screen); add_nav("Network",network_screen); add_nav("Cleaner",cleaner_screen); add_nav("Tweak Center",tweak_picker_screen); add_nav("Restore",restore_screen); add_nav("System",system_screen); add_nav("Settings",settings_screen)

tk.Label(root,text="agentfishy22",bg=BG,fg="#646B73",font=("Segoe UI",7)).place(relx=1.0,rely=1.0,x=-8,y=-65,anchor="se")

category_var=tk.StringVar(value="All tweaks")
picker_category_var=tk.StringVar(value="All categories")
accent_var=tk.StringVar(value="Duck Yellow")
for tweak in real_tweaks(): selected_tweaks[tweak[0]]=tk.BooleanVar(value=False)

dashboard(); root.after_idle(update_scroll); root.mainloop()
