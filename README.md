# K8S-Project

Kubernetes / 云原生练习项目合集，覆盖存储、编排、监控、日志、CI/CD、混沌工程等常见场景。

集群环境：Kubernetes，私有镜像仓库 Harbor，节点 `192.168.19.132`。

## 目录结构

| 目录 | 内容 |
| --- | --- |
| `harbor-project/` | Harbor 私有镜像仓库部署（配置文件与安装脚本） |
| `ghost-project/` | Ghost 博客部署：hostPath / local-path 两种 PV 方案、HPA 弹性伸缩、Prometheus + Grafana + Blackbox + 钉钉告警 |
| `helm-project/` | `biz-db-chart`：MySQL + Redis StatefulSet 与备份 CronJob 的 Helm Chart，含 dev / test / prod 多环境 values |
| `Loki-Fluent-Bit-Project/` | Loki + Fluent Bit 日志采集（Helm 部署） |
| `statefulSet-mysql-redis-cronJob-project/` | StatefulSet 部署 MySQL / Redis 及备份 CronJob |
| `jenkins-project/` | Jenkins 部署清单（Deployment、Service、RBAC、PV/PVC） |
| `git/` | Jenkins 流水线示例（Dockerfile、Jenkinsfile） |
| `HPA/` | metrics-server 组件与 Nginx HPA 配置 |
| `Chaos-Mesh/` | 混沌工程实验（Pod Kill、Pod Failure） |
| `local-path-provisioner-project/` | local-path 动态存储供给 |
| `ansible-web-deploy/` | Ansible 部署 Nginx 站点，含回滚 playbook |

## 使用说明

各目录下均为独立的 YAML / Chart，按需 `kubectl apply -f` 或 `helm install` 即可。

需要额外准备的内容，本仓库未包含：

- **Harbor 离线安装包**：`harbor-offline-installer-v1.10.1.tgz` 体积超过 600 MB，请从 [Harbor Releases](https://github.com/goharbor/harbor/releases) 自行下载后放入 `harbor-project/`。
- **Helm 依赖子 Chart**：`Loki-Fluent-Bit-Project/loki-stack/charts/` 为第三方 charts，进入该目录执行 `helm dependency build` 即可拉取。

## 注意

仓库中的密码（`root123`、`Harbor12345`、`admin123` 等）均为练习环境使用的默认值。真实环境的凭据请勿提交，仓库中随机的 `CORE_SECRET`、钉钉机器人 `access_token` 已替换为占位符。
