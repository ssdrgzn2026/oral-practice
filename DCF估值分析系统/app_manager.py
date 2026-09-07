# -*- coding: utf-8 -*-
"""
Streamlit 应用统一管理器
一台服务器上部署多个 Streamlit 应用，自动分配端口、一键启停
"""
import os
import sys
import subprocess
import socket
import json
import time

# ========== 应用配置表 ==========
# 每个应用：名称、路径、固定端口（None 则自动找空闲端口）
APPS = {
    "dcf": {
        "name": "DCF估值分析系统",
        "path": r"C:\Users\Administrator\LZQ\DCF\streamlit_app.py",
        "port": 8515,
    },
    # 以后加新系统，直接在这里添加：
    # "formula": {
    #     "name": "公式转换系统",
    #     "path": r"C:\Users\Administrator\LZQ\公式转换系统\streamlit_app.py",
    #     "port": 8516,
    # },
}

PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".app_pids.json")


def find_free_port(start=8513, end=8525):
    """找一个空闲端口"""
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
    return None


def load_pids():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_pids(pids):
    with open(PID_FILE, 'w', encoding='utf-8') as f:
        json.dump(pids, f, indent=2)


def is_port_listening(port):
    """检查端口是否已被监听"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('0.0.0.0', port)) == 0


def start_app(app_key):
    """启动单个应用"""
    app = APPS.get(app_key)
    if not app:
        print(f"错误：未找到应用 '{app_key}'")
        return False

    pids = load_pids()
    
    # 如果已经在运行，先提示
    if app_key in pids:
        if is_port_listening(app["port"]):
            print(f"[{app['name']}] 已经在运行，端口 {app['port']}")
            return True
        else:
            # PID 残留，清理
            del pids[app_key]

    port = app["port"]
    if port is None:
        port = find_free_port()
        if port is None:
            print(f"[{app['name']}] 错误：找不到空闲端口")
            return False

    # 检查端口是否被占用
    if is_port_listening(port):
        print(f"[{app['name']}] 错误：端口 {port} 已被占用")
        return False

    cmd = [
        sys.executable, '-m', 'streamlit', 'run', app['path'],
        f'--server.port={port}',
        '--server.headless=true',
        '--server.address=0.0.0.0',
    ]

    print(f"[{app['name']}] 正在启动，端口 {port}...")
    
    # 使用 CREATE_NEW_PROCESS_GROUP 确保子进程独立
    if sys.platform == 'win32':
        proc = subprocess.Popen(
            cmd,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    time.sleep(3)
    
    if is_port_listening(port):
        pids[app_key] = proc.pid
        save_pids(pids)
        print(f"[{app['name']}] ✅ 启动成功！访问地址：")
        print(f"    http://localhost:{port}")
        print(f"    http://<服务器IP>:{port}")
        return True
    else:
        print(f"[{app['name']}] ❌ 启动失败，请检查代码是否有错误")
        return False


def stop_app(app_key):
    """停止单个应用"""
    app = APPS.get(app_key)
    if not app:
        print(f"错误：未找到应用 '{app_key}'")
        return

    pids = load_pids()
    if app_key not in pids:
        print(f"[{app['name']}] 当前未运行")
        return

    pid = pids[app_key]
    try:
        if sys.platform == 'win32':
            subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True)
        else:
            os.kill(pid, 9)
        print(f"[{app['name']}] ✅ 已停止")
    except Exception as e:
        print(f"[{app['name']}] 停止时出错: {e}")
    
    if app_key in pids:
        del pids[app_key]
        save_pids(pids)


def stop_all():
    """停止所有应用"""
    pids = load_pids()
    for app_key in list(pids.keys()):
        stop_app(app_key)
    print("所有应用已停止")


def start_all():
    """启动所有应用"""
    for app_key in APPS:
        start_app(app_key)
        time.sleep(2)


def status():
    """查看所有应用状态"""
    print("\n" + "=" * 50)
    print("Streamlit 应用状态")
    print("=" * 50)
    for app_key, app in APPS.items():
        port = app["port"] or "自动"
        running = is_port_listening(app["port"]) if app["port"] else False
        status_str = "🟢 运行中" if running else "🔴 已停止"
        print(f"  [{app_key}] {app['name']}")
        print(f"    端口: {port}  |  状态: {status_str}")
        if running and app["port"]:
            print(f"    地址: http://<服务器IP>:{app['port']}")
    print("=" * 50 + "\n")


def show_help():
    print("""
用法: python app_manager.py <命令> [应用名]

命令:
  start   [app_key]   启动指定应用（如 dcf）
  stop    [app_key]   停止指定应用
  restart [app_key]   重启指定应用
  startall            启动所有应用
  stopall             停止所有应用
  status              查看所有应用状态

示例:
  python app_manager.py start dcf
  python app_manager.py stop dcf
  python app_manager.py status
""")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        show_help()
        sys.exit(0)

    cmd = sys.argv[1].lower()
    app_key = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == 'start':
        if app_key:
            start_app(app_key)
        else:
            print("请指定应用名，如: python app_manager.py start dcf")
    elif cmd == 'stop':
        if app_key:
            stop_app(app_key)
        else:
            print("请指定应用名，如: python app_manager.py stop dcf")
    elif cmd == 'restart':
        if app_key:
            stop_app(app_key)
            time.sleep(1)
            start_app(app_key)
        else:
            print("请指定应用名")
    elif cmd == 'startall':
        start_all()
    elif cmd == 'stopall':
        stop_all()
    elif cmd == 'status':
        status()
    else:
        show_help()
