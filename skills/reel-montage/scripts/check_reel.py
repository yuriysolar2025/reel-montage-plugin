#!/usr/bin/env python3
"""Проверка готового ролика перед тем, как отдать его человеку.

    python3 check_reel.py out/reel.mp4

Проверяет: 1080×1920, длину, дыры в звуке, зависшие куски, чёрные вставки.
Делает лист кадров <ролик>.sheet.jpg (кадр каждую секунду) — его нужно посмотреть глазами:
совпадает ли картинка с фразой, главное в кадре, нет ли посторонних.
"""
import json, re, subprocess, sys

p = sys.argv[1]; bad = []
info = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,width,height:format=duration',
                                  '-of', 'json', p], capture_output=True, text=True).stdout)
dur = float(info['format']['duration']); v = [s for s in info['streams'] if s['codec_type'] == 'video']
a = [s for s in info['streams'] if s['codec_type'] == 'audio']
print(f'длина {dur:.1f} с')
if not v or (v[0]['width'], v[0]['height']) != (1080, 1920): bad.append(f'кадр не 1080×1920: {v and (v[0]["width"], v[0]["height"])}')
if not a: bad.append('нет звуковой дорожки')
else:
    pk = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'packet=pts_time,duration_time',
                         '-of', 'csv=p=0', p], capture_output=True, text=True).stdout.split()
    end = None
    for row in pk:
        try: t, d = map(float, row.split(',')[:2])
        except ValueError: continue
        if end is not None and t - end > 0.05: bad.append(f'дыра в звуке {t - end:.2f} с на {end:.2f} с')
        end = t + d
fz = subprocess.run(['ffmpeg', '-hide_banner', '-i', p, '-vf', 'freezedetect=n=0.003:d=0.4', '-an', '-f', 'null', '-'],
                    capture_output=True, text=True).stderr
for s, d in zip(re.findall(r'freeze_start: ([\d.]+)', fz), re.findall(r'freeze_duration: ([\d.]+)', fz)):
    bad.append(f'картинка стоит {float(d):.1f} с с {float(s):.1f} с (если это не стоп-кадр — проверь отрезок)')
bk = subprocess.run(['ffmpeg', '-hide_banner', '-i', p, '-vf', 'blackdetect=d=0.2:pix_th=0.08', '-an', '-f', 'null', '-'],
                    capture_output=True, text=True).stderr
for s in re.findall(r'black_start:([\d.]+)', bk):
    if float(s) < dur - 1.0: bad.append(f'чёрная вставка с {float(s):.1f} с')
sheet = re.sub(r'\.\w+$', '', p) + '.sheet.jpg'
cols = 8; rows = max(1, int(dur) // cols + 1)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', p, '-vf', f'fps=1,scale=180:-2,tile={cols}x{rows}', '-frames:v', '1', sheet])
print('лист кадров:', sheet)
print('\n'.join(['ПРОБЛЕМЫ:'] + ['  - ' + b for b in bad]) if bad else 'технически чисто (смысл кадров проверь по листу)')
sys.exit(1 if bad else 0)
