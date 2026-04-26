import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from budget_tracker.repository import BudgetRepository
from tests.helpers import make_db_path


def test_main_window_can_be_constructed():
    from PySide6.QtWidgets import QApplication

    from budget_tracker.app import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow(BudgetRepository(make_db_path()))

    assert window.windowTitle() == "Personal Budget Tracker"
    assert window.expense_table.columnCount() == 6

    window.close()
    app.quit()
