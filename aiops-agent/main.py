# main.py
import os
import json
import logging
import yaml
import paramiko
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from kubernetes import client, config
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
import time
from pathlib import Path
from fastapi import BackgroundTasks

# ===================== 1、加载配置 =====================
load_dotenv()

CONFIG_PATH = "/app/config.yaml"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

# 日志配置（可选）
log_config_path = cfg.get("log_config_path")
if log_config_path and os.path.exists(log_config_path):
    import logging.config
    with open(log_config_path, "r", encoding="utf-8") as lf:
        logging.config.dictConfig(yaml.safe_load(lf))

# LLM 初始化（LangChain 兼容）
llm = ChatOpenAI(
    base_url=os.getenv("LLM_BASE_URL"),
    api_key=os.getenv("LLM_API_KEY"),
    model=os.getenv("LLM_MODEL"),
    temperature=float(os.getenv("LLM_TEMPERATURE", 0.1))
)

# K8s SDK 加载 kubeconfig
kubeconfig_path = cfg["kubernetes"]["kubeconfig_path"]
try:
    config.load_kube_config(config_file=kubeconfig_path)
    k8s_v1 = client.CoreV1Api()
    logging.info("Kubernetes 客户端初始化成功")
except Exception as e:
    logging.error(f"Kubernetes 客户端初始化失败: {e}")
    k8s_v1 = None

# 读取配置参数
AGENT_MAX_ITER = cfg["agent"]["max_iterations"]
AGENT_TIMEOUT = cfg["agent"]["timeout_seconds"]
SSH_PRIVATE_KEY_PATH = cfg["ssh"]["private_key_path"]
SSH_TIMEOUT = cfg["ssh"]["ssh_timeout"]
SERVER_LIST = cfg["ssh"]["servers"]
CMD_BLACKLIST = cfg["cmd_blacklist"]
REPORT_SAVE_DIR = cfg["report"]["save_dir"]

app = FastAPI(title="LangGraph-SRE-AIOps-Agent")

# ===================== 2、封装基础工具 @tool =====================

@tool
def get_server_basic_info(host: str) -> str:
    """
    通过SSH获取服务器基础运行信息，用于服务器故障排查
    Args:
        host: 服务器IP地址
    Returns:
        返回服务器CPU、内存、负载、磁盘、dmesg报错信息
    """
    target = next((s for s in SERVER_LIST if s["host"] == host), None)
    if not target:
        return f"错误：主机 {host} 不在托管服务器列表中"

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        private_key = paramiko.RSAKey.from_private_key_file(SSH_PRIVATE_KEY_PATH)
        ssh.connect(
            hostname=target["host"],
            port=target["port"],
            username=target["user"],
            pkey=private_key,
            timeout=SSH_TIMEOUT
        )
        commands = ["uptime", "free -h", "df -h", "dmesg -T | tail -30 | tail -10"]
        output_buf = []
        for cmd in commands:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            out = stdout.read().decode("utf-8", errors="ignore")
            err = stderr.read().decode("utf-8", errors="ignore")
            output_buf.append(f"=== command: {cmd} ===\n{out}{err}")
        return "\n".join(output_buf)
    except Exception as e:
        return f"SSH连接 {host} 失败: {str(e)}"
    finally:
        ssh.close()

@tool
def k8s_list_pod(namespace: str = "default") -> str:
    """获取Kubernetes指定命名空间下所有Pod状态信息"""
    if k8s_v1 is None:
        return "Kubernetes 客户端未初始化"
    try:
        ret = k8s_v1.list_namespaced_pod(namespace=namespace)
        result = []
        for item in ret.items:
            result.append({
                "name": item.metadata.name,
                "status": item.status.phase,
                "restart_count": sum(c.restart_count for c in item.status.container_statuses or [])
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"查询Pod失败: {str(e)}"

@tool
def k8s_get_pod_log(namespace: str, pod_name: str, tail_lines: int = 50) -> str:
    """获取Pod容器日志"""
    if k8s_v1 is None:
        return "Kubernetes 客户端未初始化"
    try:
        return k8s_v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            tail_lines=tail_lines
        )
    except Exception as e:
        return f"获取Pod日志失败: {str(e)}"

@tool
def k8s_get_events(namespace: str = "default") -> str:
    """获取K8s事件"""
    if k8s_v1 is None:
        return "Kubernetes 客户端未初始化"
    try:
        evs = k8s_v1.list_namespaced_event(namespace=namespace)
        buf = []
        for e in evs.items[-20:]:
            buf.append(f"[{e.last_timestamp}] {e.type} {e.reason}: {e.message}")
        return "\n".join(buf)
    except Exception as e:
        return f"获取k8s事件失败: {str(e)}"

tools = [get_server_basic_info, k8s_list_pod, k8s_get_pod_log, k8s_get_events]

# ===================== 3、Web接口 =====================
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/api/v1/alert/receive")
async def alert_receive(request: Request, background_tasks: BackgroundTasks):
    alert_payload = await request.json()
    # 后台执行排障逻辑，HTTP立刻返回，不会阻塞Alertmanager
    background_tasks.add_task(run_agent_by_alert, alert_payload)
    return {"code":0,"msg":"accepted,agent running in background"}

# 创建ReAct Agent
agent_graph = create_react_agent(
    model=llm,
    tools=tools,
)

def run_agent_by_alert(alert_data: dict):
    """根据告警信息调用Agent执行排障，返回结果与报告路径"""
    alerts = alert_data.get("alerts", [])
    prompt = f"""你是一名SRE运维工程师，收到Prometheus告警：
告警原始数据：{alerts}
请调用可用工具完成故障排查：
1. 如果告警携带instance服务器IP，调用get_server_basic_info采集服务器信息
2. 如果是k8s相关告警，调用k8s_list_pod、k8s_get_pod_log、k8s_get_events排查集群问题
输出内容包含：现象分析、可能根因、处理建议。
"""
    inputs = {"messages": [("user", prompt)]}
    config = {"recursion_limit": AGENT_MAX_ITER}
    result = agent_graph.invoke(inputs, config=config)

    # 获取Agent最终回答
    final_msg = result["messages"][-1].content

    # 生成markdown报告保存
    ts = int(time.time())
    report_filename = f"alert_report_{ts}.md"
    report_path = Path(REPORT_SAVE_DIR) / report_filename
    md_content = (
            "# AIOps 告警排障报告\n"
            f"生成时间: {time.ctime()}\n"
            "## 原始告警\n"
            "```json\n"
            f"{json.dumps(alerts,ensure_ascii=False,indent=2)}\n"
            "```\n"
            "## Agent排障分析\n"
            f"{final_msg}\n"
)
    with open(report_path,"w",encoding="utf-8") as f:
        f.write(md_content)
    return {
        "report_file": str(report_path),
        "analysis": final_msg
    }
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
