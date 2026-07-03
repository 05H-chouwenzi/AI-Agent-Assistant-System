#!/bin/bash
# ============================================================
# AI Agent Assistant System — 一键部署脚本
# 适用: Ubuntu 22.04 / Docker 26 / Tencent Cloud Light Server
# 用法: bash deploy.sh
# ============================================================

set -e

# ---------- 颜色 ----------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }
title() { echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
          echo -e "${BLUE}  $1${NC}"
          echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }

# ---------- 前置工具安装 ----------
info "检查基础工具..."
NEED_INSTALL=""
for cmd in curl tr; do
  command -v "$cmd" &>/dev/null || NEED_INSTALL="$NEED_INSTALL $cmd"
done
if [ -n "$NEED_INSTALL" ]; then
  apt-get update -qq && apt-get install -y -qq $NEED_INSTALL
  ok "已安装:$NEED_INSTALL"
fi

# ============================================================
# 1. 环境检查
# ============================================================
title "1/6  环境检查"

# Docker
if ! command -v docker &>/dev/null; then
  err "Docker 未安装！正在自动安装..."
  curl -fsSL https://get.docker.com | bash
  ok "Docker 安装完成"
  # 重新检测
  command -v docker &>/dev/null || { err "Docker 安装失败，请手动安装"; exit 1; }
fi
DOCKER_VER=$(docker --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
info "Docker 版本: $DOCKER_VER"

# Docker Compose
if docker compose version &>/dev/null; then
  COMPOSE_CMD="docker compose"
  COMPOSE_VER=$(docker compose version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
  info "Docker Compose 版本: $COMPOSE_VER"
elif docker-compose --version &>/dev/null; then
  COMPOSE_CMD="docker-compose"
  COMPOSE_VER=$(docker-compose --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
  info "Docker Compose (独立) 版本: $COMPOSE_VER"
else
  err "Docker Compose 未安装！正在安装..."
  DOCKER_CONFIG=${DOCKER_CONFIG:-/usr/local/lib/docker}
  mkdir -p "$DOCKER_CONFIG/cli-plugins"
  curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
    -o "$DOCKER_CONFIG/cli-plugins/docker-compose"
  chmod +x "$DOCKER_CONFIG/cli-plugins/docker-compose"
  COMPOSE_CMD="docker compose"
  ok "Docker Compose 安装完成"
fi

# Git
if ! command -v git &>/dev/null; then
  info "Git 未安装，正在安装..."
  apt-get install -y -qq git
  ok "Git 安装完成"
fi

# 端口 80 检查
if ss -tlnp 2>/dev/null | grep -q ':80 '; then
  warn "端口 80 已被占用！"
  ss -tlnp | grep ':80 '
  echo ""
  read -p "是否强制停止占用 80 端口的进程？(y/N): " KILL_PORT
  if [[ "$KILL_PORT" =~ ^[Yy]$ ]]; then
    PID=$(ss -tlnp | grep ':80 ' | grep -oE 'pid=[0-9]+' | grep -oE '[0-9]+' | head -1)
    if [ -n "$PID" ]; then
      kill -9 "$PID" 2>/dev/null && ok "已终止进程 PID=$PID" || warn "终止失败"
    fi
    systemctl stop nginx 2>/dev/null || true
  fi
fi

ok "环境检查通过"

# ============================================================
# 2. 项目代码
# ============================================================
title "2/6  获取项目代码"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

if [ -d "$PROJECT_DIR/.git" ]; then
  info "已在项目目录: $PROJECT_DIR"
  cd "$PROJECT_DIR"
else
  echo ""
  echo -e "${YELLOW}项目目录未检测到 .git，需要从 GitHub 克隆。${NC}"
  read -p "GitHub 仓库 URL: " REPO_URL
  [ -z "$REPO_URL" ] && { err "仓库 URL 不能为空"; exit 1; }
  read -p "分支名（默认 main）: " REPO_BRANCH
  REPO_BRANCH=${REPO_BRANCH:-main}
  read -p "安装目录（默认 ./ai-assistant）: " INSTALL_DIR
  INSTALL_DIR=${INSTALL_DIR:-./ai-assistant}

  info "克隆 $REPO_URL ($REPO_BRANCH) → $INSTALL_DIR"
  git clone --depth 1 -b "$REPO_BRANCH" "$REPO_URL" "$INSTALL_DIR"
  cd "$INSTALL_DIR"
  PROJECT_DIR=$(pwd)
  ok "代码获取完成"
fi

# ============================================================
# 3. 环境变量配置
# ============================================================
title "3/6  配置环境变量"

ENV_FILE="$PROJECT_DIR/.env"
ENV_EXAMPLE="$PROJECT_DIR/.env.example"

if [ -f "$ENV_FILE" ]; then
  info "检测到已有 .env 文件"
  echo "────────── 当前配置 ──────────"
  grep -v '^#' "$ENV_FILE" | grep -v '^$' | sed 's/DASHSCOPE_API_KEY=.*/DASHSCOPE_API_KEY=sk-****(已隐藏)/'
  echo "─────────────────────────────"
  read -p "是否重新配置？(y/N): " RECONFIG
else
  RECONFIG="y"
fi

if [[ "$RECONFIG" =~ ^[Yy]$ ]]; then
  # MySQL 密码
  read -p "MySQL Root 密码（留空自动生成16位随机密码）: " DB_PASS
  if [ -z "$DB_PASS" ]; then
    DB_PASS=$(tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 16)
    info "自动生成密码: $DB_PASS"
  fi

  # 数据库名
  read -p "数据库名（默认 ai_assistant）: " DB_NAME
  DB_NAME=${DB_NAME:-ai_assistant}

  # DashScope API Key
  read -p "阿里云 DashScope API Key (sk-...): " DASHSCOPE_KEY
  if [ -z "$DASHSCOPE_KEY" ]; then
    warn "未填写 API Key，LLM 功能暂时不可用，后续可编辑 .env 补充"
  fi

  # 写入 .env（用 echo 而非 heredoc 防止密码含特殊字符时出问题）
  > "$ENV_FILE"
  echo "# ---- MySQL 数据库配置 ----" >> "$ENV_FILE"
  echo "MYSQL_ROOT_PASSWORD=$DB_PASS" >> "$ENV_FILE"
  echo "MYSQL_DATABASE=$DB_NAME" >> "$ENV_FILE"
  echo "" >> "$ENV_FILE"
  echo "# ---- 数据库连接（后端用） ----" >> "$ENV_FILE"
  echo "DATABASE_URL=mysql+pymysql://root:${DB_PASS}@db:3306/${DB_NAME}" >> "$ENV_FILE"
  echo "" >> "$ENV_FILE"
  echo "# ---- 阿里云 DashScope API ----" >> "$ENV_FILE"
  echo "DASHSCOPE_API_KEY=$DASHSCOPE_KEY" >> "$ENV_FILE"

  ok ".env 文件已生成"
fi

# 从 .env 安全地读取变量
DB_PASS=$(grep -E '^MYSQL_ROOT_PASSWORD=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2-)
DB_NAME=$(grep -E '^MYSQL_DATABASE=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2-)
DB_NAME=${DB_NAME:-ai_assistant}

# ============================================================
# 4. JWT 密钥
# ============================================================
title "4/6  配置 JWT 密钥"

AUTH_FILE="$PROJECT_DIR/backend/utils/auth.py"
if [ -f "$AUTH_FILE" ] && grep -q 'SECRET_KEY = "your-secret-key-change-in-production"' "$AUTH_FILE" 2>/dev/null; then
  info "检测到默认 JWT 密钥，正在生成随机密钥..."
  JWT_SECRET=$(tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 64)
  # 跨平台 sed 替换
  if [[ "$(uname)" == "Darwin" ]]; then
    sed -i '' "s/SECRET_KEY = \"your-secret-key-change-in-production\"/SECRET_KEY = \"$JWT_SECRET\"/" "$AUTH_FILE"
  else
    sed -i "s/SECRET_KEY = \"your-secret-key-change-in-production\"/SECRET_KEY = \"$JWT_SECRET\"/" "$AUTH_FILE"
  fi
  ok "JWT 密钥已更新"
else
  ok "JWT 密钥已自定义（跳过）"
fi

# ============================================================
# 5. 构建 & 启动
# ============================================================
title "5/6  构建 & 启动 Docker 容器"

cd "$PROJECT_DIR"

# 创建必要的数据目录
mkdir -p backend/uploads backend/rag/data

# 构建镜像（首次会慢一些，后续缓存加速）
info "正在构建 Docker 镜像，首次约 3-10 分钟..."
$COMPOSE_CMD build --parallel 2>/dev/null || $COMPOSE_CMD build
ok "镜像构建完成"

# 启动服务
info "正在启动服务..."
$COMPOSE_CMD up -d
ok "服务已启动"

# 等待就绪
info "等待后端就绪（最多 60 秒）..."
BACKEND_READY=false
for i in $(seq 1 30); do
  if curl -sf http://localhost/health >/dev/null 2>&1; then
    BACKEND_READY=true
    ok "后端已就绪 ✓"
    break
  fi
  sleep 2
done

if [ "$BACKEND_READY" = false ]; then
  warn "后端未在 60s 内响应，请检查日志：$COMPOSE_CMD logs backend"
fi

# ============================================================
# 6. 验证
# ============================================================
title "6/6  部署验证"

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  🎉  AI Agent Assistant System 部署完成！${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 容器状态
echo -e "${GREEN}▶ 容器运行状态:${NC}"
$COMPOSE_CMD ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || $COMPOSE_CMD ps
echo ""

# 健康检查
echo -e "${GREEN}▶ 健康检查:${NC}"
HEALTH=$(curl -s http://localhost/health 2>/dev/null || echo "失败")
echo "   /health → $HEALTH"
DB_TEST=$(curl -s http://localhost/db-test 2>/dev/null || echo "失败")
echo "   /db-test → $DB_TEST"
echo ""

# 公网 IP
PUBLIC_IP=$(curl -s --max-time 3 http://checkip.amazonaws.com 2>/dev/null || \
            curl -s --max-time 3 https://api.ipify.org 2>/dev/null || \
            echo "")

echo -e "${GREEN}▶ 访问地址:${NC}"
echo -e "   本地:   ${CYAN}http://localhost${NC}"
if [ -n "$PUBLIC_IP" ]; then
  echo -e "   公网:   ${CYAN}http://$PUBLIC_IP${NC}"
  echo -e "   ${YELLOW}⚠ 请在 腾讯云控制台 → 防火墙 → 放行 80 端口${NC}"
fi
echo ""

echo -e "${GREEN}▶ 常用命令:${NC}"
echo "   docker compose logs -f          查看所有实时日志"
echo "   docker compose logs -f backend  查看后端日志"
echo "   docker compose restart          重启所有服务"
echo "   docker compose down             停止所有服务"
echo "   docker compose down -v          停止并清空数据库（危险！）"
echo ""

echo -e "${YELLOW}▶ 首次使用:${NC}"
echo "   1. 浏览器打开 http://${PUBLIC_IP:-服务器IP}"
echo "   2. 点击「注册」创建你的管理员账号"
echo "   3. 登录后即可使用 AI 助手"
if [ -z "$DASHSCOPE_KEY" ]; then
  echo ""
  echo -e "${YELLOW}   ⚠ 未配置 DashScope API Key，LLM 功能不可用${NC}"
  echo "     编辑 .env 填入 DASHSCOPE_API_KEY 后执行: docker compose restart backend"
fi
echo ""

# 检查退出容器
EXITED=$($COMPOSE_CMD ps --format json 2>/dev/null | grep -c "exited" || true)
if [ "$EXITED" -gt 0 ]; then
  warn "有 $EXITED 个容器异常退出！查看日志：$COMPOSE_CMD logs --tail=50"
fi

# ============================================================
# 保存部署信息
# ============================================================
cat > "$PROJECT_DIR/.deploy-info" <<INFO
部署时间: $(date '+%Y-%m-%d %H:%M:%S')
Docker 版本: $DOCKER_VER
Compose 命令: $COMPOSE_CMD
项目目录: $PROJECT_DIR
数据库: $DB_NAME
公网 IP: $PUBLIC_IP
INFO

info "部署信息已保存至 .deploy-info"
info "部署脚本执行完毕！"
