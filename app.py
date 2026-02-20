from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except Exception as exc:  # pragma: no cover - startup guard
        print("PySide6 is required. Install dependencies with: pip install -r requirements.txt")
        print(f"Import error: {exc}")
        return 1

    from gui.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
