"""Locates rpncalc's run_file/repl/RpnError wherever the agent put them, and records which API shape was used."""
import importlib
import inspect
import io
import pkgutil
import sys

import rpncalc

NOTES = {}


def _modules():
    yield rpncalc
    for info in pkgutil.iter_modules(rpncalc.__path__):
        try:
            yield importlib.import_module(f"rpncalc.{info.name}")
        except Exception:
            continue


def _factory(cls):
    """Returns a zero-arg constructor for cls, trying no args first, then one no-arg rpncalc class instance (e.g. Interpreter(Lexer()))."""
    try:
        cls()
        return cls
    except Exception:
        pass
    for mod in _modules():
        for dep in vars(mod).values():
            if inspect.isclass(dep) and dep.__module__.startswith("rpncalc") and dep is not cls and not issubclass(dep, BaseException):
                try:
                    dep()
                    cls(dep())
                except Exception:
                    continue
                return lambda cls=cls, dep=dep: cls(dep())
    return None


def find(name):
    for mod in _modules():
        obj = getattr(mod, name, None)
        if callable(obj):
            NOTES[name] = f"module-level in {mod.__name__}"
            return lambda: obj
    for mod in _modules():
        for cls in vars(mod).values():
            if inspect.isclass(cls) and cls.__module__ == mod.__name__ and callable(getattr(cls, name, None)):
                make = _factory(cls)
                if make is None:
                    continue
                NOTES[name] = f"method of {mod.__name__}.{cls.__name__} (not a module-level function)"
                return lambda make=make: getattr(make(), name)
    NOTES[name] = "missing"
    return None


def _rpn_error():
    for mod in _modules():
        cls = getattr(mod, "RpnError", None)
        if inspect.isclass(cls):
            return cls
    NOTES["RpnError"] = "missing"
    return type("MissingRpnError", (Exception,), {})


RpnError = _rpn_error()
_run_file = find("run_file")


def _evaluate_fallback(src):
    from rpncalc.lexer import tokenize

    forms = [("token objects", tokenize), ("split strings", str.split), ("raw string", str)]
    for name in ("evaluate", "eval_rpn", "evaluate_rpn", "eval"):
        getter = find(name)
        if getter is None:
            continue
        fn = getter()
        for form_name, make in forms:
            try:
                probe = fn(make("1 2 +"))
                probe = probe[-1] if isinstance(probe, (list, tuple)) and probe else probe
                if probe != 3:
                    continue
            except Exception:
                continue
            NOTES["run_file"] = f"missing; scored through {name}() with {form_name}"
            return fn(make(src))
    raise AssertionError("no run_file and no usable evaluate function found")


def run_source(path, src):
    if _run_file is not None:
        return _run_file()(path)
    return _evaluate_fallback(src)


def drive_repl(lines):
    getter = find("repl")
    assert getter is not None, "no repl found"
    fn = getter()
    params = list(inspect.signature(fn).parameters.values())
    feed = io.StringIO("\n".join(lines) + "\n")
    out = io.StringIO()
    real = (sys.stdin, sys.stdout)
    import builtins

    real_input = builtins.input

    def fake_input(prompt=""):
        ln = feed.readline()
        if not ln:
            raise EOFError
        return ln.rstrip("\n")

    sys.stdin, sys.stdout, builtins.input = feed, out, fake_input
    returned = None
    try:
        if not params:
            NOTES["repl_args"] = "stdin"
            returned = fn()
        elif len([p for p in params if p.default is inspect.Parameter.empty]) >= 2:
            NOTES["repl_args"] = "(input_stream, output_stream)"
            sink = io.StringIO()
            returned = fn(feed, sink)
            out.write(sink.getvalue())
        else:
            NOTES["repl_args"] = "lines iterable"
            returned = fn(list(lines))
    except EOFError:
        pass
    finally:
        sys.stdin, sys.stdout = real
        builtins.input = real_input
    return out.getvalue() + (str(returned) if returned is not None else "")
