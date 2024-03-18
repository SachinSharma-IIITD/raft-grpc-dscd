# from threading import Timer

# def test():
#     print('Test')
#     # a = input()
#     # print(a)
#     # if a == '0':
#     #     timer.cancel()
#     # timer.run()


# timer = Timer(3, test)
# timer.start()
# # test()

import time

max_time = 2 #the time you want

while True:
    start_time = time.time()
    while (time.time() - start_time) < max_time:
        pass
    print('done')