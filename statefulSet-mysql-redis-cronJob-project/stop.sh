#!/bin/bash
# stop.sh 一键销毁整套环境
NAMESPACE="biz"

echo "===== 1.删除CronJob定时任务 ====="
kubectl delete -f backup-cronjob.yaml -n $NAMESPACE

echo "===== 2.删除MySQL、Redis StatefulSet ====="
kubectl delete -f mysql-sts.yaml -n $NAMESPACE
kubectl delete -f redis-sts.yaml -n $NAMESPACE

echo "===== 3.删除备份PVC（包含备份文件） ====="
kubectl delete -f backup-pvc.yaml -n $NAMESPACE

echo "===== 4.删除RBAC权限资源 ====="
kubectl delete -f backup-rbac.yaml -n $NAMESPACE

echo "===== 5.删除Secret ====="
kubectl delete -f secret.yaml -n $NAMESPACE

echo "===== 删除命名空间 $NAMESPACE ====="
kubectl delete ns $NAMESPACE

echo "===== 环境清理完成 ====="
