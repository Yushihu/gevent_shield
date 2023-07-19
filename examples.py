from gevent import sleep, spawn, spawn_later

from shield import shield


@shield()
def work():
    for _ in range(3):
        print('programing...')
        sleep(1)


@shield()
def exercise():
    for _ in range(3):
        print('push-up')
        sleep(1)


def date():
    sleep(3)
    print("Wait... I don't have a girlfriend...")


def daily_life():
    work()
    exercise()
    date()


g1 = spawn(daily_life)
g2 = spawn_later(2, g1.kill)
g1.join()
g2.join()

# print out will be:
##############################################
# programing...
# programing...
# programing...  (kill happens, but postponed)
# push-up
# push-up
# push-up  (date won't happen, because it's not shielded)
##############################################
