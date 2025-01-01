import os
import sys
import time
import subprocess
import psutil
import carla
import signal
import glob

def kill_carla_processes():
    """终止所有CARLA相关进程"""
    print("正在终止所有CARLA进程...")
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if 'carla' in proc.info['name'].lower():
                print(f"终止进程: {proc.info['name']} (PID: {proc.info['pid']})")
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    time.sleep(2)  # 等待进程完全终止

def clean_cache():
    """清理CARLA缓存文件"""
    print("正在清理CARLA缓存...")
    cache_paths = [
        os.path.expanduser("~/.cache/carla"),
        os.path.expanduser("~/AppData/Local/carla"),
        "G:/Simulator/WindowsNoEditor/CarlaUE4/Saved"
    ]
    
    for path in cache_paths:
        if os.path.exists(path):
            try:
                for item in glob.glob(os.path.join(path, "*")):
                    if os.path.isfile(item):
                        os.remove(item)
                    elif os.path.isdir(item):
                        os.rmdir(item)
                print(f"已清理缓存: {path}")
            except Exception as e:
                print(f"清理 {path} 时出错: {e}")

def start_carla_server():
    """启动CARLA服务器"""
    print("正在启动CARLA服务器...")
    carla_path = "G:/Simulator/WindowsNoEditor/CarlaUE4.exe"
    
    # 服务器启动参数
    params = [
        "-carla-rpc-port=2000",       # RPC端口
        "-quality-level=Epic",         # 图形质量
        "-fps=30",                     # 帧率限制
        "-windowed",                   # 窗口模式
        "-ResX=1280",                  # 窗口宽度
        "-ResY=720"                    # 窗口高度
    ]
    
    try:
        process = subprocess.Popen([carla_path] + params, 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE)
        print(f"CARLA服务器已启动，PID: {process.pid}")
        return process
    except Exception as e:
        print(f"启动CARLA服务器失败: {e}")
        return None

def wait_for_server():
    """等待服务器就绪"""
    print("等待服务器就绪...")
    max_attempts = 10
    attempt = 0
    
    while attempt < max_attempts:
        try:
            client = carla.Client('localhost', 2000)
            client.set_timeout(10.0)
            world = client.get_world()
            print("服务器已就绪！")
            return True
        except Exception as e:
            attempt += 1
            print(f"尝试连接服务器 {attempt}/{max_attempts}")
            time.sleep(2)
    
    print("服务器启动超时！")
    return False

def init_server():
    """完整的服务器初始化流程"""
    print("开始初始化CARLA服务器...")
    
    # 1. 终止现有进程
    kill_carla_processes()
    
    # 2. 清理缓存
    clean_cache()
    
    # 3. 启动服务器
    server_process = start_carla_server()
    if not server_process:
        print("服务器启动失败！")
        return False
    
    # 4. 等待服务器就绪
    if not wait_for_server():
        print("服务器初始化失败！")
        server_process.terminate()
        return False
    
    print("CARLA服务器初始化完成！")
    return True

def signal_handler(sig, frame):
    """处理Ctrl+C信号"""
    print("\n正在关闭服务器...")
    kill_carla_processes()
    sys.exit(0)

if __name__ == "__main__":
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        if init_server():
            print("服务器已准备就绪，按Ctrl+C关闭服务器")
            # 保持脚本运行
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在关闭服务器...")
        kill_carla_processes()
