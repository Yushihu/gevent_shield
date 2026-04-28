
from inspect import isgeneratorfunction
from functools import wraps
from typing import Callable

from gevent import GreenletExit, spawn, getcurrent, Greenlet
from gevent.event import Event


def shield(exception_type=GreenletExit, suppress=False):
    def decorator[**P, R](func: Callable[P, R]) -> Callable[P, R]:
        if isgeneratorfunction(func):
            _shield = GeneratorShield(exception_type, suppress)
            @wraps(func)
            def wrapper(*args: P.args, **kwargs: P.kwargs):
                yield from _shield.execute(func, *args, **kwargs)
        else:
            _shield = FunctionShield(exception_type, suppress)
            @wraps(func)
            def wrapper(*args: P.args, **kwargs: P.kwargs):
                return _shield.execute(func, *args, **kwargs)

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
    def execute[**P, R](self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
        exception = None

        def wrapper():
            nonlocal exception
            try:
                return func(*args, **kwargs)
            except Exception as e:
                exception = e
                return None

        g = spawn(wrapper)

        if self.suppress:
            _suppress_wait(g.join, self.exception_type)
        else:
            _wait(g.join, self.exception_type)

        if exception:
            raise exception

        return g.get()


class GeneratorShield(_Shield):
    def execute[**P, R](self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
        in_ = Event()
        out = Event()

        yielded = None
        received = None

        done = False
        exception = None
        closed = False

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
                        return

                    try:
                        yielded = generator.send(received)
                    except StopIteration as e:
                        return e.value

                    received = None
            except Exception as e:
                exception = e
                return
            finally:
                out.set()
                done = True

        if self.suppress:
            out_wait = _suppress_wait
        else:
            out_wait = _wait

        g = spawn(inner)

        while True:
            out_wait(out.wait, self.exception_type)
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


def _suppress_wait(wait_func, exec_type):
    while True:
        try:
            wait_func()
            break
        except exec_type:
            continue



def _wait(wait_func, exec_type):
    try:
        wait_func()
    except exec_type as signal:
        signals = [signal]

        while True:
            try:
                wait_func()
                break
            except exec_type as signal:
                signals.append(signal)
                continue

        cur = getcurrent()
        if isinstance(cur, Greenlet):
            for signal in signals:
                cur.kill(signal, block=False)
