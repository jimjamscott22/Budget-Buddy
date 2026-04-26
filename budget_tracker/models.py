from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Category:
    id: int
    name: str


@dataclass(frozen=True)
class Expense:
    id: int
    spent_on: date
    category_id: int
    category_name: str
    description: str
    amount: float
    payment_method: str


@dataclass(frozen=True)
class MonthlyBudget:
    id: int
    year: int
    month: int
    category_id: int
    category_name: str
    amount: float


@dataclass(frozen=True)
class BudgetSummary:
    category_id: int
    category_name: str
    budget_amount: float
    spent_amount: float
    remaining_amount: float
    percent_used: float | None
    is_over_budget: bool

