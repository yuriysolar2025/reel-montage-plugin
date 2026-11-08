#!/usr/bin/env python3
"""Вставить паузы в озвучку (под перебивки, где звучит только музыка).

    python3 voice_pauses.py voice.mp3 voice_p.mp3 12.4:2.0 30.1:1.5
                                                 ^ где (с)  ^ сколько тишины (с)

Резать нужно в тишине между фразами: найди её так —
    ffmpeg -i voice.mp3 -af silencedetect=n=-40dB:d=0.15 -f null - 2>&1 | grep silence_
После вставки все тайминги clips/subs ПОСЛЕ точки сдвигаются на длину паузы — поправь reel.json.
Скрипт печатает, на сколько сдвинуть каждый участок.
"""
import subprocess, sys

src, dst = sys.argv[1], sys.argv[2]
cuts = sorted((float(a), float(b)) for a, b in (x.split(':') for x in sys.argv[3:]))
if not cuts: sys.exit(__doc__)
fc, labels, prev = [], [], 0.0
for i, (t, gap) in enumerate(cuts):
    fc.append(f'[0:a]atrim={prev}:{t},asetpts=PTS-STARTPTS[p{i}]')
    fc.append(f'anullsrc=r=44100:cl=mono,atrim=0:{gap}[z{i}]')
    labels += [f'[p{i}]', f'[z{i}]']; prev = t
fc.append(f'[0:a]atrim={prev},asetpts=PTS-STARTPTS[pe]'); labels.append('[pe]')
fc.append(f'{"".join(f"{l}aformat=sample_rates=44100:channel_layouts=mono[f{k}];" for k, l in enumerate(labels))}'.rstrip(';'))
fc.append(''.join(f'[f{k}]' for k in range(len(labels))) + f'concat=n={len(labels)}:v=0:a=1[out]')
r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-filter_complex', ';'.join(fc), '-map', '[out]', dst],
                   capture_output=True, text=True)
if r.returncode: sys.exit(r.stderr[-1500:])
shift = 0.0
for t, gap in cuts:
    shift += gap; print(f'всё, что было после {t:.2f} с, теперь на +{shift:.2f} с позже')
print('готово:', dst)
