#!/bin/bash
echo "==================================="
echo "  chaos-mesh一键控制脚本"
echo "  1.停止chaos-mesh（缩容到0）"
echo "  2.启动chaos-mesh（恢复为1）"
echo "==================================="
read -p "请输入选项【1/2】：" opt

NAMESPACE="chaos-mesh"

case "$opt" in
  1)
    echo "正在停用 Chaos Mesh..."
    kubectl -n $NAMESPACE scale deployment chaos-controller-manager --replicas=0
    kubectl -n $NAMESPACE scale deployment chaos-dashboard --replicas=0
    kubectl -n $NAMESPACE scale deployment chaos-dns-server --replicas=0
    # DaemonSet 缩容需要删除其 Pod，恢复时控制器会自动重建
    kubectl -n $NAMESPACE patch daemonset chaos-daemon -p '{"spec":{"template":{"spec":{"nodeSelector":{"chaos-mesh/active":"true"}}}}}' 2>/dev/null || \
    kubectl -n $NAMESPACE delete pods -l app.kubernetes.io/component=chaos-daemon
    echo "Chaos Mesh 已停用。"
    ;;
  2)
    echo "正在启动 Chaos Mesh..."
    kubectl -n $NAMESPACE scale deployment chaos-controller-manager --replicas=3
    kubectl -n $NAMESPACE scale deployment chaos-dashboard --replicas=1
    kubectl -n $NAMESPACE scale deployment chaos-dns-server --replicas=1
    # 恢复 DaemonSet（如果是通过 nodeSelector 禁用的方式）
    kubectl -n $NAMESPACE patch daemonset chaos-daemon --type=json -p '[{"op":"remove","path":"/spec/template/spec/nodeSelector/chaos-mesh~1active"}]' 2>/dev/null || true
    echo "Chaos Mesh 已启动。"
    ;;
  *)
    echo "用法: $0 {start|stop}"
    exit 1
    ;;
esac
