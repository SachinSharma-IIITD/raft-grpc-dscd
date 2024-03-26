import time
import random


class CountDownTimer:
    def __init__(self, MAX_T, type=['random', 'fixed']):
        self.max_t = MAX_T
        self.type = type
        self.Timer = 0

    def countDown(self):
        self.restart_timer()
        
        while self.Timer > 0:
            print(self.Timer)
            time.sleep(1)
            self.Timer -= 1
        return 0

    def restart_timer(self):
        if self.type == 'fixed':
            self.Timer = self.max_t
        elif self.type == 'random':
            self.Timer = random.randint(self.Timer, self.max_t)
