import time
import random


class CountDownTimer:
    def __init__(self, MAX_T, type=['random', 'fixed']):
        self.max_t = MAX_T
        self.type = type
        self.Timer = 0

    def countDown(self, timeout=None):
        self.restart_timer(timeout)

        while self.Timer > 0:
            print(self.Timer)
            time.sleep(1)
            self.Timer -= 1
        return 0

    def restart_timer(self, timeout=None):
        if timeout:
            self.Timer = timeout
        elif self.type == 'fixed':
            self.Timer = self.max_t
        elif self.type == 'random':
            self.Timer = random.randint(max(self.Timer, self.max_t//2), self.max_t)
