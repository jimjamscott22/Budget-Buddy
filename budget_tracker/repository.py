from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from .models import Category, Expense, MonthlyBudget


DEFAULT_CATEGORIES = (
    "Groceries",
    "Dining",
    "Rent",
    "Utilities",
    "Transportation",
    "Entertainment",
    "Health",
    "Shopping",
    "Other",
)


class BudgetRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spent_on TEXT NOT NULL,
                    category_id INTEGER NOT NULL REFERENCES categories(id),
                    description TEXT NOT NULL DEFAULT '',
                    amount REAL NOT NULL CHECK(amount > 0),
                    payment_method TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS monthly_budgets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year INTEGER NOT NULL,
                    month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
                    category_id INTEGER NOT NULL REFERENCES categories(id),
                    amount REAL NOT NULL CHECK(amount >= 0),
                    UNIQUE(year, month, category_id)
                );
                """
            )
            conn.executemany(
                "INSERT OR IGNORE INTO categories(name) VALUES (?)",
                [(name,) for name in DEFAULT_CATEGORIES],
            )

    def list_categories(self) -> list[Category]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
        return [Category(id=row["id"], name=row["name"]) for row in rows]

    def add_category(self, name: str) -> int:
        name = name.strip()
        if not name:
            raise ValueError("category name is required")
        with self._connect() as conn:
            cursor = conn.execute("INSERT INTO categories(name) VALUES (?)", (name,))
            return int(cursor.lastrowid)

    def get_category_by_name(self, name: str) -> Category:
        with self._connect() as conn:
            row = conn.execute("SELECT id, name FROM categories WHERE name = ?", (name,)).fetchone()
        if row is None:
            raise ValueError(f"unknown category: {name}")
        return Category(id=row["id"], name=row["name"])

    def delete_category(self, category_id: int) -> None:
        with self._connect() as conn:
            used = conn.execute(
                "SELECT 1 FROM expenses WHERE category_id = ? LIMIT 1",
                (category_id,),
            ).fetchone()
            if used:
                raise ValueError("category is in use by existing expenses")
            conn.execute("DELETE FROM monthly_budgets WHERE category_id = ?", (category_id,))
            conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))

    def add_expense(
        self,
        spent_on: date,
        category_id: int,
        description: str,
        amount: float,
        payment_method: str,
    ) -> int:
        self._validate_expense(spent_on, category_id, amount)
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO expenses(spent_on, category_id, description, amount, payment_method)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    spent_on.isoformat(),
                    category_id,
                    description.strip(),
                    float(amount),
                    payment_method.strip(),
                ),
            )
            return int(cursor.lastrowid)

    def update_expense(
        self,
        expense_id: int,
        spent_on: date,
        category_id: int,
        description: str,
        amount: float,
        payment_method: str,
    ) -> None:
        self._validate_expense(spent_on, category_id, amount)
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE expenses
                SET spent_on = ?, category_id = ?, description = ?, amount = ?, payment_method = ?
                WHERE id = ?
                """,
                (
                    spent_on.isoformat(),
                    category_id,
                    description.strip(),
                    float(amount),
                    payment_method.strip(),
                    expense_id,
                ),
            )
            if cursor.rowcount == 0:
                raise ValueError("expense not found")

    def delete_expense(self, expense_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))

    def get_expense(self, expense_id: int) -> Expense:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT e.id, e.spent_on, e.category_id, c.name AS category_name,
                       e.description, e.amount, e.payment_method
                FROM expenses e
                JOIN categories c ON c.id = e.category_id
                WHERE e.id = ?
                """,
                (expense_id,),
            ).fetchone()
        if row is None:
            raise ValueError("expense not found")
        return self._expense_from_row(row)

    def list_expenses(
        self,
        *,
        year: int | None = None,
        month: int | None = None,
        category_id: int | None = None,
    ) -> list[Expense]:
        conditions: list[str] = []
        params: list[object] = []
        if year is not None and month is not None:
            conditions.append("strftime('%Y-%m', e.spent_on) = ?")
            params.append(f"{year:04d}-{month:02d}")
        elif year is not None:
            conditions.append("strftime('%Y', e.spent_on) = ?")
            params.append(f"{year:04d}")
        if category_id is not None:
            conditions.append("e.category_id = ?")
            params.append(category_id)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT e.id, e.spent_on, e.category_id, c.name AS category_name,
                   e.description, e.amount, e.payment_method
            FROM expenses e
            JOIN categories c ON c.id = e.category_id
            {where}
            ORDER BY e.spent_on DESC, e.id DESC
        """
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._expense_from_row(row) for row in rows]

    def set_monthly_budget(self, year: int, month: int, category_id: int, amount: float) -> None:
        self._validate_month(year, month)
        if amount < 0:
            raise ValueError("budget amount must be zero or greater")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO monthly_budgets(year, month, category_id, amount)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(year, month, category_id)
                DO UPDATE SET amount = excluded.amount
                """,
                (year, month, category_id, float(amount)),
            )

    def list_monthly_budgets(self, year: int, month: int) -> list[MonthlyBudget]:
        self._validate_month(year, month)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT b.id, b.year, b.month, b.category_id, c.name AS category_name, b.amount
                FROM monthly_budgets b
                JOIN categories c ON c.id = b.category_id
                WHERE b.year = ? AND b.month = ?
                ORDER BY c.name
                """,
                (year, month),
            ).fetchall()
        return [
            MonthlyBudget(
                id=row["id"],
                year=row["year"],
                month=row["month"],
                category_id=row["category_id"],
                category_name=row["category_name"],
                amount=float(row["amount"]),
            )
            for row in rows
        ]

    def spending_by_category(self, year: int, month: int) -> dict[int, float]:
        self._validate_month(year, month)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT category_id, SUM(amount) AS total
                FROM expenses
                WHERE strftime('%Y-%m', spent_on) = ?
                GROUP BY category_id
                """,
                (f"{year:04d}-{month:02d}",),
            ).fetchall()
        return {row["category_id"]: float(row["total"] or 0) for row in rows}

    def _validate_expense(self, spent_on: date, category_id: int, amount: float) -> None:
        if not isinstance(spent_on, date):
            raise ValueError("expense date is required")
        if not category_id:
            raise ValueError("category is required")
        if amount <= 0:
            raise ValueError("expense amount must be positive")

    def _validate_month(self, year: int, month: int) -> None:
        if year < 1900:
            raise ValueError("year must be valid")
        if month < 1 or month > 12:
            raise ValueError("month must be between 1 and 12")

    def _expense_from_row(self, row: sqlite3.Row) -> Expense:
        return Expense(
            id=row["id"],
            spent_on=date.fromisoformat(row["spent_on"]),
            category_id=row["category_id"],
            category_name=row["category_name"],
            description=row["description"],
            amount=float(row["amount"]),
            payment_method=row["payment_method"],
        )

