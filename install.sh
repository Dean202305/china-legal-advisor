#!/usr/bin/env bash
# install.sh —— 把 china-legal-advisor 安装到各类 AI 编码工具
#
# 用法：
#   ./install.sh                     # 自动检测已安装的工具并全部安装
#   ./install.sh --target claude     # 只装到 Claude Code
#   ./install.sh --target codex      # 只装到 OpenAI Codex
#   ./install.sh --target dsh        # 只装到 DSH
#   ./install.sh --target cursor     # 在当前项目写入 Cursor 规则
#   ./install.sh --target project    # 在当前项目写入 .claude/skills 与 .cursor/rules
#   ./install.sh --target all        # 全部目标（含 project）
#   ./install.sh --copy              # 复制而非符号链接（部分工具不支持符号链接时使用）
#   ./install.sh --uninstall         # 卸载
#   ./install.sh --check             # 仅检查运行环境与语料完整性
#
# 可组合多个 --target，例如：./install.sh --target claude --target codex

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAME="china-legal-advisor"
MODE="link"
ACTION="install"
TARGETS=()
SKILL_DIRS=(
  "$HOME/.claude/skills"
  "$HOME/.codex/skills"
  "$HOME/.dsh/skills"
)

c_reset="\033[0m"; c_ok="\033[32m"; c_warn="\033[33m"; c_err="\033[31m"; c_dim="\033[2m"
ok()   { printf "${c_ok}✓${c_reset} %b\n" "$1"; }
warn() { printf "${c_warn}!${c_reset} %b\n" "$1"; }
err()  { printf "${c_err}✗${c_reset} %b\n" "$1"; }
dim()  { printf "${c_dim}  %b${c_reset}\n" "$1"; }

usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGETS+=("${2:-}"); shift 2 ;;
    --target=*) TARGETS+=("${1#*=}"); shift ;;
    --copy) MODE="copy"; shift ;;
    --link) MODE="link"; shift ;;
    --uninstall) ACTION="uninstall"; shift ;;
    --check) ACTION="check"; shift ;;
    -h|--help) usage ;;
    *) err "未知参数：$1"; echo; usage ;;
  esac
done

check_env() {
  echo "== 环境检查 =="
  if command -v python3 >/dev/null 2>&1; then
    local ver; ver="$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
    if python3 -c 'import sys; sys.exit(0 if sys.version_info>=(3,8) else 1)'; then
      ok "python3 ${ver}"
    else
      err "python3 ${ver} 版本过低（需要 3.8+）"; return 1
    fi
  else
    err "未找到 python3（本技能需要 Python 3.8+，无第三方依赖）"; return 1
  fi
  echo
  echo "== 语料完整性自检 =="
  ( cd "$SRC" && python3 scripts/selftest.py | tail -4 )
  echo
  echo "== 检索工具冒烟测试 =="
  ( cd "$SRC" && python3 scripts/law.py stats )
}

install_into() {  # $1 = 目标 skills 目录（个人级）
  local dir="$1" dest="$1/$NAME"
  mkdir -p "$dir"
  if [[ "$MODE" == "link" ]]; then
    rm -rf "$dest"
    ln -s "$SRC" "$dest"
    ok "$dest → $SRC ${c_dim}(符号链接，git pull 即同步)${c_reset}"
  else
    rm -rf "$dest"; mkdir -p "$dest"
    # 只复制运行所需内容，避免把 .git 等一并拷入
    ( cd "$SRC" && tar --exclude='./.git' --exclude='./.github' \
        -cf - SKILL.md references scripts ) | ( cd "$dest" && tar -xf - )
    ok "$dest ${c_dim}(已复制；更新需重新运行本脚本)${c_reset}"
  fi
}

uninstall_from() {  # $1 = 目标 skills 目录
  local dest="$1/$NAME"
  if [[ -L "$dest" || -d "$dest" ]]; then rm -rf "$dest"; ok "已移除 $dest"; else dim "未安装：$dest"; fi
}

install_cursor() {  # 写入当前项目的 Cursor 规则
  local proj="$PWD"
  if [[ ! -d "$proj/.git" && ! -f "$proj/package.json" && ! -f "$proj/AGENTS.md" ]]; then
    warn "$proj 看起来不是项目根目录，仍将写入 .cursor/rules/"
  fi
  mkdir -p "$proj/.cursor/rules"
  cp "$SRC/.cursor/rules/$NAME.mdc" "$proj/.cursor/rules/$NAME.mdc"
  ok "$proj/.cursor/rules/$NAME.mdc"
  dim "Cursor 规则是项目级的；请在各项目根目录分别运行 --target cursor"
}

uninstall_cursor() {
  local f="$PWD/.cursor/rules/$NAME.mdc"
  [[ -f "$f" ]] && { rm -f "$f"; ok "已移除 $f"; } || dim "未安装：$f"
}

install_project() {  # 项目级：.claude/skills + .cursor/rules
  local proj="$PWD"
  mkdir -p "$proj/.claude/skills"
  if [[ "$MODE" == "link" ]]; then rm -rf "$proj/.claude/skills/$NAME"; ln -s "$SRC" "$proj/.claude/skills/$NAME"
  else rm -rf "$proj/.claude/skills/$NAME"; mkdir -p "$proj/.claude/skills/$NAME"
       ( cd "$SRC" && tar --exclude='./.git' -cf - SKILL.md references scripts ) | ( cd "$proj/.claude/skills/$NAME" && tar -xf - ); fi
  ok "$proj/.claude/skills/$NAME"
  install_cursor
}

case "$ACTION" in
  check) check_env; exit $? ;;
  uninstall)
    if [[ ${#TARGETS[@]} -eq 0 ]]; then
      err "请指定要卸载的目标：--target claude|codex|dsh|cursor|project|all"
      exit 1
    fi
    for t in "${TARGETS[@]}"; do
      case "$t" in
        claude) uninstall_from "$HOME/.claude/skills" ;;
        codex)  uninstall_from "$HOME/.codex/skills" ;;
        dsh)    uninstall_from "$HOME/.dsh/skills" ;;
        cursor) uninstall_cursor ;;
        project) uninstall_from "$PWD/.claude/skills"; uninstall_cursor ;;
        all)
          for d in "${SKILL_DIRS[@]}"; do uninstall_from "$d"; done
          uninstall_cursor ;;
        *) warn "忽略未知目标：$t" ;;
      esac
    done
    exit 0 ;;
esac

check_env || exit 1

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  echo "== 自动检测已安装的工具 =="
  detected=0
  for d in "${SKILL_DIRS[@]}"; do
    parent="$(dirname "$d")"
    if [[ -d "$d" || -d "$parent" ]]; then
      case "$d" in
        */.claude/skills) TARGETS+=("claude"); detected=$((detected+1)) ;;
        */.codex/skills)  TARGETS+=("codex");  detected=$((detected+1)) ;;
        */.dsh/skills)    TARGETS+=("dsh");    detected=$((detected+1)) ;;
      esac
    fi
  done
  if [[ $detected -eq 0 ]]; then
    warn "未检测到 ~/.claude、~/.codex 或 ~/.dsh，将只提供仓库内使用说明"
    dim "你也可以手动指定：./install.sh --target claude"
  fi
fi

echo
echo "== 安装（模式：$MODE）=="
if [[ ${#TARGETS[@]} -eq 0 ]]; then
  warn "没有可安装的目标。"
  dim "手动指定：./install.sh --target claude|codex|dsh|cursor|project|all"
  exit 0
fi
for t in "${TARGETS[@]}"; do
  case "$t" in
    claude) install_into "$HOME/.claude/skills" ;;
    codex)  install_into "$HOME/.codex/skills" ;;
    dsh)    install_into "$HOME/.dsh/skills" ;;
    cursor) install_cursor ;;
    project) install_project ;;
    all)
      for d in "${SKILL_DIRS[@]}"; do install_into "$d"; done
      install_cursor ;;
    *) warn "忽略未知目标：$t" ;;
  esac
done

echo
ok "完成。重启你的 AI 工具（或新开会话）即可识别本技能。"
dim "验证：向 AI 提问「劳动合同法第 38 条怎么规定的？」"
dim "卸载：./install.sh --uninstall --target all"
