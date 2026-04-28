from gevent import GreenletExit, sleep, spawn

from shield import shield


def titled(func):
    def wrapper(*args, **kwargs):
        print(f"=== {func.__name__} ===")
        return func(*args, **kwargs)
    return wrapper


@titled
def test1():
    count = 0

    def inc():
        nonlocal count
        count += 1
        print(f"inc: {count}")

    @shield()
    def shield_inc():
        nonlocal count
        print("enter shield")
        sleep(0.2)
        inc()
        print("exit shield")


    def main():
        nonlocal count
        print(f"enter main: {count}")
        shield_inc()
        try:
            sleep(0)
            inc()
        except GreenletExit:
            print("killed in main")
            raise
        finally:
            print(f"finally in main: {count}")


    def kill(g):
        sleep(0.1)
        print("kill")
        g.kill()

    g = spawn(main)
    spawn(kill, g)
    spawn(kill, g)
    g.join()

    print(count)

    assert count == 1


@titled
def test2():
    class MyExit(GreenletExit):
        pass

    count = 0

    def inc():
        nonlocal count
        count += 1
        print(f"inc: {count}")

    @shield(exception_type=MyExit, suppress=True)
    def shield_inc():
        nonlocal count
        print("enter shield")
        sleep(0.2)
        inc()
        print("exit shield")


    def main():
        nonlocal count
        print(f"enter main: {count}")
        shield_inc()
        try:
            sleep(0)
            inc()
        except GreenletExit:
            print("killed in main")
            raise
        finally:
            print(f"finally in main: {count}")


    def kill(g):
        sleep(0.1)
        print("kill")
        g.kill(MyExit())

    g = spawn(main)
    spawn(kill, g)
    g.join()

    print(count)

    assert count == 2


@titled
def test3():
    class TheError(Exception):
        pass

    @shield()
    def f():
        e = TheError("test")
        print(f"raise error {e}")
        raise e

    try:
        f()
        assert False, "should raise"
    except TheError as e:
        print(f"caught error: {e}")


@titled
def test4():
    @shield()
    def create_str(ret):
        print(f"creating string: {ret}")
        return ret
    
    expected = "hello"
    s = create_str(expected)
    print(f"created string: {s}")
    assert s == expected


@titled
def test5():
    count = 0

    @shield()
    def shield_func(i):
        try:
            while True:
                print(f"enter shield: {i}")
                i += 1
                sleep(0.1)
                print(f"exit shield: {i}")
                i = yield i
                print(f"received in shield: {i}")
        finally:
            print(f"finally in shield: {i}")

    def main():
        nonlocal count
        g = shield_func(count)
        i = next(g)
        while True:
            print(f"main received: {i}")
            count = i
            try:
                i = g.send(i + 1)
                sleep(0.1)
            except StopIteration:
                print("shield_func done")
                break

    def kill(gx):
        sleep(0.35)
        print("kill")
        gx.kill()
    
    g = spawn(main)
    spawn(kill, g)
    g.join()

    assert count == 3


if __name__ == "__main__":
    test1()
    test2()
    test3()
    test4()
    test5()