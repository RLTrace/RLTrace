import time
import json
import math
import numpy as np
from queue import Queue
from threading import Lock
from threading import Thread
from .syzkaller import Syzkaller
from .brain import DeepQNetwork

LENGTH = 5

class Trans:
    def __init__(self, step, state, action, state_, reward=None):
        self.step = step

        self.state = state
        self.state_ = state_

        self.action = action
        self.reward = reward

        self.cover_after = None
        self.cover_before = None

        self.trace_before = None
        self.trace_after = None

        self.name_before = None
        self.name_after = None


class Env:
    def __init__(self):

        self.sendQueue = Queue()
        self.getQueue = Queue()
        self.syzkaller = Syzkaller(sendQueue=self.sendQueue,
                                   getQueue=self.getQueue,
                                   db_file="harper.db")
        self.cover = 0
        self.state = None

        self.min = 0
        self.max = len(self.syzkaller.target)

        self.n_features = LENGTH + 1
        self.n_actions = self.max
        self.cheese = 1000
        self.output = []
        self.total = 0

        self.brain = DeepQNetwork(self.n_actions, self.n_features,
                                  learning_rate=0.01,
                                  reward_decay=0.9,
                                  e_greedy=0.95,
                                  replace_target_iter=200,
                                  memory_size=40000,
                                  batch_size=64,
                                  e_greedy_increment=0.00002,
                                  e_greedy_init=0.0)

        self.steps = 0

        self.mutex = Lock()
        self.memory = []

        self.threads = []
        self.threads.append(Thread(target=self.syzkaller.coverage))
        self.threads.append(Thread(target=self.syzkaller.collect))
        self.threads.append(Thread(target=self.check))
        for t in self.threads:
            t.setDaemon(True)
            t.start()

        self.syzkaller.load()

    def reset(self):
        self.total = 0
        state = np.random.randint(self.min, self.max, size=[LENGTH], dtype=int)
        self.state = np.concatenate((state, np.array([0])), axis=0)
        return self.norm(self.state.copy())

    def norm(self, state):
        true_state = state[:LENGTH] / self.max
        pos = state[LENGTH:LENGTH+1] / LENGTH
        return np.concatenate((true_state, pos), axis=0)

    def step(self, action):
        self.steps += 1
        state = self.state.copy()
        
        pos = int(self.state[LENGTH])
        self.state[pos] = action

        self.state[LENGTH] = (pos + 1) % LENGTH

        if self.state[pos] < 0:
            self.state[pos] = 0

        if self.state[pos] >= self.max:
            self.state[pos] = self.max - 1

        state_ = self.state.copy()
        if self.mutex.acquire(1):
            self.memory.append(Trans(step=self.steps, state=state, action=action, state_=state_))
            self.mutex.release()
        self.sendQueue.put(state[:LENGTH].tolist())
        self.sendQueue.put(state_[:LENGTH].tolist())
        return self.norm(self.state.copy())

    def check(self):
        while True:
            trace = self.getQueue.get()
            if self.mutex.acquire(1):
                i = 0
                while i < len(self.memory):
                    if self.memory[i].state[:LENGTH].tolist() == trace.state:
                        self.memory[i].cover_before = trace.cover
                        self.memory[i].trace_before = trace.trace
                        self.memory[i].name_before = trace.name

                    if self.memory[i].state_[:LENGTH].tolist() == trace.state:
                        self.memory[i].cover_after = trace.cover
                        self.memory[i].trace_after = trace.trace
                        self.memory[i].name_after = trace.name

                    if self.memory[i].cover_after and self.memory[i].cover_before:
                        reward = 0
                        try:
                            for j in range(LENGTH):
                                if j >= self.memory[i].state[LENGTH]:
                                    if self.memory[i].cover_after[j] != 0 and self.memory[i].cover_before[j] != 0:
                                        reward += math.log(self.memory[i].cover_after[j] / self.memory[i].cover_before[j])
                            reward = reward / (LENGTH - self.memory[i].state[LENGTH])
                            self.total += reward
                        
                            self.brain.store_transition(self.norm(self.memory[i].state), self.memory[i].action, reward,
                                                        self.norm(self.memory[i].state_))

                            if reward >= 1:
                                self.output.append({"Trace": str(self.memory[i].trace_after),
                                                    "Name": self.memory[i].name_after,
                                                    "Cover": str(self.memory[i].cover_after)})
                                with open("output.json", "w+") as f:
                                    f.write(json.dumps(self.output, sort_keys=False, indent=4, separators=(',', ':')))
                            if reward <= -1:
                                self.output.append({"Trace": str(self.memory[i].trace_before),
                                                    "Name": self.memory[i].name_before,
                                                    "Cover": str(self.memory[i].cover_before)})
                                with open("output.json", "w+") as f:
                                    f.write(json.dumps(self.output, sort_keys=False, indent=4, separators=(',', ':')))
                            if self.total >= 10:
                                print("End_Win ", "Log_Tag:", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                                    self.memory[i].step, self.memory[i].state_.tolist(), self.memory[i].cover_after, self.memory[i].action,
                                    reward, self.total, self.memory[i].trace_before, self.memory[i].trace_after)
                                self.reset()
                                print("\n")
                            elif self.total < -5:
                                print("End_Lose ", "Log_Tag:", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                                    self.memory[i].step, self.memory[i].state_.tolist(), self.memory[i].cover_after, self.memory[i].action,
                                    reward, self.total, self.memory[i].trace_before, self.memory[i].trace_after)
                                self.reset()
                                print("\n")
                            else:
                                print("Log_Tag:", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                                    self.memory[i].step, self.memory[i].state_.tolist(), self.memory[i].cover_after, self.memory[i].action,
                                    reward, self.total, self.memory[i].trace_before, self.memory[i].trace_after)
                            self.memory.remove(self.memory[i])
                        except Exception as e:
                                print("Log_Err:", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                                    self.memory[i].step, self.memory[i].state_.tolist(), self.memory[i].cover_after, self.memory[i].action,
                                    self.total, self.memory[i].trace_before, self.memory[i].trace_after)
                    else:
                        i += 1
                self.mutex.release()

    def destroy(self):
        self.syzkaller.close()
        for thread in self.threads:
            thread.join()
