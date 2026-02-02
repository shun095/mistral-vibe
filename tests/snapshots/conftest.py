import os


def pytest_configure(config):
    # Make sure nothing disables colour
    os.environ.pop("NO_COLOR", None)

    # Force colour on
    os.environ["FORCE_COLOR"] = "1"
    os.environ["PY_COLORS"] = "1"

    # Ensure a colour-capable terminal is assumed
    os.environ.setdefault("TERM", "xterm-256color")
    os.environ.setdefault("COLORTERM", "truecolor")
