#!/bin/bash
echo "==================================="
echo "  k8s-jenkins一键控制脚本"
echo "  1.停止jenkins（缩容到0）"
echo "  2.启动jenkins（恢复为1）"
echo "==================================="
read -p "请输入选项【1/2】：" opt

case $opt in
        1)
        echo "正在停止jenkins..."
        kubectl scale deployment -n ci jenkins --replicas=0
        echo "jenkins已停止！"
        ;;

        2)
        echo "正在启动jenkins..."
        kubectl scale deployment -n ci jenkins --replicas=1
        echo "jenkins已启动！"
        ;;

        *)
        echo "输入错误！请输入1或2"
        ;;
esac
