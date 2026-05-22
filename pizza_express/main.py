"""PizzaExpress application entry point — single Tk window."""

import sys

from pizza_express.ui.app_shell import PizzaExpressApp


def main() -> None:
    app = PizzaExpressApp()
    app.mainloop()


if __name__ == "__main__":
    main()
    sys.exit(0)
