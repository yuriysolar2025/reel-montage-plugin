#!/usr/bin/env python3
"""Озвучка текста своим голосом в ElevenLabs (необязательно: можно просто записать голос самому).

    export ELEVENLABS_API_KEY=…     # ключ из elevenlabs.io → Profile → API keys; в файлы проекта не класть
    export ELEVENLABS_VOICE_ID=…    # id своего клонированного голоса (Voices → ⋯ → Copy voice ID)
    python3 tts_elevenlabs.py text.txt voice.mp3

Ударения в русском тексте ставь знаком U+0301 после ударной гласной (пото́м) — модель Multilingual v2
их чаще всего слушается. Слова, которые она упорно ломает, заменяй синонимом.
"""
import json, os, sys, urllib.request, urllib.error

key, voice = os.environ.get('ELEVENLABS_API_KEY'), os.environ.get('ELEVENLABS_VOICE_ID')
if not key or not voice: sys.exit('Нужны переменные ELEVENLABS_API_KEY и ELEVENLABS_VOICE_ID (см. начало файла).')
text = open(sys.argv[1], encoding='utf-8').read().strip()
body = {'text': text, 'model_id': os.environ.get('ELEVENLABS_MODEL', 'eleven_multilingual_v2'),
        'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75, 'style': 0.0, 'speed': 1.0}}
req = urllib.request.Request(f'https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128',
                             data=json.dumps(body).encode(), method='POST',
                             headers={'xi-api-key': key, 'Content-Type': 'application/json', 'Accept': 'audio/mpeg'})
try:
    open(sys.argv[2], 'wb').write(urllib.request.urlopen(req, timeout=300).read())
except urllib.error.HTTPError as e:
    sys.exit(f'ElevenLabs ответил {e.code}: {e.read()[:200].decode("utf-8", "replace")}')
print('готово:', sys.argv[2])
