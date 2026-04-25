
from inspect import isgeneratorfunction
from functools import wraps
from typing import Callable

from gevent import GreenletExit, spawn, getcurrent, Greenlet
from gevent.event import Event


def shield(exception_type=GreenletExit, suppress=False):
    def decorator(func: Callable[...]) -> Callable[...]:
        if isgeneratorfunction(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                yield from GeneratorShield(exception_type, suppress).execute(func, *args, **kwargs)
        else:
            @wraps(func)
            def wrapper(*args, **kwargs):
                return FunctionShield(exception_type, suppress).execute(func, *args, **kwargs)
            
        return wrapper

    return decorator


def shielding(exception_type=GreenletExit, suppress=False):
    def d(func):
        return FunctionShield(exception_type, suppress).execute(func)
    return d


class _Shield:
    def __init__(self, exception_type=GreenletExit, suppress=False):
        self.exception_type = exception_type
        self.suppress = suppress

    def execute(self, func, *args, **kwargs):
        raise NotImplementedError


class FunctionShield(_Shield):
    def execute(self, func, *args, **kwargs):
        reraise = not self.suppress
        
        exception = None

        def wrapper():
            nonlocal exception
            try:
                return func(*args, **kwargs)
            except Exception as e:
                exception = e
                return

        g = spawn(wrapper)

        try:
            g.join()
        except self.exception_type as e:
            if reraise:
                signals = []
                while True:
                    try:
                        g.join()
                        break
                    except self.exception_type as e:
                        signals.append(e)
                        continue

                cur = getcurrent()
                if isinstance(cur, Greenlet):
                    for signal in signals:
                        cur.kill(signal, block=False)
            else:
                while True:
                    try:
                        g.join()
                        break
                    except self.exception_type as e:
                        continue

        if exception:
            raise exception

        return g.get()


class GeneratorShield(_Shield):
    def execute(self, func, *args, **kwargs):
        in_ = Event()
        out = Event()

        yielded = None
        received = None

        done = False
        exception = None
        closed = False

        reraise = not self.suppress

        def inner():
            nonlocal yielded, received, done, exception, closed
            generator = func(*args, **kwargs)

            try:
                try:
                    yielded = next(generator)
                except StopIteration:
                    return

                while True:
                    out.set()
                    in_.wait()
                    in_.clear()
                    if closed:
                        generator.close()
                        break

                    try:
                        yielded = generator.send(received)
                    except StopIteration:
                        break

                    received = None
            except Exception as e:
                exception = e
                return
            finally:
                out.set()
                done = True

        g = spawn(inner)

        while True:
            try:
                out.wait()
            except self.exception_type as e:
                if reraise:
                    signals = [e]

                    while True:
                        try:
                            out.wait()
                            break
                        except self.exception_type as e:
                            signals.append(e)
                            continue

                    cur = getcurrent()
                    if isinstance(cur, Greenlet):
                        for signal in signals:
                            cur.kill(signal, block=False)

                else:
                    while True:
                        try:
                            out.wait()
                            break
                        except self.exception_type as e:
                            continue

            out.clear()
            if done:
                break

            try:
                received = yield yielded
            except GeneratorExit:
                closed = True
            in_.set()

        if exception:
            raise exception

        g.get()
