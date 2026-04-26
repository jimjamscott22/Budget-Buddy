from datetime import date

from budget_tracker.budgeting import build_budget_summary
from budget_tracker.repository import BudgetRepository
from tests.helpers import make_db_path


def test_budget_summary_calculates_spent_remaining_percent_and_over_budget():
    repo = BudgetRepository(make_db_path())
    groceries = repo.get_category_by_name("Groceries")
    dining = repo.get_category_by_name("Dining")

    repo.set_monthly_budget(2026, 4, groceries.id, 100)
    repo.set_monthly_budget(2026, 4, dining.id, 50)
    repo.add_expense(date(2026, 4, 1), groceries.id, "Groceries 1", 60, "Debit")
    repo.add_expense(date(2026, 4, 2), groceries.id, "Groceries 2", 55, "Debit")
    repo.add_expense(date(2026, 4, 3), dining.id, "Coffee", 12.5, "Credit")
    repo.add_expense(date(2026, 5, 1), groceries.id, "Next month", 200, "Debit")

    summary = build_budget_summary(repo, 2026, 4)
    by_name = {item.category_name: item for item in summary}

    assert by_name["Groceries"].budget_amount == 100
    assert by_name["Groceries"].spent_amount == 115
    assert by_name["Groceries"].remaining_amount == -15
    assert by_name["Groceries"].percent_used == 115
    assert by_name["Groceries"].is_over_budget is True

    assert by_name["Dining"].budget_amount == 50
    assert by_name["Dining"].spent_amount == 12.5
    assert by_name["Dining"].remaining_amount == 37.5
    assert by_name["Dining"].percent_used == 25
    assert by_name["Dining"].is_over_budget is False


def test_budget_summary_includes_spending_without_budget():
    repo = BudgetRepository(make_db_path())
    health = repo.get_category_by_name("Health")
    repo.add_expense(date(2026, 4, 10), health.id, "Copay", 35, "Card")

    summary = build_budget_summary(repo, 2026, 4)
    item = next(row for row in summary if row.category_name == "Health")

    assert item.budget_amount == 0
    assert item.spent_amount == 35
    assert item.remaining_amount == -35
    assert item.percent_used is None
    assert item.is_over_budget is True
