#!/bin/bash
# Расшифровка речи whisper.cpp: текст + пословные тайминги (для субтитров).
#   bash transcribe.sh <аудио или видео> [язык=ru]
# Рядом с файлом появятся <имя>.txt (весь текст) и <имя>.words.srt (по одному слову, с таймингами).
# whisper-cli: brew install whisper-cpp (Mac) или сборка github.com/ggml-org/whisper.cpp; путь можно задать WHISPER_CLI.
# Модель ggml-small (~470 МБ) скачивается один раз в ~/.cache/reel-montage/ (или укажи WHISPER_MODEL).
set -euo pipefail
IN=$1; LANG_=${2:-ru}
CLI=${WHISPER_CLI:-$(command -v whisper-cli || command -v whisper-cpp || true)}
[ -z "$CLI" ] && [ -x "$HOME/whisper.cpp/build/bin/whisper-cli" ] && CLI="$HOME/whisper.cpp/build/bin/whisper-cli"
[ -z "$CLI" ] && { echo "Нет whisper-cli. Mac: brew install whisper-cpp"; exit 1; }
MODEL=${WHISPER_MODEL:-$HOME/.cache/reel-montage/ggml-small.bin}
if [ ! -f "$MODEL" ]; then
  mkdir -p "$(dirname "$MODEL")"
  echo "Качаю модель whisper small в $MODEL (один раз)…"
  curl -L --fail -sS -o "$MODEL.part" https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin
  mv "$MODEL.part" "$MODEL"
fi
BASE="${IN%.*}"; TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
ffmpeg -v error -y -i "$IN" -vn -ac 1 -ar 16000 "$TMP/a.wav"
"$CLI" -m "$MODEL" -l "$LANG_" -f "$TMP/a.wav" -otxt -of "$TMP/full" >/dev/null 2>&1
"$CLI" -m "$MODEL" -l "$LANG_" -f "$TMP/a.wav" -osrt -ml 1 -sow -of "$TMP/words" >/dev/null 2>&1
cp "$TMP/full.txt" "$BASE.txt"; cp "$TMP/words.srt" "$BASE.words.srt"
echo "текст: $BASE.txt"; echo "слова: $BASE.words.srt"
cat "$BASE.txt"
