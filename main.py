import subprocess
import time
import requests
import qrcode
import os
import threading

def run_api_server():
    print("啟動後端 API server...")
    subprocess.Popen(["python", "backend/api_server.py"])

def start_ngrok(port=3000):
    print("啟動 ngrok 隧道...")
    subprocess.Popen(["ngrok", "http", "5000"])
    time.sleep(3)

def get_public_url():
    for _ in range(10):
        try:
            res = requests.get("http://127.0.0.1:4040/api/tunnels")
            tunnels = res.json()["tunnels"]
            for t in tunnels:
                if t["proto"] == "https":
                    return t["public_url"]
        except:
            pass
        time.sleep(1)
    return None

def generate_qrcode(url):
    full_url = f"{url}/menu"
    os.makedirs("web/static", exist_ok=True)
    img = qrcode.make(full_url)
    img.save("web/static/qrcode.png")
    print(f"\n✅ QRCode 產生完成：{full_url}")

if __name__ == "__main__":
    print("FASTFOOD SYSTEM 自動啟動中...")
    threading.Thread(target=run_api_server).start()
    time.sleep(1)
    start_ngrok()

    url = get_public_url()
    if url:
        generate_qrcode(url)
    else:
        print("❌無法取得 ngrok 公網網址")
