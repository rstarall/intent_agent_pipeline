#!/bin/bash

# Docker权限设置脚本
# 目的：允许普通用户在宿主机上运行docker命令，但容器内部仍使用root权限

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否以root权限运行
check_sudo() {
    if [ "$EUID" -ne 0 ]; then
        log_error "此脚本需要sudo权限运行"
        echo "使用方法: sudo bash scripts/setup_docker_permissions.sh [username]"
        exit 1
    fi
}

# 获取目标用户
get_target_user() {
    if [ -n "$1" ]; then
        TARGET_USER="$1"
    else
        # 获取调用sudo的实际用户
        if [ -n "$SUDO_USER" ]; then
            TARGET_USER="$SUDO_USER"
        else
            log_error "无法确定目标用户，请指定用户名"
            echo "使用方法: sudo bash scripts/setup_docker_permissions.sh [username]"
            exit 1
        fi
    fi
    
    # 验证用户是否存在
    if ! id "$TARGET_USER" >/dev/null 2>&1; then
        log_error "用户 '$TARGET_USER' 不存在"
        exit 1
    fi
    
    log_info "目标用户: $TARGET_USER"
}

# 检查Docker是否已安装
check_docker() {
    log_info "检查Docker安装状态..."
    
    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker未安装，请先安装Docker"
        echo "安装命令（Ubuntu/Debian）:"
        echo "curl -fsSL https://get.docker.com -o get-docker.sh"
        echo "sudo sh get-docker.sh"
        exit 1
    fi
    
    if ! command -v docker-compose >/dev/null 2>&1; then
        log_warning "docker-compose未安装，建议安装以使用docker-compose功能"
        echo "安装命令: sudo apt-get install docker-compose-plugin"
    fi
    
    log_success "Docker已安装"
}

# 创建docker组并添加用户
setup_docker_group() {
    log_info "设置docker组权限..."
    
    # 创建docker组（如果不存在）
    if ! getent group docker >/dev/null; then
        log_info "创建docker组..."
        groupadd docker
    else
        log_info "docker组已存在"
    fi
    
    # 将用户添加到docker组
    if groups "$TARGET_USER" | grep -q "\bdocker\b"; then
        log_info "用户 $TARGET_USER 已在docker组中"
    else
        log_info "将用户 $TARGET_USER 添加到docker组..."
        usermod -aG docker "$TARGET_USER"
        log_success "用户已添加到docker组"
    fi
}

# 启动并启用Docker服务
setup_docker_service() {
    log_info "设置Docker服务..."
    
    # 启动Docker服务
    if systemctl is-active --quiet docker; then
        log_info "Docker服务已运行"
    else
        log_info "启动Docker服务..."
        systemctl start docker
        log_success "Docker服务已启动"
    fi
    
    # 设置Docker开机自启
    if systemctl is-enabled --quiet docker; then
        log_info "Docker服务已设置开机自启"
    else
        log_info "设置Docker服务开机自启..."
        systemctl enable docker
        log_success "Docker服务已设置开机自启"
    fi
}

# 设置项目文件权限
setup_project_permissions() {
    log_info "设置项目文件权限..."
    
    PROJECT_ROOT=$(dirname "$(dirname "$(realpath "$0")")")
    
    # 确保用户拥有项目目录的访问权限
    chown -R "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT/logs" 2>/dev/null || mkdir -p "$PROJECT_ROOT/logs" && chown -R "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT/logs"
    chown -R "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT/data" 2>/dev/null || mkdir -p "$PROJECT_ROOT/data" && chown -R "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT/data"
    
    # 设置docker相关文件权限
    if [ -f "$PROJECT_ROOT/docker-compose.yml" ]; then
        chown "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT/docker-compose.yml"
    fi
    
    if [ -f "$PROJECT_ROOT/docker/docker-compose.yml" ]; then
        chown -R "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT/docker/"
    fi
    
    log_success "项目文件权限设置完成"
}

# 创建快捷脚本
create_user_scripts() {
    log_info "创建用户快捷脚本..."
    
    USER_HOME=$(eval echo "~$TARGET_USER")
    SCRIPT_DIR="$USER_HOME/.local/bin"
    
    # 创建脚本目录
    sudo -u "$TARGET_USER" mkdir -p "$SCRIPT_DIR"
    
    # 创建docker管理脚本
    cat > "$SCRIPT_DIR/manage-docker.sh" << 'EOF'
#!/bin/bash

# Docker管理快捷脚本
# 容器内部仍使用root权限

PROJECT_ROOT="$HOME/intent_agent_pipeline"

case "$1" in
    "start")
        echo "启动服务..."
        cd "$PROJECT_ROOT" && docker-compose -f docker/docker-compose.yml up -d
        ;;
    "stop")
        echo "停止服务..."
        cd "$PROJECT_ROOT" && docker-compose -f docker/docker-compose.yml down
        ;;
    "restart")
        echo "重启服务..."
        cd "$PROJECT_ROOT" && docker-compose -f docker/docker-compose.yml restart
        ;;
    "logs")
        echo "查看日志..."
        cd "$PROJECT_ROOT" && docker-compose -f docker/docker-compose.yml logs -f
        ;;
    "shell")
        echo "进入容器shell (root权限)..."
        cd "$PROJECT_ROOT" && docker-compose -f docker/docker-compose.yml exec intent-agent-pipeline bash
        ;;
    "build")
        echo "构建镜像..."
        cd "$PROJECT_ROOT" && docker-compose -f docker/docker-compose.yml build --no-cache
        ;;
    "status")
        echo "查看状态..."
        cd "$PROJECT_ROOT" && docker-compose -f docker/docker-compose.yml ps
        ;;
    *)
        echo "使用方法: $0 {start|stop|restart|logs|shell|build|status}"
        echo ""
        echo "命令说明:"
        echo "  start   - 启动所有服务"
        echo "  stop    - 停止所有服务"
        echo "  restart - 重启所有服务"
        echo "  logs    - 查看实时日志"
        echo "  shell   - 进入主容器shell (root权限)"
        echo "  build   - 重新构建镜像"
        echo "  status  - 查看容器状态"
        exit 1
        ;;
esac
EOF

    chmod +x "$SCRIPT_DIR/manage-docker.sh"
    chown "$TARGET_USER:$TARGET_USER" "$SCRIPT_DIR/manage-docker.sh"
    
    log_success "快捷脚本创建完成: $SCRIPT_DIR/manage-docker.sh"
}

# 验证设置
verify_setup() {
    log_info "验证设置..."
    
    # 检查用户是否在docker组中
    if groups "$TARGET_USER" | grep -q "\bdocker\b"; then
        log_success "✓ 用户在docker组中"
    else
        log_error "✗ 用户不在docker组中"
        return 1
    fi
    
    # 检查Docker服务状态
    if systemctl is-active --quiet docker; then
        log_success "✓ Docker服务运行正常"
    else
        log_error "✗ Docker服务未运行"
        return 1
    fi
    
    log_success "所有设置验证通过！"
}

# 显示使用说明
show_usage_info() {
    log_info "设置完成！使用说明："
    echo ""
    echo -e "${GREEN}以普通用户身份使用Docker：${NC}"
    echo "1. 重新登录或运行: newgrp docker"
    echo "2. 测试docker命令: docker --version"
    echo "3. 测试docker run: docker run hello-world"
    echo ""
    echo -e "${GREEN}管理项目：${NC}"
    echo "使用快捷脚本: ~/.local/bin/manage-docker.sh"
    echo "  例如: ~/.local/bin/manage-docker.sh start"
    echo ""
    echo -e "${GREEN}容器内权限说明：${NC}"
    echo "• 容器内部默认使用root用户"
    echo "• 可以通过以下命令进入容器："
    echo "  ~/.local/bin/manage-docker.sh shell"
    echo ""
    echo -e "${YELLOW}注意：${NC}"
    echo "• 首次使用需要重新登录才能生效"
    echo "• 如果仍无法使用docker命令，请运行: newgrp docker"
    echo "• 容器内root权限仅在容器内有效，不影响宿主机安全"
}

# 主函数
main() {
    echo "========================================"
    echo "     Docker权限设置脚本"
    echo "========================================"
    echo ""
    
    check_sudo
    get_target_user "$1"
    check_docker
    setup_docker_group
    setup_docker_service
    setup_project_permissions
    create_user_scripts
    
    echo ""
    echo "========================================"
    
    if verify_setup; then
        echo ""
        show_usage_info
        echo ""
        log_success "Docker权限设置完成！"
    else
        echo ""
        log_error "设置过程中出现问题，请检查上述错误信息"
        exit 1
    fi
}

# 运行主函数
main "$@" 