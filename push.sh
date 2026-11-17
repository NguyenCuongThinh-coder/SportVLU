#!/usr/bin/env bash
set -e

# SportVLU auto-commit & push script
MESSAGE="${1:-Update SportVLU}"

echo "🔍 1. Kiểm tra unit tests trước khi đẩy..."
if [ -d ".venv" ]; then
    .venv/bin/python -m unittest discover -s tests -v
else
    python3 -m unittest discover -s tests -v
fi

echo "📦 2. Thêm các file thay đổi vào Git..."
git add .

echo "📝 3. Tạo commit: '$MESSAGE'..."
git commit -m "$MESSAGE" || { echo "ℹ️ Không có thay đổi nào mới để commit."; exit 0; }

echo "🚀 4. Đẩy code lên GitHub (origin main)..."
git push origin main

echo "✅ Hoàn tất! GitHub đã cập nhật và Render sẽ tự động build lại website."
