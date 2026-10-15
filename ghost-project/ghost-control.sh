#!/bin/bash
echo "==================================="
echo "  k8s-ghost监控组件一键控制脚本"
echo "  1.停止ghost及所有监控（缩容到0）"
echo "  2.启动ghost及所有监控（恢复为1）"
echo "==================================="
read -p "请输入选项【1/2】：" opt

case $opt in
	1)
	echo "正在停止ghost及监控组件..."
	kubectl scale deployment -n monitoring prometheus --replicas=0
	kubectl scale deployment -n monitoring grafana --replicas=0
	kubectl scale deployment -n monitoring alertmanager --replicas=0
	kubectl scale deployment -n monitoring blackbox-exporter --replicas=0
	kubectl scale deployment -n monitoring prometheus-webhook-dingtalk --replicas=0
	kubectl scale deployment -n blog ghost-local --replicas=0
	kubectl scale deployment -n blog mysql-exporter --replicas=0
	kubectl scale deployment -n blog mysql-local --replicas=0
	#kubectl delete hpa ghost-local-hpa -n blog --ignore-not-found
	echo "ghost及相关监控组件已停止！"
	;;

	2)
	echo "正在启动ghost及监控组件..."
	kubectl scale deployment -n monitoring prometheus --replicas=1
	kubectl scale deployment -n monitoring grafana --replicas=1
	kubectl scale deployment -n monitoring alertmanager --replicas=1
	kubectl scale deployment -n monitoring blackbox-exporter --replicas=1
	kubectl scale deployment -n monitoring prometheus-webhook-dingtalk --replicas=1
	kubectl scale deployment -n blog ghost-local --replicas=1
	kubectl scale deployment -n blog mysql-exporter --replicas=1
	kubectl scale deployment -n blog mysql-local --replicas=1
	#kubectl apply -f /root/K8S-Project/ghost-project/hpa-ghost/ghost-hpa.yaml
	echo "ghost及相关监控组件已启动！"
	;;
	
	*)
	echo "输入错误！请输入1或2"
	;;
esac
