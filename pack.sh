#!/usr/bin/env bash
# 打包 article-study skill 为可分发 zip。
# 包内容取自 git 已提交文件（git archive），天然排除 .DS_Store、.git、产物目录。
set -euo pipefail
cd "$(dirname "$0")"

# 终端非 UTF-8 时改用英文提示，避免中文乱码
if locale charmap 2>/dev/null | grep -qiE 'utf-?8'; then
  MSG_DIRTY='工作区有未提交的改动，请先 commit 再打包（zip 内容取自最新提交）'
  MSG_DONE='已打包: '
else
  MSG_DIRTY='Uncommitted changes detected; commit first (zip is built from HEAD).'
  MSG_DONE='Packaged: '
fi

if ! git diff --quiet HEAD --; then
  echo "$MSG_DIRTY" >&2
  git status --short
  exit 1
fi

mkdir -p dist
OUT="dist/article-study-$(date +%Y%m%d).zip"
rm -f "$OUT"
git archive --format=zip --prefix=article-study/ -o "$OUT" HEAD

echo "$MSG_DONE$OUT"
unzip -l "$OUT"
