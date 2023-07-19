from gevent import GreenletExit, spawn, getcurrent, Greenlet
from functools import wraps


def shield(et=GreenletExit, suppress=False):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            g = spawn(func, *args, **kwargs)
            signal = None
            while True:
                try:
                    g.join()
                    break
                except et as e:
                    signal = e
                    continue

            if signal is not None and not suppress:
                cur = getcurrent()
                if isinstance(cur, Greenlet):
                    cur.kill(signal, block=False)

            return g.get()

        return wrapper

    return decorator
