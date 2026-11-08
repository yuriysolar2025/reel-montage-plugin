#!/usr/bin/env python3
"""Первый шаг любого монтажа: FableCut запущен и открыт в браузере. Без вопросов человеку.

    python3 fablecut_open.py

- Сервер не отвечает на 127.0.0.1:<FABLECUT_PORT, по умолчанию 7777> — запускает `npx -y fablecut@1.18.0` в фоне.
- Mac: открывает вкладку в Google Chrome (нет Chrome — в браузере по умолчанию), если такой вкладки ещё нет.
- Windows/Linux: открывает системный браузер, только когда сервер запустили сейчас (вкладок там не видно,
  так что повторно не открываем, чтобы не плодить вкладки).
FABLECUT_NO_OPEN=1 отключает открытие браузера (например, для съёмки без экрана).
"""
import os, platform, shutil, subprocess, sys, time, urllib.request, webbrowser

PORT = os.environ.get('FABLECUT_PORT', '7777')
URL = f'http://localhost:{PORT}'


def up():
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/project', timeout=1); return True
    except Exception:
        return False


def start_server():
    npx = shutil.which('npx') or shutil.which('npx.cmd')
    if not npx: return False
    env = dict(os.environ, PORT=PORT, FABLECUT_PORT=PORT)
    log = open(os.path.join(os.path.expanduser('~'), '.fablecut-server.log'), 'ab')
    kw = {'creationflags': 0x00000008} if os.name == 'nt' else {'start_new_session': True}   # отвязать от терминала
    subprocess.Popen([npx, '-y', 'fablecut@1.18.0'], stdout=log, stderr=log, stdin=subprocess.DEVNULL, env=env, **kw)
    for _ in range(120):   # первый запуск npx качает пакет — до ~30 с
        if up(): return True
        time.sleep(0.25)
    return False


def mac_chrome_has_tab():
    r = subprocess.run(['osascript', '-e', 'if application "Google Chrome" is running then tell application "Google Chrome" '
                        'to get URL of tabs of windows'], capture_output=True, text=True)
    return f'localhost:{PORT}' in r.stdout or f'127.0.0.1:{PORT}' in r.stdout


def ensure(quiet=False):
    say = (lambda *a: None) if quiet else print
    started = False
    if not up():
        if not start_server():
            say(f'FableCut: не запустился (нужен Node.js 18+, лог ~/.fablecut-server.log). Сборка пойдёт без живого показа.')
            return False
        started = True; say(f'FableCut: сервер запущен, {URL}')
    if os.environ.get('FABLECUT_NO_OPEN') == '1': return True
    if platform.system() == 'Darwin':
        if mac_chrome_has_tab(): say('FableCut: вкладка уже открыта'); return True
        ok = subprocess.run(['open', '-a', 'Google Chrome', URL], capture_output=True).returncode == 0
        if not ok: subprocess.run(['open', URL])
        say(f'FableCut: открыл {URL}')
    elif started:
        webbrowser.open(URL); say(f'FableCut: открыл {URL} в браузере')
    else:
        say(f'FableCut: уже запущен — если вкладки нет, открой {URL}')
    return True


if __name__ == '__main__':
    sys.exit(0 if ensure() else 1)
