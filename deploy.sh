#!/bin/bash
# Деплой микросайта «Деловой Инсайд» на Netlify
# Запуск: bash deploy.sh
# Требуется: Netlify CLI (npm install -g netlify-cli) и авторизация

set -e
cd "$(dirname "$0")"

echo "📡 Деплой «Деловой Инсайд»..."

# Regenerate RSS (на всякий случай)
python3 generate_rss.py

# Option 1: Netlify CLI (если установлен)
if command -v netlify &>/dev/null; then
    echo "🚀 Деплой через Netlify CLI..."
    netlify deploy --prod --dir=. --message="Статья $(date +%Y-%m-%d)"
    echo "✅ Готово: $SITE_URL"
    exit 0
fi

# Option 2: Git push → GitHub → Netlify auto-deploy
if git remote get-url origin &>/dev/null; then
    echo "📤 Push в GitHub..."
    git add articles/ rss.xml manifest.json
    git commit -m "📰 Статья $(date +%Y-%m-%d)" || echo "⚠️ Нет изменений"
    git push origin main
    echo "✅ GitHub обновлён → Netlify подхватит автоматически"
    exit 0
fi

echo "❌ Не настроен деплой. Выполни:"
echo "   1. netlify login"
echo "   2. netlify init --dir=."
echo "   ИЛИ"
echo "   3. git init && git remote add origin git@github.com:USER/delovoy-insaid.git"
