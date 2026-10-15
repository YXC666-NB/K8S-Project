#!/bin/bash
# start.sh 一键部署 biz 命名空间整套项目

NAMESPACE="biz"

echo "===== 1.创建命名空间 $NAMESPACE ====="
kubectl create ns $NAMESPACE

echo "===== 2.部署Secret密码 ====="
kubectl apply -f secret.yaml -n $NAMESPACE

echo "===== 3.部署MySQL StatefulSet + 无头Service ====="
kubectl apply -f mysql-sts.yaml -n $NAMESPACE

echo "===== 4.部署Redis StatefulSet + 无头Service ====="
kubectl apply -f redis-sts.yaml -n $NAMESPACE

echo "===== 5.部署备份RBAC权限 ====="
kubectl apply -f backup-rbac.yaml -n $NAMESPACE

echo "===== 6.部署备份PVC ====="
kubectl apply -f backup-pvc.yaml -n $NAMESPACE

echo "===== 7.部署CronJob定时备份 ====="
kubectl apply -f backup-cronjob.yaml -n $NAMESPACE

echo ""
echo "===== 全部资源提交完成，等待Pod启动 ====="
kubectl get all -n $NAMESPACE
echo ""
echo "查看PVC：kubectl get pvc -n $NAMESPACE"
echo "手动触发一次备份测试：kubectl create job manual-backup --from=cronjob/db-backup-cron -n $NAMESPACE"


