# K8S-Project

云原生运维与 AIOps 实践项目合集。前半部分是 Kubernetes 各核心能力的动手实践（存储、编排、监控、日志、CI/CD、混沌工程），后半部分是一个完整的 **AIOps 智能运维 Agent**——把 Prometheus 告警接入大模型 Agent，自动完成故障排查并产出报告。

集群环境：Kubernetes v1.x（`192.168.19.132`），私有镜像仓库 Harbor，节点 `192.168.19.132` / `192.168.19.135` / `192.168.19.136`。

## 项目总览

| 模块 | 类型 | 说明 |
| --- | --- | --- |
| [`aiops-agent/`](#一aiops-agent智能运维-agent) | AI 应用 | 基于 LangGraph 的告警自愈 Agent，接入 Alertmanager 自动排障 |
| [`ghost-project/`](#二kubernetes-运维实践模块) | K8s 实践 | Ghost 博客部署 + PV 方案 + HPA + 全套监控告警 |
| [`harbor-project/`](#二kubernetes-运维实践模块) | K8s 实践 | Harbor 私有镜像仓库部署 |
| [`helm-project/`](#二kubernetes-运维实践模块) | Helm | MySQL + Redis 多环境 Chart |
| [`Loki-Fluent-Bit-Project/`](#二kubernetes-运维实践模块) | 日志 | Loki + Fluent Bit 日志采集 |
| [`statefulSet-mysql-redis-cronJob-project/`](#二kubernetes-运维实践模块) | K8s 实践 | StatefulSet 有状态服务与备份 CronJob |
| [`jenkins-project/`](#二kubernetes-运维实践模块) | CI/CD | Jenkins 部署与流水线 |
| [`git/`](#二kubernetes-运维实践模块) | CI/CD | Docker 镜像构建与 Jenkinsfile |
| [`HPA/`](#二kubernetes-运维实践模块) | 弹性伸缩 | metrics-server 与 Nginx HPA |
| [`Chaos-Mesh/`](#二kubernetes-运维实践模块) | 混沌工程 | Pod 故障注入实验 |
| [`local-path-provisioner-project/`](#二kubernetes-运维实践模块) | 存储 | local-path 动态存储供给 |
| [`ansible-web-deploy/`](#二kubernetes-运维实践模块) | 自动化 | Ansible 部署 Nginx 站点与回滚 |

---

# 一、AIOps 智能运维 Agent

`aiops-agent/` —— 一个跑在容器里的 SRE 智能体。Prometheus 触发告警后，Alertmanager 把告警推到它的 HTTP 接口，Agent 自主判断该查服务器还是查集群，调用工具采集现场信息，最后由大模型输出「现象分析 / 可能根因 / 处理建议」，并落盘成 Markdown 报告。

## 实现功能

**1. 告警接入与异步排障**
- `POST /api/v1/alert/receive` 接收 Alertmanager 的 webhook 告警（含 `alerts` 数组）
- 通过 FastAPI `BackgroundTasks` 把排障逻辑丢到后台执行，接口立即返回 `accepted,agent running in background`，不会阻塞 Alertmanager 的告警投递
- `GET /health` 提供存活探针，供容器 healthcheck 使用

**2. ReAct 自主排障 Agent**
- 用 LangGraph 的 `create_react_agent` 构建 ReAct 循环，模型自主决定调用哪个工具、调用几次，而非固定流程
- 内置 Prompt 引导排障路径：告警带 `instance` IP 就去查服务器，K8s 相关告警就去查集群
- 输出结构固定为「现象分析 → 可能根因 → 处理建议」

**3. 四个运维工具（`@tool` 封装）**

| 工具 | 能力 |
| --- | --- |
| `get_server_basic_info(host)` | 通过 SSH 登录受管服务器，采集 `uptime`、`free -h`、`df -h`、`dmesg` 最近报错 |
| `k8s_list_pod(namespace)` | 列出命名空间下所有 Pod 的状态与**重启次数**（快速定位 CrashLoopBackOff） |
| `k8s_get_pod_log(namespace, pod_name, tail_lines)` | 拉取 Pod 容器日志 |
| `k8s_get_events(namespace)` | 拉取最近 20 条 K8s Event，用于定位调度失败、镜像拉取失败等问题 |

**4. 排障报告自动落盘**
- 每次排障生成 `reports/alert_report_<时间戳>.md`，内含告警原文 JSON、生成时间和 Agent 分析结论，便于事后复盘与留痕

**5. 面向生产的安全约束**
- **命令黑名单**：`rm` / `mkfs` / `fdisk` / `iptables` / `reboot` / `halt` / `shutdown`，在工具层拦截，防止模型执行破坏性操作
- **K8s 只读模式**：`read_only_mode: true`，仅调用查询类 API，禁止变更集群资源
- **服务器白名单**：SSH 工具只允许连 `config.yaml` 中登记的受管主机，传入其他 IP 直接拒绝
- **迭代熔断**：`max_iterations: 15` 映射为 LangGraph 的 `recursion_limit`，防止模型陷入工具调用死循环
- **非 root 运行**：Dockerfile 内创建 `aiops` 普通用户启动服务
- **审计日志**：`log_config.json` 用 JSON 格式输出，`RotatingFileHandler` 落地 `logs/agent_audit.log`（10 MB × 10 份轮转）

## 技术栈

| 层次 | 选型 |
| --- | --- |
| Agent 框架 | LangGraph（`create_react_agent`）、LangChain Core |
| 大模型 | DeepSeek（经 `langchain-openai` 走 OpenAI 兼容接口，模型与地址均可切换） |
| Web 服务 | FastAPI + Uvicorn |
| 服务器运维 | Paramiko（SSH，RSA 私钥认证） |
| 集群运维 | 官方 `kubernetes` Python SDK（读取 kubeconfig） |
| 配置管理 | PyYAML + python-dotenv |
| 部署 | Docker + Docker Compose（CPU 1 核 / 内存 512 M 限额） |

## 配置说明

**`config.yaml`（业务配置）**

| 配置项 | 作用 |
| --- | --- |
| `agent.max_iterations` | Agent 最大迭代次数，防死循环 |
| `agent.timeout_seconds` | 单次 Graph 执行总超时（预留配置，当前版本未接入执行逻辑） |
| `agent.enable_human_in_loop` | 人工确认节点开关（预留配置，当前版本未接入） |
| `ssh.servers` | 受管服务器白名单（host / port / user） |
| `ssh.private_key_path` | 容器内 SSH 私钥路径 |
| `cmd_blacklist` | 高危命令黑名单 |
| `kubernetes.kubeconfig_path` | 容器内 kubeconfig 路径 |
| `kubernetes.read_only_mode` | 强制只读，禁止变更资源 |
| `webhook.listen_port` / `alert_path` | 告警接收端口与路由 |
| `report.save_dir` | 排障报告输出目录 |

**`.env`（环境变量）** —— 见 `.env.example`：`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`LLM_TEMPERATURE`、`LOG_LEVEL`。

## 部署与运行

```bash
cd aiops-agent
cp .env.example .env          # 填入真实的 LLM_API_KEY
# 准备两个凭证文件（见下方"需要自行准备"）
docker compose up -d --build
curl http://127.0.0.1:8000/health
```

接 Alertmanager 时，在 `alertmanager.yaml` 的 receiver 中加：

```yaml
receivers:
  - name: aiops-agent
    webhook_configs:
      - url: http://<agent地址>:8000/api/v1/alert/receive
```

## 安全设计说明

⚠️ **本仓库不包含任何真实凭证。** 运行前需要自行准备以下三个文件，它们都已写入 `.gitignore`，请勿提交：

| 文件 | 用途 | 获取方式 |
| --- | --- | --- |
| `.env` | 大模型 API Key | 复制 `.env.example` 并填入 |
| `kubeconfig` | 集群访问凭证（需 cluster-admin 读权限，已被只读模式限制） | 从集群 `~/.kube/config` 拷贝 |
| `ssh-keys/id_rsa` | 受管服务器的 SSH 私钥 | 自己 `ssh-keygen` 生成并把公钥下发到各节点 |

---

# 二、Kubernetes 运维实践模块

| 目录 | 内容 |
| --- | --- |
| `harbor-project/` | Harbor 私有镜像仓库部署（配置文件与安装脚本） |
| `ghost-project/` | Ghost 博客部署：hostPath / local-path 两种 PV 方案、HPA 弹性伸缩、Prometheus + Grafana + Blackbox + 钉钉告警、`ghost-control.sh` 一键控制脚本 |
| `helm-project/` | `biz-db-chart`：MySQL + Redis StatefulSet 与备份 CronJob 的 Helm Chart，含 dev / test / prod 多环境 values |
| `Loki-Fluent-Bit-Project/` | Loki + Fluent Bit 日志采集（Helm 部署） |
| `statefulSet-mysql-redis-cronJob-project/` | StatefulSet 部署 MySQL / Redis 及备份 CronJob，附启停脚本 |
| `jenkins-project/` | Jenkins 部署清单（Deployment、Service、RBAC、PV/PVC） |
| `git/` | Jenkins 流水线示例（Dockerfile、Jenkinsfile） |
| `HPA/` | metrics-server 组件与 Nginx HPA 配置 |
| `Chaos-Mesh/` | 混沌工程实验（Pod Kill、Pod Failure），含一键控制脚本 |
| `local-path-provisioner-project/` | local-path 动态存储供给与测试用 PVC/Pod |
| `ansible-web-deploy/` | Ansible 部署 Nginx 站点，含 role 结构与回滚 playbook |

各目录下均为独立的 YAML / Chart，按需 `kubectl apply -f` 或 `helm install` 即可。

---

# 仓库未包含的内容

以下几项因为体积或安全原因没有提交，需要时请自行准备：

- **Harbor 离线安装包**：`harbor-offline-installer-v1.10.1.tgz` 超过 600 MB，请从 [Harbor Releases](https://github.com/goharbor/harbor/releases) 下载后放入 `harbor-project/`
- **Helm 依赖子 Chart**：`Loki-Fluent-Bit-Project/loki-stack/charts/` 为第三方 charts，进入该目录执行 `helm dependency build` 即可拉取
- **aiops-agent 的凭证文件**：`.env`、`kubeconfig`、`ssh-keys/id_rsa`（见上文安全设计说明）

# 注意事项

仓库中出现的密码（`root123`、`Harbor12345`、`admin123` 等）均为**练习环境使用的默认值**。真实环境的凭据请勿提交；harbor 的随机 `CORE_SECRET`、钉钉机器人 `access_token` 等已在仓库中替换为占位符。
