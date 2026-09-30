"""Точка входа."""

from __future__ import annotations

import tkinter as tk

from pokerlab.desktop.app import ReviewApp


def main() -> None:
    root = tk.Tk()
    ReviewApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()