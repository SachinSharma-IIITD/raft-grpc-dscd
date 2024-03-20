import time
import random

class countDownTimer :
    def __init__(self):
        self.Timer = 0 
    def countDown(self,T):
        self.Timer = T
        while self.Timer > 0:
            print(self.Timer)
            time.sleep(1)
            self.Timer -= 1
        return 0
    def UpdateTimeout(self):
        self.Timer = random.randint(self.Timer, 15)

