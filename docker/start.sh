#!/bin/bash

# 化妆品知识库问答机器人Pipeline项目 Docker 启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# 检查Docker和Docker Compose是否安装
check_dependencies() {
    print_message $BLUE "检查依赖..."
    
    if ! command -v docker &> /dev/null; then
        print_message $RED "错误: Docker 未安装"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_message $RED "错误: Docker Compose 未安装"
        exit 1
    fi
    
    print_message $GREEN "依赖检查通过"
}

# 检查环境变量文件
check_env_file() {
    print_message $BLUE "检查环境配置..."
    
    if [ ! -f "../.env" ]; then
        if [ -f "../.env.example" ]; then
            print_message $YELLOW "未找到 .env 文件，从 .env.example 复制..."
            cp ../.env.example ../.env
            print_message $YELLOW "请编辑 .env 文件并设置必要的环境变量"
        else
            print_message $RED "错误: 未找到 .env.example 文件"
            exit 1
        fi
    fi
    
    print_message $GREEN "环境配置检查完成"
}

# 构建镜像
build_images() {
    print_message $BLUE "构建Docker镜像..."
    docker-compose -f docker-compose.yml build
    print_message $GREEN "镜像构建完成"
}

# 启动服务
start_services() {
    local env=$1
    local compose_file="docker-compose.yml"
    
    if [ "$env" = "dev" ]; then
        compose_file="docker-compose.dev.yml"
        print_message $BLUE "启动开发环境服务..."
    else
        print_message $BLUE "启动生产环境服务..."
    fi
    
    docker-compose -f $compose_file up -d
    
    print_message $GREEN "服务启动完成"
    print_message $BLUE "等待服务就绪..."
    sleep 10
}

# 检查服务状态
check_services() {
    local env=$1
    local compose_file="docker-compose.yml"
    
    if [ "$env" = "dev" ]; then
        compose_file="docker-compose.dev.yml"
    fi
    
    print_message $BLUE "检查服务状态..."
    docker-compose -f $compose_file ps
    
    # 检查应用健康状态
    local app_url="http://localhost:8000"
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f -s $app_url/api/v1/health > /dev/null; then
            print_message $GREEN "应用服务就绪"
            break
        else
            print_message $YELLOW "等待应用服务启动... ($attempt/$max_attempts)"
            sleep 2
            ((attempt++))
        fi
    done
    
    if [ $attempt -gt $max_attempts ]; then
        print_message $RED "应用服务启动超时"
        print_message $BLUE "查看日志:"
        docker-compose -f $compose_file logs intent-agent-pipeline
        exit 1
    fi
}

# 显示服务信息
show_services_info() {
    local env=$1
    
    print_message $GREEN "=== 服务信息 ==="
    print_message $BLUE "主应用: http://localhost:8000"
    print_message $BLUE "API文档: http://localhost:8000/docs"
    print_message $BLUE "健康检查: http://localhost:8000/api/v1/health"
    
    if [ "$env" = "dev" ]; then
        print_message $BLUE "Redis管理: http://localhost:8081"
        print_message $BLUE "PostgreSQL管理: http://localhost:8082 (admin@example.com / admin)"
        print_message $BLUE "日志查看: http://localhost:8083"
        print_message $BLUE "Redis端口: 6380"
        print_message $BLUE "PostgreSQL端口: 5433"
    else
        print_message $BLUE "Redis端口: 6379"
        print_message $BLUE "PostgreSQL端口: 5432"
    fi
    
    print_message $GREEN "=== 常用命令 ==="
    print_message $BLUE "查看日志: docker-compose logs -f [service_name]"
    print_message $BLUE "停止服务: docker-compose down"
    print_message $BLUE "重启服务: docker-compose restart [service_name]"
    print_message $BLUE "进入容器: docker-compose exec [service_name] bash"
}

# 停止服务
stop_services() {
    local env=$1
    local compose_file="docker-compose.yml"
    
    if [ "$env" = "dev" ]; then
        compose_file="docker-compose.dev.yml"
    fi
    
    print_message $BLUE "停止服务..."
    docker-compose -f $compose_file down
    print_message $GREEN "服务已停止"
}

# 清理资源
cleanup() {
    local env=$1
    local compose_file="docker-compose.yml"
    
    if [ "$env" = "dev" ]; then
        compose_file="docker-compose.dev.yml"
    fi
    
    print_message $BLUE "清理资源..."
    docker-compose -f $compose_file down -v --remove-orphans
    docker system prune -f
    print_message $GREEN "资源清理完成"
}

# 显示帮助信息
show_help() {
    echo "化妆品知识库问答机器人Pipeline项目 Docker 启动脚本"
    echo ""
    echo "用法: $0 [命令] [选项]"
    echo ""
    echo "命令:"
    echo "  start [dev|prod]  启动服务 (默认: prod)"
    echo "  stop [dev|prod]   停止服务 (默认: prod)"
    echo "  restart [dev|prod] 重启服务 (默认: prod)"
    echo "  build             构建镜像"
    echo "  logs [service]    查看日志"
    echo "  status [dev|prod] 查看服务状态 (默认: prod)"
    echo "  cleanup [dev|prod] 清理资源 (默认: prod)"
    echo "  help              显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 start dev      启动开发环境"
    echo "  $0 start prod     启动生产环境"
    echo "  $0 logs app       查看应用日志"
    echo "  $0 stop dev       停止开发环境"
}

# 主函数
main() {
    local command=${1:-help}
    local env=${2:-prod}
    
    case $command in
        start)
            check_dependencies
            check_env_file
            build_images
            start_services $env
            check_services $env
            show_services_info $env
            ;;
        stop)
            stop_services $env
            ;;
        restart)
            stop_services $env
            start_services $env
            check_services $env
            show_services_info $env
            ;;
        build)
            check_dependencies
            build_images
            ;;
        logs)
            local service=${2:-intent-agent-pipeline}
            local compose_file="docker-compose.yml"
            if [ "$env" = "dev" ]; then
                compose_file="docker-compose.dev.yml"
            fi
            docker-compose -f $compose_file logs -f $service
            ;;
        status)
            check_services $env
            ;;
        cleanup)
            cleanup $env
            ;;
        help|*)
            show_help
            ;;
    esac
}

# 执行主函数
main "$@"
