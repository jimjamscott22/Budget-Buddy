from datetime import date

import pytest

from budget_tracker.repository import BudgetRepository
from tests.helpers import make_db_path


def test_seeds_default_categories_in_new_database():
    repo = BudgetRepository(make_db_path())

    categories = repo.list_categories()

    names = [category.name for category in categories]
    assert "Groceries" in names
    assert "Dining" in names
    assert "Other" in names


def test_expense_crud_and_month_filtering():
    repo = BudgetRepository(make_db_path())
    groceries = repo.get_category_by_name("Groceries")
    dining = repo.get_category_by_name("Dining")

    april_id = repo.add_expense(
        spent_on=date(2026, 4, 12),
        category_id=groceries.id,
        description="Weekly groceries",
        amount=84.32,
        payment_method="Debit",
    )
    repo.add_expense(
        spent_on=date(2026, 5, 1),
        category_id=dining.id,
        description="Lunch",
        amount=18.5,
        payment_method="Credit",
    )

    april_expenses = repo.list_expenses(year=2026, month=4)
    assert len(april_expenses) == 1
    assert april_expenses[0].id == april_id
    assert april_expenses[0].category_name == "Groceries"

    repo.update_expense(
        expense_id=april_id,
        spent_on=date(2026, 4, 13),
        category_id=dining.id,
        description="Dinner",
        amount=42.0,
        payment_method="Cash",
    )
    updated = repo.get_expense(april_id)
    assert updated.spent_on == date(2026, 4, 13)
    assert updated.category_name == "Dining"
    assert updated.amount == 42.0

    repo.delete_expense(april_id)
    assert repo.list_expenses(year=2026, month=4) == []


def test_rejects_invalid_expenses():
    repo = BudgetRepository(make_db_path())
    category = repo.get_category_by_name("Groceries")

    with pytest.raises(ValueError, match="amount"):
        repo.add_expense(
            spent_on=date(2026, 4, 12),
            category_id=category.id,
            description="Bad value",
            amount=0,
            payment_method="Cash",
        )

    with pytest.raises(ValueError, match="date"):
        repo.add_expense(
            spent_on=None,
            category_id=category.id,
            description="Missing date",
            amount=12,
            payment_method="Cash",
        )


def test_category_delete_is_blocked_when_used_by_expense():
    repo = BudgetRepository(make_db_path())
    category = repo.get_category_by_name("Groceries")
    repo.add_expense(
        spent_on=date(2026, 4, 12),
        category_id=category.id,
        description="Weekly groceries",
        amount=84.32,
        payment_method="Debit",
    )

    with pytest.raises(ValueError, match="in use"):
        repo.delete_category(category.id)


def test_monthly_category_budget_upsert_and_lookup():
    repo = BudgetRepository(make_db_path())
    category = repo.get_category_by_name("Groceries")

    repo.set_monthly_budget(2026, 4, category.id, 400)
    repo.set_monthly_budget(2026, 4, category.id, 425)

    budgets = repo.list_monthly_budgets(2026, 4)
    assert len(budgets) == 1
    assert budgets[0].category_name == "Groceries"
    assert budgets[0].amount == 425
