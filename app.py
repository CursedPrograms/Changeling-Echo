"""Changeling Echo: train the voices the Changelings speak with (RVC, through Applio).

    python app.py      the window
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    from window import Window
    Window().run()


if __name__ == "__main__":
    main()
