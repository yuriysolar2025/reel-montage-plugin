#!/bin/bash
# Проверка, что всё нужное для монтажа стоит. Ничего не ставит сам — только говорит, чего нет.
ok=1
chk() { if eval "$2" >/dev/null 2>&1; then echo "✓ $1"; else echo "✗ $1 — $3"; ok=0; fi; }
chk "ffmpeg"  "command -v ffmpeg && command -v ffprobe" "Mac: brew install ffmpeg · Windows: winget install ffmpeg · Linux: apt install ffmpeg"
chk "Python 3" "command -v python3" "Mac: brew install python"
chk "Pillow (картинки субтитров)" "python3 -c 'import PIL' || command -v uv" "pip3 install pillow  (или поставь uv: brew install uv)"
chk "Node.js 18+ (для FableCut)" "node -e 'process.exit(parseInt(process.versions.node)<18?1:0)'" "Mac: brew install node · nodejs.org"
W=${WHISPER_CLI:-$(command -v whisper-cli || command -v whisper-cpp || echo "$HOME/whisper.cpp/build/bin/whisper-cli")}
chk "whisper.cpp (расшифровка речи)" "[ -x \"$W\" ]" "Mac: brew install whisper-cpp · иначе github.com/ggml-org/whisper.cpp"
if [ -n "${ELEVENLABS_API_KEY:-}" ] && [ -n "${ELEVENLABS_VOICE_ID:-}" ]; then echo "✓ ElevenLabs (озвучка клоном голоса)"; else echo "· ElevenLabs не настроен — не страшно: озвучку можно записать своим голосом"; fi
port=${FABLECUT_PORT:-7777}
if curl -s -m 2 "http://127.0.0.1:$port/api/project" >/dev/null; then echo "✓ FableCut открыт: http://localhost:$port"; else echo "· FableCut пока не запущен — поднимется сам при первом обращении к его MCP, или: npx -y fablecut@1.18.0"; fi
[ $ok = 1 ] && echo "Всё готово к монтажу." || { echo "Поставь то, что с ✗, и запусти проверку ещё раз."; exit 1; }
