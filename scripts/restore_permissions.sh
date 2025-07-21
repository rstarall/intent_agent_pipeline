#!/bin/bash
# 权限快速恢复脚本
# 当权限出现问题时可以快速重置

TARGET_USER=${1:-ubuntu}

echo "恢复项目权限为用户: $TARGET_USER"

sudo chown -R "$TARGET_USER:$TARGET_USER" "/home/ubuntu/intent_agent_pipeline"
sudo find "/home/ubuntu/intent_agent_pipeline" -type d -exec chmod 755 {} \;
sudo find "/home/ubuntu/intent_agent_pipeline" -type f -exec chmod 644 {} \;
sudo find "/home/ubuntu/intent_agent_pipeline" -name "*.sh" -exec chmod 755 {} \;

echo "权限恢复完成！"
