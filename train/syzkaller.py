import os
import json
import queue
import requests
import threading
from .database import DataBase


class Trace:
    def __init__(self, state, trace, name, cover=None):
        self.state = state
        self.cover = cover

        self.trace = trace
        self.name = name


class Syzkaller:
    def __init__(self, sendQueue, getQueue, db_file):
        self.sendQueue = sendQueue
        self.getQueue = getQueue

        self.path = os.getcwd() + "/patterns.json"
        self.sendurl = "http://127.0.0.1:50000/sendProgram"
        self.geturl = "http://127.0.0.1:50000/getCover"
        self.sysurl = "http://127.0.0.1:50000/getSyscall"

        self.data = []
        self.wait = {}

        self.db = DataBase(db_file=db_file)
        self.db.create_table()
        
        self.session = requests.Session()
        self.target = self.syscall()
        self.mutex = threading.Lock()

    def syscall(self):
        try:
            target = []
            r = self.session.get(self.sysurl)
            msgs = r.json()
            if msgs:
                for item in msgs:
                    if item["Name"].find("$") == -1:
                        target.append(item)
                return target
        except Exception:
            with open("syscalls.json", "r") as f:
                return json.load(f)

    def coverage_get(self, sequence):
        trace = [self.target[i]["ID"] for i in sequence]
        cover = self.cover_to_list(self.db.getCover(trace))
        match = self.match(trace)
        return cover, match

    def cover_to_list(self, cover_str):
        cover_list = str(cover_str).replace("[", "").replace("]", "").split(", ")
        return [int(i) for i in cover_list]

    def coverage(self):
        while True:
            try:
                sequence = self.sendQueue.get()
                name = " ".join([self.target[i]["Name"] for i in sequence])
                trace = [self.target[i]["ID"] for i in sequence]
                cover = self.db.getCover(trace)
                if cover is not None:
                    self.getQueue.put(Trace(state=sequence, trace=trace, name=name, cover=self.cover_to_list(cover)))
                else:
                    self.data.clear()
                    self.db.store(name, trace)
                    if self.mutex.acquire(1):
                        self.wait.update({name: Trace(state=sequence, trace=trace, name=name,)})
                        self.mutex.release()
                    data = {"name": name, "trace": trace}
                    self.data.append(data)
                    self.session.post(self.sendurl, data=json.dumps(self.data))
            except queue.Empty:
                continue

    def collect(self):
        while True:
            r = self.session.get(self.geturl)
            if r.json():
                msgs = r.json()
                for msg in msgs:
                    self.db.setCover(msg['Trace'], msg['Coverage'])
                    if self.mutex.acquire(1):
                        trace = self.wait.get(msg['Name'])
                        if trace:
                            trace.cover = msg['Coverage']
                            self.getQueue.put(trace)
                            self.wait.pop(msg['Name'])
                    self.mutex.release()

    def close(self):
        self.db.close()

