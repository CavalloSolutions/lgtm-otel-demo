import random
import requests
import time
import os
import threading

URL = os.environ.get("DEMO_SERVICE_URL", "http://localhost:5228/otel-demo")
WORKER_COUNT = int(os.environ.get("WORKER_COUNT", "2"))

class LoadGenThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    
    def run(self) -> None:
        send_requests()

def send_requests():
    while True: 
        requests.get(URL)
        time.sleep(random.random())

for i in range(WORKER_COUNT):
    LoadGenThread().run()