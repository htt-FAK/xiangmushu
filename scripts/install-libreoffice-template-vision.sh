#!/usr/bin/env bash
# 模板视觉：docx → PDF 依赖本机 LibreOffice（soffice），Linux/服务器推荐方案。
#
# 用法：
#   chmod +x scripts/install-libreoffice-template-vision.sh
#   ./scripts/install-libreoffice-template-vision.sh
#
# 国内网络（推荐）：安装前切换 apt/apk 到国内镜像，再装包
#   USE_CN_MIRROR=1 ./scripts/install-libreoffice-template-vision.sh
#
# 可选环境变量：
#   USE_CN_MIRROR=1       启用 apt / apk 国内镜像改写（会备份原配置）
#   CN_MIRROR_VENDOR=aliyun|tuna   默认 aliyun；tuna=清华开源镜像站
#   SKIP_SUDO=1           已在 root 或无需 sudo 时使用
#   APT_CN_HOST=…         高级：自行指定镜像主机名（覆盖 CN_MIRROR_VENDOR）
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

need_sudo() {
  if [[ "${SKIP_SUDO:-}" == "1" ]]; then
    return 1
  fi
  if [[ "$(id -u)" -eq 0 ]]; then
    return 1
  fi
  return 0
}

run() {
  if need_sudo; then
    sudo "$@"
  else
    "$@"
  fi
}

_mirror_host() {
  if [[ -n "${APT_CN_HOST:-}" ]]; then
    echo "$APT_CN_HOST"
    return
  fi
  case "${CN_MIRROR_VENDOR:-aliyun}" in
    tuna | tsinghua | thu)
      echo "mirrors.tuna.tsinghua.edu.cn"
      ;;
    aliyun | ali | *)
      echo "mirrors.aliyun.com"
      ;;
  esac
}

# 仅在 USE_CN_MIRROR=1 时调用：改写 Ubuntu/Debian 的 apt 源为 https://<host>/...
apply_cn_mirror_apt() {
  if [[ "${USE_CN_MIRROR:-}" != "1" ]]; then
    return 0
  fi
  if ! command -v apt-get >/dev/null 2>&1; then
    return 0
  fi
  local h stamp
  h="$(_mirror_host)"
  stamp="$(date +%Y%m%d%H%M%S)"
  echo "[apt] USE_CN_MIRROR=1：尝试将官方域名替换为 https://${h}/ …（已备份 *.bak_${stamp}）"

  _apt_sed_file() {
    local f="$1"
    [[ -f "$f" ]] || return 0
    if grep -qE "${h}" "$f" 2>/dev/null; then
      echo "[apt] 已含镜像 ${h}，跳过: $f"
      return 0
    fi
    if ! grep -qE '(deb\.debian\.org|security\.debian\.org|archive\.ubuntu\.com|security\.ubuntu\.com|ports\.ubuntu\.com)' "$f" 2>/dev/null; then
      return 0
    fi
    run cp -a "$f" "${f}.bak_${stamp}"
    # Ubuntu one-line sources.list
    run sed -i \
      -e "s|http://archive.ubuntu.com/ubuntu|https://${h}/ubuntu|g" \
      -e "s|https://archive.ubuntu.com/ubuntu|https://${h}/ubuntu|g" \
      -e "s|http://security.ubuntu.com/ubuntu|https://${h}/ubuntu|g" \
      -e "s|https://security.ubuntu.com/ubuntu|https://${h}/ubuntu|g" \
      -e "s|http://ports.ubuntu.com/ubuntu-ports|https://${h}/ubuntu-ports|g" \
      -e "s|https://ports.ubuntu.com/ubuntu-ports|https://${h}/ubuntu-ports|g" \
      "$f"
    # Debian
    run sed -i \
      -e "s|http://deb.debian.org/debian|https://${h}/debian|g" \
      -e "s|https://deb.debian.org/debian|https://${h}/debian|g" \
      -e "s|http://security.debian.org/debian-security|https://${h}/debian-security|g" \
      -e "s|https://security.debian.org/debian-security|https://${h}/debian-security|g" \
      "$f"
  }

  _apt_sed_file /etc/apt/sources.list
  local f
  shopt -s nullglob
  for f in /etc/apt/sources.list.d/*.sources /etc/apt/sources.list.d/*.list; do
    _apt_sed_file "$f"
  done
  shopt -u nullglob
}

apply_cn_mirror_apk() {
  if [[ "${USE_CN_MIRROR:-}" != "1" ]]; then
    return 0
  fi
  if ! command -v apk >/dev/null 2>&1; then
    return 0
  fi
  local h stamp
  h="$(_mirror_host)"
  stamp="$(date +%Y%m%d%H%M%S)"
  [[ -f /etc/apk/repositories ]] || return 0
  if grep -q "${h}/alpine" /etc/apk/repositories 2>/dev/null; then
    echo "[apk] 已含镜像 ${h}，跳过 repositories"
    return 0
  fi
  echo "[apk] USE_CN_MIRROR=1：将 dl-cdn 替换为 https://${h}/alpine/ …"
  run cp -a /etc/apk/repositories "/etc/apk/repositories.bak_${stamp}"
  run sed -i \
    -e "s|https://dl-cdn.alpinelinux.org/alpine|https://${h}/alpine|g" \
    -e "s|http://dl-cdn.alpinelinux.org/alpine|https://${h}/alpine|g" \
    /etc/apk/repositories
}

hint_cn_dnf_yum() {
  if [[ "${USE_CN_MIRROR:-}" != "1" ]]; then
    return 0
  fi
  echo "[dnf/yum] 国内镜像因发行版差异未自动改写仓库文件。"
  echo "           请参考阿里云「镜像站」中 Fedora / Rocky / CentOS 等对应说明配置 baseurl 后，再执行本脚本。"
  echo "           https://developer.aliyun.com/mirror/"
}

if command -v soffice >/dev/null 2>&1; then
  echo "soffice already on PATH: $(command -v soffice)"
else
  if command -v apt-get >/dev/null 2>&1; then
    apply_cn_mirror_apt
    echo "[apt] Installing LibreOffice (writer for docx→pdf)..."
    run apt-get update -qq
    run apt-get install -y --no-install-recommends libreoffice-writer
  elif command -v dnf >/dev/null 2>&1; then
    hint_cn_dnf_yum
    echo "[dnf] Installing LibreOffice..."
    run dnf install -y libreoffice-writer libreoffice-core
  elif command -v yum >/dev/null 2>&1; then
    hint_cn_dnf_yum
    echo "[yum] Installing LibreOffice..."
    run yum install -y libreoffice-writer libreoffice-core
  elif command -v apk >/dev/null 2>&1; then
    apply_cn_mirror_apk
    echo "[apk] Installing LibreOffice (image will be large)..."
    run apk add --no-cache libreoffice
  else
    echo "Unsupported distro: install LibreOffice manually so 'soffice' is on PATH."
    exit 1
  fi
fi

if ! command -v soffice >/dev/null 2>&1; then
  echo "Install finished but 'soffice' not found on PATH. Try: export PATH=\"/usr/lib/libreoffice/program:\$PATH\""
  exit 1
fi

echo "OK: $(command -v soffice)"
soffice --version | head -n 1 || true

if command -v python3 >/dev/null 2>&1; then
  echo "Tip: pip install -r requirements.txt  (includes pymupdf for PDF→PNG)"
  if [[ "${USE_CN_MIRROR:-}" == "1" ]]; then
    echo "Tip(国内): pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt"
  fi
fi
