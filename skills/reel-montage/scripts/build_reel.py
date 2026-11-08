#!/usr/bin/env python3
"""Сборка вертикального ролика 1080×1920 из описания reel.json.

    uv run --with pillow python3 build_reel.py reel.json
    (или: pip3 install pillow && python3 build_reel.py reel.json)

Пути в reel.json считаются от папки, где лежит reel.json.
Если открыт редактор FableCut (http://localhost:7777, порт меняется FABLECUT_PORT),
сборка показывает в нём, как ролик собирается: отрезки, плашка, субтитры, звук.
Финальный файл всегда рендерит ffmpeg; FableCut только витрина.

Формат reel.json — в templates/reel.example.json и в SKILL.md.
"""
import json, os, re, subprocess, sys, hashlib, urllib.request, urllib.error

W, H, FPS = 1080, 1920, 30
FONTS = ['/System/Library/Fonts/Supplemental/Arial Bold.ttf', '/Library/Fonts/Arial Bold.ttf',
         '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',
         'C:/Windows/Fonts/arialbd.ttf']


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f'ffmpeg упал:\n{" ".join(cmd)[:400]}\n{r.stderr[-1500:]}')


def probe_dur(p):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p],
                       capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except ValueError: return 0.0


# ---------- FableCut: живой показ (любой сбой здесь сборку не ломает) ----------
class Live:
    def __init__(self, cfg, key):
        port = os.environ.get('FABLECUT_PORT', '7777')
        self.base = os.environ.get('FABLECUT_URL', f'http://127.0.0.1:{port}')
        self.key = key; self.S = None
        if cfg.get('fablecut', True):   # сервер поднят и вкладка открыта — без вопросов
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            try: import fablecut_open; fablecut_open.ensure()
            except Exception as e: print('FableCut: не открыл:', e)
        self.on = cfg.get('fablecut', True) and self._ping()
        print('FableCut:', f'показываю сборку в {self.base}' if self.on else 'не запущен — живого показа не будет')

    def _req(self, method, path, data=None, ctype='application/json', timeout=60):
        req = urllib.request.Request(self.base + path, data=data, method=method, headers={'Content-Type': ctype})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b'null')

    def _ping(self):
        try: self._req('GET', '/api/project', timeout=3); return True
        except Exception: return False

    def _upload(self, path, name):
        """Файл в медиатеку FableCut. Имя с хэшем содержимого: тот же файл второй раз не грузится."""
        h = hashlib.sha1(f'{os.path.getsize(path)}:{os.path.getmtime(path)}'.encode()).hexdigest()[:8]
        base, ext = os.path.splitext(name); name = f'{self.key}_{base}_{h}{ext}'
        have = {m['name']: m['src'] for m in self._req('GET', '/api/media')}
        if name in have: return have[name]
        return self._req('POST', '/api/upload?name=' + urllib.request.quote(name), open(path, 'rb').read(),
                         'application/octet-stream', timeout=300)['src']

    def _write(self):
        try:
            cur = self._req('GET', '/api/project', timeout=10).get('revision', 0)
            self.S['revision'] = cur + 1
            self._req('PUT', '/api/project', json.dumps(self.S, ensure_ascii=False).encode())
        except Exception as e:
            print('FableCut: не записал шаг:', e)

    def _media(self, path, kind):
        src = self._upload(path, os.path.basename(path))
        mid = 'm_' + hashlib.sha1(src.encode()).hexdigest()[:10]
        if not any(m['id'] == mid for m in self.S['media']):
            m = {'id': mid, 'name': os.path.basename(path), 'kind': kind, 'src': src}
            d = probe_dur(path)
            if d and kind != 'image': m['duration'] = round(d, 3)
            self.S['media'].append(m)
        return mid

    def guard(fn):
        def wrap(self, *a, **k):
            if not self.on: return
            try: fn(self, *a, **k)
            except Exception as e: print('FableCut: шаг пропущен:', e)
        return wrap

    @guard
    def start(self, title):
        self.S = {'name': f'{title or self.key} — монтаж', 'width': W, 'height': H, 'fps': FPS,
                  'background': '#000000', 'tracks': [{'id': t, 'kind': 'video'} for t in ('V4', 'V3', 'V2', 'V1')]
                  + [{'id': 'A1', 'kind': 'audio'}, {'id': 'A2', 'kind': 'audio'}],
                  'markers': [], 'media': [], 'clips': []}
        self._write()

    @guard
    def seg(self, i, path, a, b):
        mid = self._media(path, 'video')
        self.S['clips'].append({'id': f'c_v{i}', 'mediaId': mid, 'kind': 'video', 'track': 'V1', 'start': round(a, 3),
                                'in': 0, 'duration': round(b - a, 3), 'name': f'отрезок {i + 1}',
                                'props': {'fit': 'cover', 'volume': 0}})
        self._write()

    @guard
    def overlays(self, title, subs, stickers):
        if title:
            self.S['clips'].append({'id': 'c_title', 'mediaId': None, 'kind': 'text', 'track': 'V4', 'start': 0, 'in': 0,
                                    'duration': 2.6, 'name': 'плашка',
                                    'props': {'text': title, 'fontSize': 60, 'font': 'Arial', 'weight': 700,
                                              'color': '#ffffff', 'bgColor': '#ff8c42', 'bgOpacity': 0.92, 'y': -730}})
            self._write()
        for j, s in enumerate(stickers):
            mid = self._media(s['_abs'], 'image')
            self.S['clips'].append({'id': f'c_st{j}', 'mediaId': mid, 'kind': 'image', 'track': 'V3', 'start': s['start'],
                                    'in': 0, 'duration': round(s['end'] - s['start'], 3), 'name': 'стикер',
                                    'props': {'fit': 'contain'}})
            self._write()
        for i, s in enumerate(subs):
            self.S['clips'].append({'id': f'c_sub{i}', 'mediaId': None, 'kind': 'text', 'track': 'V2', 'start': s['start'],
                                    'in': 0, 'duration': round(s['end'] - s['start'], 3), 'name': s['text'][:24],
                                    'props': {'text': s['text'], 'fontSize': 46, 'font': 'Arial', 'weight': 700,
                                              'color': '#ffffff', 'bgColor': '#0a101c', 'bgOpacity': 0.67, 'y': 680}})
            self._write()

    @guard
    def audio(self, voice, music, total, music_db):
        if voice:
            self.S['clips'].append({'id': 'c_voice', 'mediaId': self._media(voice, 'audio'), 'kind': 'audio', 'track': 'A1',
                                    'start': 0, 'in': 0, 'duration': total, 'name': 'озвучка', 'props': {'volume': 1}})
            self._write()
        if music:
            self.S['clips'].append({'id': 'c_music', 'mediaId': self._media(music, 'audio'), 'kind': 'audio', 'track': 'A2',
                                    'start': 0, 'in': 0, 'duration': total, 'name': 'музыка',
                                    'props': {'gain': music_db, 'volume': 1}})
            self._write()


# ---------- сборка ----------
def load(cfg_path):
    root = os.path.dirname(os.path.abspath(cfg_path))
    cfg = json.load(open(cfg_path, encoding='utf-8'))
    ab = lambda p: p if os.path.isabs(p) else os.path.join(root, p)
    for c in cfg['clips']: c['_abs'] = ab(c['src'])
    for s in cfg.get('stickers', []): s['_abs'] = ab(s['src'])
    for k in ('voice', 'music'):
        if cfg.get(k): cfg['_' + k] = ab(cfg[k])
    cfg['_out'] = ab(cfg.get('out', 'out/reel.mp4'))
    cfg['_work'] = ab(cfg.get('work', 'work/build'))
    # проверки до рендера
    errs = []
    prev = 0.0
    for i, c in enumerate(cfg['clips']):
        if not os.path.exists(c['_abs']): errs.append(f'отрезок {i + 1}: нет файла {c["src"]}')
        if abs(c['start'] - prev) > 0.02: errs.append(f'отрезок {i + 1}: начинается в {c["start"]}, а предыдущий кончился в {prev} (дыра или нахлёст)')
        if c['end'] <= c['start']: errs.append(f'отрезок {i + 1}: конец раньше начала')
        prev = c['end']
    for k in ('_voice', '_music'):
        if cfg.get(k) and not os.path.exists(cfg[k]): errs.append(f'нет файла {cfg[k]}')
    for s in cfg.get('stickers', []):
        if not os.path.exists(s['_abs']): errs.append(f'нет стикера {s["src"]}')
    if errs: sys.exit('reel.json с ошибками:\n  ' + '\n  '.join(errs))
    cfg['_total'] = round(prev, 3)
    return cfg


def render_clip(c, out):
    T = c['end'] - c['start']; ss = str(c.get('ss', 0)); kind = c.get('kind', 'video')
    enc = ['-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '19', '-r', str(FPS), '-pix_fmt', 'yuv420p', out]
    x = float(c.get('x', 0.5))   # окно 9:16 в альбомном кадре: 0 — левый край, 1 — правый
    crop = f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}:(iw-{W})*{x}:(ih-{H})/2,setsar=1,fps={FPS}'
    if kind == 'photo':   # фото или стоп-кадр с лёгким наездом
        fr = int(T * FPS) + 2
        vf = (f"scale={W * 1.2:.0f}:{H * 1.2:.0f}:force_original_aspect_ratio=increase,crop={W * 1.2:.0f}:{H * 1.2:.0f},"
              f"zoompan=z='1+0.0008*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={fr}:s={W}x{H}:fps={FPS}")
        run(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-i', c['_abs'], '-vf', vf, '-t', str(T)] + enc)
    else:
        sp = float(c.get('speed', 1))
        vf = (f'setpts=PTS/{sp},' if sp != 1 else '') + crop
        run(['ffmpeg', '-v', 'error', '-y', '-ss', ss, '-t', str(T * sp), '-i', c['_abs'], '-vf', vf, '-t', str(T)] + enc)


def overlay_pngs(cfg, work):
    from PIL import Image, ImageDraw, ImageFont
    font = cfg.get('font') or next((f for f in FONTS if os.path.exists(f)), None)
    if not font: sys.exit('Не нашёл жирный шрифт с кириллицей. Укажи путь к .ttf в reel.json: "font": "…"')
    Sx = 2; F = ImageFont.truetype(font, 46 * Sx); out = []
    for i, s in enumerate(cfg.get('subs', [])):
        lines = s['text'].split('\n')
        im = Image.new('RGBA', (W * Sx, H * Sx), (0, 0, 0, 0)); d = ImageDraw.Draw(im); lh = 64 * Sx
        y0 = 1640 * Sx - (len(lines) - 1) * lh // 2
        for j, ln in enumerate(lines):
            w = d.textlength(ln, font=F); x = (W * Sx - w) / 2; y = y0 + j * lh
            d.rounded_rectangle([x - 26 * Sx, y - 8 * Sx, x + w + 26 * Sx, y + lh - 4 * Sx], 28 * Sx, fill=(10, 16, 28, 170))
            d.text((x, y), ln, font=F, fill='white')
        p = os.path.join(work, f'sub{i:02d}.png'); im.resize((W, H), Image.LANCZOS).save(p); out.append((p, s['start'], s['end']))
    if cfg.get('title'):
        Fp = ImageFont.truetype(font, 60 * Sx); im = Image.new('RGBA', (W * Sx, H * Sx), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        t = cfg['title']; w = d.textlength(t, font=Fp); x = (W * Sx - w) / 2; y = 170 * Sx
        d.rounded_rectangle([x - 50 * Sx, y - 24 * Sx, x + w + 50 * Sx, y + 96 * Sx], 60 * Sx, fill=(255, 140, 66, 235))
        d.text((x, y), t, font=Fp, fill='white')
        p = os.path.join(work, 'title.png'); im.resize((W, H), Image.LANCZOS).save(p)
        out.insert(0, (p, 0, float(cfg.get('title_until', 2.6))))
    for j, s in enumerate(cfg.get('stickers', [])):   # стикер: картинка шириной width по центру (или x/y)
        im = Image.open(s['_abs']).convert('RGBA'); sw = int(s.get('width', 600)); im = im.resize((sw, int(im.height * sw / im.width)), Image.LANCZOS)
        can = Image.new('RGBA', (W, H), (0, 0, 0, 0)); cx = int(s.get('x', W / 2)); cy = int(s.get('y', H * 0.42))
        can.paste(im, (cx - im.width // 2, cy - im.height // 2), im)
        p = os.path.join(work, f'sticker{j:02d}.png'); can.save(p); out.append((p, s['start'], s['end']))
    return out


def loudnorm(path):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-i', path, '-af', 'loudnorm=I=-16:TP=-1.5:print_format=json', '-f', 'null', '-'],
                       capture_output=True, text=True).stderr
    m = json.loads(re.search(r'\{[^{}]*"input_i"[^{}]*\}', r, re.S).group(0))
    return (f"loudnorm=I=-16:TP=-1.5:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
            f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")


def build(cfg_path):
    cfg = load(cfg_path); TT = cfg['_total']; work = cfg['_work']
    os.makedirs(work, exist_ok=True); os.makedirs(os.path.dirname(cfg['_out']), exist_ok=True)
    key = re.sub(r'\W+', '_', os.path.splitext(os.path.basename(cfg_path))[0])
    live = Live(cfg, key); live.start(cfg.get('title'))
    segs = []
    for i, c in enumerate(cfg['clips']):
        out = os.path.join(work, f'seg{i:02d}.mp4'); render_clip(c, out); segs.append(out)
        print(f'  отрезок {i + 1}/{len(cfg["clips"])} готов'); live.seg(i, out, c['start'], c['end'])
    lst = os.path.join(work, 'list.txt'); open(lst, 'w').write(''.join(f"file '{os.path.abspath(s)}'\n" for s in segs))
    vid = os.path.join(work, 'video.mp4')
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', vid])

    pngs = overlay_pngs(cfg, work)
    live.overlays(cfg.get('title'), cfg.get('subs', []), cfg.get('stickers', []))
    args = ['ffmpeg', '-v', 'error', '-y', '-i', vid]
    for p, *_ in pngs: args += ['-loop', '1', '-t', str(TT), '-i', p]
    fc = ''; prev = '0:v'
    for k, (p, a, b) in enumerate(pngs):
        src = f'{k + 1}:v'
        if 'sticker' in os.path.basename(p):   # стикер всплывает и гаснет
            fc += f'[{src}]format=rgba,fade=t=in:st={a}:d=0.15:alpha=1,fade=t=out:st={b - 0.2}:d=0.2:alpha=1[s{k}];'; src = f's{k}'
        fc += f"[{prev}][{src}]overlay=0:0:enable='between(t,{a},{b})'[o{k}];"; prev = f'o{k}'
    fc += f'[{prev}]fade=t=out:st={max(0, TT - 0.6)}:d=0.6,format=yuv420p[v]'
    vtmp = os.path.join(work, 'v_only.mp4')
    run(args + ['-filter_complex', fc, '-map', '[v]', '-an', '-r', str(FPS), '-t', str(TT), '-c:v', 'libx264',
                '-preset', 'medium', '-crf', '20', vtmp])

    voice, music = cfg.get('_voice'), cfg.get('_music'); mdb = float(cfg.get('music_db', -22))
    live.audio(voice, music, TT, mdb)
    atmp = os.path.join(work, 'a_only.m4a')
    if voice and music:
        fa = (f"[0:a]apad,{loudnorm(voice)}[vo];[1:a]atrim=0:{TT},volume={mdb}dB,afade=t=in:d=1,"
              f"afade=t=out:st={max(0, TT - 2.5)}:d=2.5[mu];[vo][mu]amix=inputs=2:duration=first:normalize=0,atrim=0:{TT},aresample=48000[a]")
        ain = ['-i', voice, '-stream_loop', '-1', '-i', music]
    elif voice:
        fa = f'[0:a]apad,{loudnorm(voice)},atrim=0:{TT},aresample=48000[a]'; ain = ['-i', voice]
    elif music:
        fa = f'[0:a]atrim=0:{TT},volume=-14dB,afade=t=in:d=1,afade=t=out:st={max(0, TT - 2.5)}:d=2.5,aresample=48000[a]'; ain = ['-stream_loop', '-1', '-i', music]
    else:   # тишина: без звуковой дорожки соцсети иногда не принимают ролик
        fa = f'anullsrc=r=48000:cl=stereo,atrim=0:{TT}[a]'; ain = []
    run(['ffmpeg', '-v', 'error', '-y'] + ain + ['-filter_complex', fa, '-map', '[a]', '-t', str(TT), '-c:a', 'aac', '-b:a', '192k', atmp])
    run(['ffmpeg', '-v', 'error', '-y', '-i', vtmp, '-i', atmp, '-c', 'copy', '-movflags', '+faststart', cfg['_out']])
    print(f'готово: {cfg["_out"]} ({TT} с)')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    build(sys.argv[1])
