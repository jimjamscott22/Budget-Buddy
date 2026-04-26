from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .budgeting import build_budget_summary
from .models import Category, Expense
from .repository import BudgetRepository


class ExpenseDialog(QDialog):
    def __init__(
        self,
        categories: list[Category],
        expense: Expense | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Edit Expense" if expense else "Add Expense")
        self.categories = categories

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())

        self.category_combo = QComboBox()
        for category in categories:
            self.category_combo.addItem(category.name, category.id)

        self.description_edit = QLineEdit()
        self.amount_edit = QDoubleSpinBox()
        self.amount_edit.setRange(0.01, 1_000_000)
        self.amount_edit.setDecimals(2)
        self.amount_edit.setPrefix("$")
        self.amount_edit.setSingleStep(5)

        self.payment_edit = QLineEdit()
        self.payment_edit.setPlaceholderText("Cash, Debit, Credit...")

        if expense:
            self.date_edit.setDate(QDate(expense.spent_on.year, expense.spent_on.month, expense.spent_on.day))
            index = self.category_combo.findData(expense.category_id)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)
            self.description_edit.setText(expense.description)
            self.amount_edit.setValue(expense.amount)
            self.payment_edit.setText(expense.payment_method)

        form = QFormLayout()
        form.addRow("Date", self.date_edit)
        form.addRow("Category", self.category_combo)
        form.addRow("Description", self.description_edit)
        form.addRow("Amount", self.amount_edit)
        form.addRow("Payment method", self.payment_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> dict[str, object]:
        selected_date = self.date_edit.date()
        return {
            "spent_on": date(selected_date.year(), selected_date.month(), selected_date.day()),
            "category_id": int(self.category_combo.currentData()),
            "description": self.description_edit.text(),
            "amount": float(self.amount_edit.value()),
            "payment_method": self.payment_edit.text(),
        }


class BudgetDialog(QDialog):
    def __init__(
        self,
        categories: list[Category],
        year: int,
        month: int,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Set Monthly Budget")

        self.year_edit = QSpinBox()
        self.year_edit.setRange(2000, 2100)
        self.year_edit.setValue(year)

        self.month_edit = QSpinBox()
        self.month_edit.setRange(1, 12)
        self.month_edit.setValue(month)

        self.category_combo = QComboBox()
        for category in categories:
            self.category_combo.addItem(category.name, category.id)

        self.amount_edit = QDoubleSpinBox()
        self.amount_edit.setRange(0, 1_000_000)
        self.amount_edit.setDecimals(2)
        self.amount_edit.setPrefix("$")
        self.amount_edit.setSingleStep(25)

        form = QFormLayout()
        form.addRow("Year", self.year_edit)
        form.addRow("Month", self.month_edit)
        form.addRow("Category", self.category_combo)
        form.addRow("Budget", self.amount_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> dict[str, object]:
        return {
            "year": int(self.year_edit.value()),
            "month": int(self.month_edit.value()),
            "category_id": int(self.category_combo.currentData()),
            "amount": float(self.amount_edit.value()),
        }


class SpendingChart(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.figure = Figure(figsize=(6, 3), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

    def update_chart(self, rows) -> None:
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        chart_rows = [row for row in rows if row.spent_amount > 0]
        if not chart_rows:
            axis.text(0.5, 0.5, "No spending for this month", ha="center", va="center")
            axis.set_axis_off()
        else:
            names = [row.category_name for row in chart_rows]
            values = [row.spent_amount for row in chart_rows]
            colors = ["#D64545" if row.is_over_budget else "#2F7D5A" for row in chart_rows]
            axis.bar(names, values, color=colors)
            axis.set_title("Monthly Spending by Category")
            axis.set_ylabel("Spent ($)")
            axis.tick_params(axis="x", rotation=35)
            axis.grid(axis="y", alpha=0.2)
        self.canvas.draw_idle()


class MainWindow(QMainWindow):
    def __init__(self, repo: BudgetRepository):
        super().__init__()
        self.repo = repo
        self.categories: list[Category] = []
        self.expense_ids: list[int] = []

        self.setWindowTitle("Personal Budget Tracker")
        self.resize(1180, 760)
        self._build_actions()
        self._build_ui()
        self.refresh_all()

    def _build_actions(self) -> None:
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.refresh_all)
        self.toolbar = self.addToolBar("Main")
        self.toolbar.addAction(refresh_action)

    def _build_ui(self) -> None:
        today = QDate.currentDate()
        self.year_filter = QSpinBox()
        self.year_filter.setRange(2000, 2100)
        self.year_filter.setValue(today.year())
        self.year_filter.valueChanged.connect(self.refresh_all)

        self.month_filter = QSpinBox()
        self.month_filter.setRange(1, 12)
        self.month_filter.setValue(today.month())
        self.month_filter.valueChanged.connect(self.refresh_all)

        self.category_filter = QComboBox()
        self.category_filter.currentIndexChanged.connect(self.refresh_expenses)

        self.add_button = QPushButton("Add Expense")
        self.add_button.clicked.connect(self.add_expense)
        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self.edit_selected_expense)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_selected_expense)
        self.budget_button = QPushButton("Set Budget")
        self.budget_button.clicked.connect(self.set_budget)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Year"))
        filters.addWidget(self.year_filter)
        filters.addWidget(QLabel("Month"))
        filters.addWidget(self.month_filter)
        filters.addWidget(QLabel("Category"))
        filters.addWidget(self.category_filter, 1)
        filters.addWidget(self.add_button)
        filters.addWidget(self.edit_button)
        filters.addWidget(self.delete_button)
        filters.addWidget(self.budget_button)

        self.expense_table = QTableWidget(0, 6)
        self.expense_table.setHorizontalHeaderLabels(
            ["Date", "Category", "Description", "Amount", "Payment", "ID"]
        )
        self.expense_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.expense_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.expense_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.expense_table.setColumnHidden(5, True)
        self.expense_table.doubleClicked.connect(self.edit_selected_expense)

        expense_group = QGroupBox("Expenses")
        expense_layout = QVBoxLayout(expense_group)
        expense_layout.addLayout(filters)
        expense_layout.addWidget(self.expense_table)

        self.budget_table = QTableWidget(0, 5)
        self.budget_table.setHorizontalHeaderLabels(["Category", "Budget", "Spent", "Remaining", "Used"])
        self.budget_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.budget_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        self.chart = SpendingChart()
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("Budget Overview"))
        right_layout.addWidget(self.budget_table, 2)
        right_layout.addWidget(self.chart, 3)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(expense_group)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        root = QWidget()
        layout = QGridLayout(root)
        layout.addWidget(splitter, 0, 0)
        self.setCentralWidget(root)

    def refresh_all(self) -> None:
        self.refresh_categories()
        self.refresh_expenses()
        self.refresh_budget_overview()

    def refresh_categories(self) -> None:
        current_id = self.category_filter.currentData()
        self.categories = self.repo.list_categories()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("All categories", None)
        for category in self.categories:
            self.category_filter.addItem(category.name, category.id)
        index = self.category_filter.findData(current_id)
        self.category_filter.setCurrentIndex(index if index >= 0 else 0)
        self.category_filter.blockSignals(False)

    def refresh_expenses(self) -> None:
        year = int(self.year_filter.value())
        month = int(self.month_filter.value())
        category_id = self.category_filter.currentData()
        expenses = self.repo.list_expenses(year=year, month=month, category_id=category_id)
        self.expense_ids = [expense.id for expense in expenses]
        self.expense_table.setRowCount(len(expenses))
        for row, expense in enumerate(expenses):
            values = [
                expense.spent_on.isoformat(),
                expense.category_name,
                expense.description,
                f"${expense.amount:,.2f}",
                expense.payment_method,
                str(expense.id),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.expense_table.setItem(row, column, item)

    def refresh_budget_overview(self) -> None:
        summary = build_budget_summary(self.repo, int(self.year_filter.value()), int(self.month_filter.value()))
        self.budget_table.setRowCount(len(summary))
        for row_index, row in enumerate(summary):
            values = [
                row.category_name,
                f"${row.budget_amount:,.2f}",
                f"${row.spent_amount:,.2f}",
                f"${row.remaining_amount:,.2f}",
                "No budget" if row.percent_used is None else f"{row.percent_used:.0f}%",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column > 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if row.is_over_budget:
                    item.setBackground(Qt.GlobalColor.red)
                    item.setForeground(Qt.GlobalColor.white)
                self.budget_table.setItem(row_index, column, item)
        self.chart.update_chart(summary)

    def add_expense(self) -> None:
        dialog = ExpenseDialog(self.categories, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.repo.add_expense(**dialog.values())
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid expense", str(exc))
                return
            self.refresh_all()

    def edit_selected_expense(self) -> None:
        expense_id = self.selected_expense_id()
        if expense_id is None:
            QMessageBox.information(self, "Edit expense", "Select an expense first.")
            return
        expense = self.repo.get_expense(expense_id)
        dialog = ExpenseDialog(self.categories, expense=expense, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.repo.update_expense(expense_id=expense_id, **dialog.values())
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid expense", str(exc))
                return
            self.refresh_all()

    def delete_selected_expense(self) -> None:
        expense_id = self.selected_expense_id()
        if expense_id is None:
            QMessageBox.information(self, "Delete expense", "Select an expense first.")
            return
        response = QMessageBox.question(
            self,
            "Delete expense",
            "Delete the selected expense?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if response == QMessageBox.StandardButton.Yes:
            self.repo.delete_expense(expense_id)
            self.refresh_all()

    def set_budget(self) -> None:
        dialog = BudgetDialog(
            self.categories,
            int(self.year_filter.value()),
            int(self.month_filter.value()),
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.repo.set_monthly_budget(**dialog.values())
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid budget", str(exc))
                return
            self.refresh_budget_overview()

    def selected_expense_id(self) -> int | None:
        selected_rows = self.expense_table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        row = selected_rows[0].row()
        item = self.expense_table.item(row, 5)
        return int(item.text()) if item else None


def default_database_path() -> Path:
    return Path.cwd() / "data" / "budget_tracker.db"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Personal Budget Tracker")
    window = MainWindow(BudgetRepository(default_database_path()))
    window.show()
    return app.exec()

