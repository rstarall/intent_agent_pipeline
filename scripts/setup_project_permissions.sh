#!/bin/bash

# 项目权限设置脚本
# 目的：赋予普通用户对整个项目的完全修改权限

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
        echo "使用方法: sudo bash scripts/setup_project_permissions.sh [username]"
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
            echo "使用方法: sudo bash scripts/setup_project_permissions.sh [username]"
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

# 获取项目根目录
get_project_root() {
    PROJECT_ROOT=$(dirname "$(dirname "$(realpath "$0")")")
    log_info "项目根目录: $PROJECT_ROOT"
    
    # 验证这确实是项目目录
    if [ ! -f "$PROJECT_ROOT/requirements.txt" ] || [ ! -d "$PROJECT_ROOT/app" ]; then
        log_error "未找到项目标识文件，请确认脚本在正确的项目目录中"
        exit 1
    fi
}

# 设置项目目录权限
setup_project_ownership() {
    log_info "设置项目目录所有权..."
    
    # 递归更改整个项目目录的所有者
    chown -R "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT"
    log_success "项目目录所有权已设置为 $TARGET_USER"
    
    # 设置目录权限为755 (rwxr-xr-x)
    find "$PROJECT_ROOT" -type d -exec chmod 755 {} \;
    log_success "目录权限已设置为755"
    
    # 设置普通文件权限为644 (rw-r--r--)
    find "$PROJECT_ROOT" -type f -exec chmod 644 {} \;
    log_success "文件权限已设置为644"
    
    # 设置脚本文件权限为755 (rwxr-xr-x)
    find "$PROJECT_ROOT" -name "*.sh" -exec chmod 755 {} \;
    find "$PROJECT_ROOT/scripts" -name "*.py" -exec chmod 755 {} \; 2>/dev/null || true
    log_success "可执行文件权限已设置为755"
}

# 设置特殊目录权限
setup_special_directories() {
    log_info "设置特殊目录权限..."
    
    # 创建并设置logs目录权限
    if [ ! -d "$PROJECT_ROOT/logs" ]; then
        mkdir -p "$PROJECT_ROOT/logs"
    fi
    chown -R "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT/logs"
    chmod 755 "$PROJECT_ROOT/logs"
    
    # 创建并设置data目录权限  
    if [ ! -d "$PROJECT_ROOT/data" ]; then
        mkdir -p "$PROJECT_ROOT/data"
    fi
    chown -R "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT/data"
    chmod 755 "$PROJECT_ROOT/data"
    
    # 设置.pytest_cache目录权限（如果存在）
    if [ -d "$PROJECT_ROOT/.pytest_cache" ]; then
        chown -R "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT/.pytest_cache"
        chmod 755 "$PROJECT_ROOT/.pytest_cache"
    fi
    
    # 设置__pycache__目录权限
    find "$PROJECT_ROOT" -name "__pycache__" -type d -exec chown -R "$TARGET_USER:$TARGET_USER" {} \; 2>/dev/null || true
    find "$PROJECT_ROOT" -name "__pycache__" -type d -exec chmod 755 {} \; 2>/dev/null || true
    
    log_success "特殊目录权限设置完成"
}

# 设置git权限
setup_git_permissions() {
    log_info "设置Git权限..."
    
    if [ -d "$PROJECT_ROOT/.git" ]; then
        chown -R "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT/.git"
        chmod 755 "$PROJECT_ROOT/.git"
        
        # 设置git hooks权限
        if [ -d "$PROJECT_ROOT/.git/hooks" ]; then
            find "$PROJECT_ROOT/.git/hooks" -type f -exec chmod 755 {} \;
        fi
        
        log_success "Git权限设置完成"
    else
        log_warning "未找到.git目录"
    fi
}

# 设置Docker相关权限
setup_docker_permissions() {
    log_info "设置Docker相关文件权限..."
    
    # Docker目录权限
    if [ -d "$PROJECT_ROOT/docker" ]; then
        chown -R "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT/docker"
        chmod 755 "$PROJECT_ROOT/docker"
        
        # 设置docker脚本权限
        find "$PROJECT_ROOT/docker" -name "*.sh" -exec chmod 755 {} \;
        
        log_success "Docker目录权限设置完成"
    fi
    
    # docker-compose文件权限
    for compose_file in "docker-compose.yml" "docker-compose.*.yml"; do
        if ls "$PROJECT_ROOT"/$compose_file 1> /dev/null 2>&1; then
            chown "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT"/$compose_file
            chmod 644 "$PROJECT_ROOT"/$compose_file
        fi
    done
}

# 设置配置文件权限
setup_config_permissions() {
    log_info "设置配置文件权限..."
    
    # .env 文件权限（如果存在）
    for env_file in ".env" ".env.*"; do
        if ls "$PROJECT_ROOT"/$env_file 1> /dev/null 2>&1; then
            chown "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT"/$env_file
            chmod 600 "$PROJECT_ROOT"/$env_file  # 环境变量文件使用更严格的权限
        fi
    done
    
    # 其他配置文件
    for config_file in "requirements.txt" "requirements-dev.txt" "pytest.ini" "setup.py" "pyproject.toml"; do
        if [ -f "$PROJECT_ROOT/$config_file" ]; then
            chown "$TARGET_USER:$TARGET_USER" "$PROJECT_ROOT/$config_file"
            chmod 644 "$PROJECT_ROOT/$config_file"
        fi
    done
    
    log_success "配置文件权限设置完成"
}

# 验证权限设置
verify_permissions() {
    log_info "验证权限设置..."
    
    # 检查项目根目录权限
    if [ "$(stat -c %U "$PROJECT_ROOT")" = "$TARGET_USER" ]; then
        log_success "✓ 项目根目录所有权正确"
    else
        log_error "✗ 项目根目录所有权不正确"
        return 1
    fi
    
    # 检查核心应用目录权限
    if [ -d "$PROJECT_ROOT/app" ]; then
        if [ "$(stat -c %U "$PROJECT_ROOT/app")" = "$TARGET_USER" ]; then
            log_success "✓ 应用目录所有权正确"
        else
            log_error "✗ 应用目录所有权不正确"
            return 1
        fi
    fi
    
    # 测试写入权限
    TEST_FILE="$PROJECT_ROOT/.permission_test"
    if sudo -u "$TARGET_USER" touch "$TEST_FILE" 2>/dev/null; then
        sudo -u "$TARGET_USER" rm -f "$TEST_FILE"
        log_success "✓ 写入权限测试通过"
    else
        log_error "✗ 写入权限测试失败"
        return 1
    fi
    
    log_success "所有权限验证通过！"
}

# 显示权限信息
show_permission_info() {
    log_info "权限设置摘要："
    echo ""
    echo -e "${GREEN}项目目录结构权限：${NC}"
    echo "• 目录权限: 755 (rwxr-xr-x)"
    echo "• 普通文件: 644 (rw-r--r--)"  
    echo "• 可执行脚本: 755 (rwxr-xr-x)"
    echo "• 环境配置文件: 600 (rw-------)"
    echo ""
    echo -e "${GREEN}用户权限：${NC}"
    echo "• 项目所有者: $TARGET_USER"
    echo "• 可以读写修改所有项目文件"
    echo "• 可以创建删除文件和目录"
    echo "• 可以执行脚本文件"
    echo ""
    echo -e "${GREEN}测试权限：${NC}"
    echo "# 测试文件创建权限"
    echo "touch $PROJECT_ROOT/test_file.txt"
    echo ""
    echo "# 测试目录创建权限"  
    echo "mkdir $PROJECT_ROOT/test_dir"
    echo ""
    echo "# 测试文件编辑权限"
    echo "echo 'test' > $PROJECT_ROOT/test_file.txt"
    echo ""
    echo -e "${YELLOW}注意：${NC}"
    echo "• 如果仍有权限问题，请重新登录或刷新文件管理器"
    echo "• VSCode需要重启才能识别新的文件权限"
    echo "• Docker容器内部仍然使用root权限运行"
}

# 创建权限恢复脚本
create_restore_script() {
    log_info "创建权限恢复脚本..."
    
    RESTORE_SCRIPT="$PROJECT_ROOT/scripts/restore_permissions.sh"
    
    cat > "$RESTORE_SCRIPT" << EOF
#!/bin/bash
# 权限快速恢复脚本
# 当权限出现问题时可以快速重置

TARGET_USER=\${1:-$TARGET_USER}

echo "恢复项目权限为用户: \$TARGET_USER"

sudo chown -R "\$TARGET_USER:\$TARGET_USER" "$PROJECT_ROOT"
sudo find "$PROJECT_ROOT" -type d -exec chmod 755 {} \\;
sudo find "$PROJECT_ROOT" -type f -exec chmod 644 {} \\;
sudo find "$PROJECT_ROOT" -name "*.sh" -exec chmod 755 {} \\;

echo "权限恢复完成！"
EOF

    chmod 755 "$RESTORE_SCRIPT"
    chown "$TARGET_USER:$TARGET_USER" "$RESTORE_SCRIPT"
    
    log_success "权限恢复脚本已创建: scripts/restore_permissions.sh"
}

# 主函数
main() {
    echo "========================================"
    echo "     项目权限设置脚本"
    echo "========================================"
    echo ""
    
    check_sudo
    get_target_user "$1"
    get_project_root
    
    setup_project_ownership
    setup_special_directories
    setup_git_permissions
    setup_docker_permissions
    setup_config_permissions
    create_restore_script
    
    echo ""
    echo "========================================"
    
    if verify_permissions; then
        echo ""
        show_permission_info
        echo ""
        log_success "项目权限设置完成！用户 $TARGET_USER 现在拥有完整的项目修改权限。"
    else
        echo ""
        log_error "权限设置过程中出现问题，请检查上述错误信息"
        exit 1
    fi
}

# 运行主函数
main "$@" 