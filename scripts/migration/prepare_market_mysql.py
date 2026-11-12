"""Compatibility launcher for the guided Market MySQL preparation workflow."""
import os
import runpy
import sys


MINIMUM_PYTHON = (3, 8)


def main():
    if sys.version_info < MINIMUM_PYTHON:
        sys.stderr.write(
            "ERROR: this workflow requires Python 3.8 or newer; "
            "the current interpreter is {}.{}. Use the interpreter in the "
            "cPanel application's virtual environment, typically "
            "~/virtualenv/<app-name>/<version>/bin/python.\n".format(
                sys.version_info[0], sys.version_info[1]
            )
        )
        return 2

    implementation = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "prepare_market_mysql_impl.py",
    )
    runpy.run_path(implementation, run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
