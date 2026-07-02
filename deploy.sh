#!/bin/bash
# Деплой на GitHub Pages
set -e
cd "$(dirname "$0")"

echo "📡 Деплой «Деловой Инсайд» на GitHub Pages..."

# Regenerate RSS
python3 generate_rss.py

# Git push
git add -A
git commit -m "📰 Статья $(date +%Y-%m-%d)" || echo "⚠️ Нет изменений"
git push origin main

echo "✅ Сайт: https://shalaxxx-maker.github.io/delovoy-insaid/"
echo "✅ RSS: https://shalaxxx-maker.github.io/delovoy-insaid/rss.xml"
