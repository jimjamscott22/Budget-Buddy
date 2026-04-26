from __future__ import annotations

from .models import BudgetSummary
from .repository import BudgetRepository


def build_budget_summary(repo: BudgetRepository, year: int, month: int) -> list[BudgetSummary]:
    categories = repo.list_categories()
    budgets = {budget.category_id: budget.amount for budget in repo.list_monthly_budgets(year, month)}
    spending = repo.spending_by_category(year, month)
    category_ids = {category.id for category in categories} | set(budgets) | set(spending)
    categories_by_id = {category.id: category.name for category in categories}

    rows: list[BudgetSummary] = []
    for category_id in sorted(category_ids, key=lambda item: categories_by_id.get(item, "")):
        category_name = categories_by_id.get(category_id, "Unknown")
        budget_amount = round(float(budgets.get(category_id, 0)), 2)
        spent_amount = round(float(spending.get(category_id, 0)), 2)
        remaining_amount = round(budget_amount - spent_amount, 2)
        percent_used = None if budget_amount == 0 else round((spent_amount / budget_amount) * 100, 2)
        rows.append(
            BudgetSummary(
                category_id=category_id,
                category_name=category_name,
                budget_amount=budget_amount,
                spent_amount=spent_amount,
                remaining_amount=remaining_amount,
                percent_used=percent_used,
                is_over_budget=spent_amount > budget_amount,
            )
        )
    return rows

