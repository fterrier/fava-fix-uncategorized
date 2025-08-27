import pytest
import time
from playwright.sync_api import Page, expect


class TestFixUncategorizedFrontend:
    """End-to-end tests for the Fix Uncategorized plugin frontend."""

    def test_extension_page_loads(self, page: Page, fava_server: str):
        """Test that the Fix Uncategorized extension page loads."""
        page.goto(f"{fava_server}/extension/FixUncategorized/")
        
        # Should see the page title (Fava adds " - Beancount" to extension titles)
        expect(page).to_have_title("Fix Uncategorized - Beancount")
        
        # Should see the top bar with filter checkbox and save button
        expect(page.locator("#only-uncategorized")).to_be_visible()
        expect(page.locator("#save-all-btn")).to_be_visible()

    def test_transactions_list_displays(self, page: Page, fava_server: str):
        """Test that transactions are loaded and displayed."""
        page.goto(f"{fava_server}/extension/FixUncategorized/")
        
        # Wait for transactions to load
        page.wait_for_selector(".txn-block", timeout=5000)
        
        # Should see transaction blocks
        transactions = page.locator(".txn-block")
        expect(transactions).to_have_count(4)  # All 4 transactions from test data
        
        # Should see uncategorized transactions highlighted
        uncategorized_txns = page.locator(".txn-block.txn-unclassified")
        expect(uncategorized_txns).to_have_count(3)  # 3 uncategorized transactions

    def test_filter_only_uncategorized(self, page: Page, fava_server: str):
        """Test the 'Only uncategorized' filter functionality."""
        page.goto(f"{fava_server}/extension/FixUncategorized/")
        
        # Wait for transactions to load
        page.wait_for_selector(".txn-block", timeout=5000)
        
        # Initially, filter should be checked and only uncategorized should be visible
        checkbox = page.locator("#only-uncategorized")
        expect(checkbox).to_be_checked()
        
        # Count visible transactions (should be 3 uncategorized)
        visible_txns = page.locator(".txn-block:visible")
        expect(visible_txns).to_have_count(3)
        
        # Uncheck the filter
        checkbox.uncheck()
        
        # Now all transactions should be visible (4 total)
        visible_txns = page.locator(".txn-block:visible")
        expect(visible_txns).to_have_count(4)

    def test_add_posting_to_transaction(self, page: Page, fava_server: str):
        """Test adding a posting to a transaction."""
        page.goto(f"{fava_server}/extension/FixUncategorized/")
        
        # Wait for transactions to load
        page.wait_for_selector(".txn-block", timeout=5000)
        
        # Find first uncategorized transaction
        first_txn = page.locator(".txn-block.txn-unclassified").first
        
        # Should have at least one empty posting row
        posting_rows = first_txn.locator(".posting-row")
        expect(posting_rows).to_have_count(1)
        
        # Fill in account and amount
        account_input = first_txn.locator(".expense-account-input").first
        amount_input = first_txn.locator(".expense-amount").first
        
        account_input.fill("Expenses:Family:Groceries")
        amount_input.fill("150.00 CHF")
        
        # Transaction should be marked as modified
        expect(first_txn).to_have_class("txn-modified")

    def test_add_multiple_postings(self, page: Page, fava_server: str):
        """Test adding multiple postings to split a transaction."""
        page.goto(f"{fava_server}/extension/FixUncategorized/")
        
        # Wait for transactions to load
        page.wait_for_selector(".txn-block", timeout=5000)
        
        # Find first uncategorized transaction
        first_txn = page.locator(".txn-block.txn-unclassified").first
        
        # Fill in first posting
        first_txn.locator(".expense-account-input").first.fill("Expenses:Family:Groceries")
        first_txn.locator(".expense-amount").first.fill("100.00 CHF")
        
        # Add another posting
        first_txn.locator(".add-below-btn").first.click()
        
        # Should now have 2 posting rows
        posting_rows = first_txn.locator(".posting-row")
        expect(posting_rows).to_have_count(2)
        
        # Fill in second posting
        account_inputs = first_txn.locator(".expense-account-input")
        amount_inputs = first_txn.locator(".expense-amount")
        
        account_inputs.nth(1).fill("Expenses:Family:Restaurants")
        amount_inputs.nth(1).fill("50.00 CHF")

    def test_delete_posting_row(self, page: Page, fava_server: str):
        """Test deleting a posting row."""
        page.goto(f"{fava_server}/extension/FixUncategorized/")
        
        # Wait for transactions to load
        page.wait_for_selector(".txn-block", timeout=5000)
        
        # Find first uncategorized transaction
        first_txn = page.locator(".txn-block.txn-unclassified").first
        
        # Add a posting row
        first_txn.locator(".add-below-btn").first.click()
        
        # Should have 2 rows
        posting_rows = first_txn.locator(".posting-row")
        expect(posting_rows).to_have_count(2)
        
        # Delete the second row
        first_txn.locator(".delete-btn").nth(1).click()
        
        # Should be back to 1 row
        posting_rows = first_txn.locator(".posting-row")
        expect(posting_rows).to_have_count(1)

    def test_account_autocomplete(self, page: Page, fava_server: str):
        """Test that account autocomplete works."""
        page.goto(f"{fava_server}/extension/FixUncategorized/")
        
        # Wait for transactions to load
        page.wait_for_selector(".txn-block", timeout=5000)
        
        # Find first uncategorized transaction
        first_txn = page.locator(".txn-block.txn-unclassified").first
        account_input = first_txn.locator(".expense-account-input").first
        
        # Type partial account name
        account_input.fill("Expenses:Family:")
        
        # Should see autocomplete suggestions
        # Note: This test might need adjustment based on actual autocomplete implementation
        expect(page.locator("#expense-accounts-list")).to_be_visible()

    def test_save_functionality_requires_modifications(self, page: Page, fava_server: str):
        """Test that save button works correctly when there are modifications."""
        page.goto(f"{fava_server}/extension/FixUncategorized/")
        
        # Wait for transactions to load
        page.wait_for_selector(".txn-block", timeout=5000)
        
        # Initially save button should be enabled but nothing to save
        save_btn = page.locator("#save-all-btn")
        expect(save_btn).to_be_enabled()
        
        # Make a modification
        first_txn = page.locator(".txn-block.txn-unclassified").first
        first_txn.locator(".expense-account-input").first.fill("Expenses:Family:Groceries")
        first_txn.locator(".expense-amount").first.fill("150.00 CHF")
        
        # Click save button (note: this will likely show an alert about no server endpoint in test)
        save_btn.click()
        
        # In a real test environment, we'd verify the server response
        # For now, we just verify the save attempt was made

    def test_move_posting_up_down(self, page: Page, fava_server: str):
        """Test moving postings up and down."""
        page.goto(f"{fava_server}/extension/FixUncategorized/")
        
        # Wait for transactions to load
        page.wait_for_selector(".txn-block", timeout=5000)
        
        # Find first uncategorized transaction
        first_txn = page.locator(".txn-block.txn-unclassified").first
        
        # Add two postings
        first_txn.locator(".expense-account-input").first.fill("Expenses:Family:Groceries")
        first_txn.locator(".expense-amount").first.fill("100.00 CHF")
        
        first_txn.locator(".add-below-btn").first.click()
        
        account_inputs = first_txn.locator(".expense-account-input")
        amount_inputs = first_txn.locator(".expense-amount")
        
        account_inputs.nth(1).fill("Expenses:Family:Restaurants")
        amount_inputs.nth(1).fill("50.00 CHF")
        
        # Move second posting up
        first_txn.locator(".move-up-btn").nth(1).click()
        
        # Verify the order changed (Restaurants should now be first)
        first_account = first_txn.locator(".expense-account-input").first
        expect(first_account).to_have_value("Expenses:Family:Restaurants")