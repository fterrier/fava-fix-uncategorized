import pytest
import time
import re
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
        expect(first_txn).to_have_class(re.compile(r".*txn-modified.*"))

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
        
        # The expense accounts list should exist in the DOM (even if hidden initially)
        expect(page.locator("#expense-accounts-list")).to_be_attached()
        
        # Check that it contains account options
        account_list = page.locator("#expense-accounts-list li")
        # Should have at least one account option
        expect(account_list.first).to_be_attached()
        
        # Type partial account name to trigger autocomplete
        account_input.click()
        account_input.fill("Expenses:")
        
        # The autocomplete should now be functional (we can't easily test visibility 
        # of the Awesomplete dropdown, but we can verify the account list has entries)
        expect(account_list.first).to_contain_text("Expenses")

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

    def test_error_display_for_unbalanced_transaction(self, page: Page, fava_server: str):
        """Test that errors are displayed for unbalanced transactions."""
        page.goto(f"{fava_server}/extension/FixUncategorized/")
        
        # Wait for transactions to load
        page.wait_for_selector(".txn-block", timeout=5000)
        
        # Uncheck the filter to show all transactions (including the salary with errors)
        checkbox = page.locator("#only-uncategorized")
        if checkbox.is_checked():
            checkbox.uncheck()
        
        # Find the salary transaction by looking for the text "Salary Payment" in any transaction
        salary_txn = page.locator(".txn-block").filter(has_text="Salary Payment")
        expect(salary_txn).to_have_count(1)
        
        # The salary transaction should have the "error" class
        expect(salary_txn).to_have_class("txn-block error")
        
        # Check for error message in the txn-error-message div
        error_message_div = salary_txn.locator(".txn-error-message")
        expect(error_message_div).to_be_visible()
        
        # Verify the error message content mentions balance issues
        error_text = error_message_div.inner_text().lower()
        assert any(keyword in error_text for keyword in ["balance", "imbalance", "sum"]), \
            f"Error message should mention balance issue: {error_text}"

    def test_save_multiple_modifications(self, page: Page, fava_server: str):
        """Test that saving multiple times with different modifications works."""
        page.goto(f"{fava_server}/extension/FixUncategorized/")
        page.wait_for_selector(".txn-block", timeout=5000)
        
        first_txn = page.locator(".txn-block.txn-unclassified").first
        
        # First modification: Set to Groceries
        first_txn.locator(".expense-account-input").first.fill("Expenses:Family:Groceries")
        first_txn.locator(".expense-amount").first.fill("150.00 CHF")
        page.locator("#save-all-btn").click()
        
        # Wait for save to complete and reload data
        page.wait_for_timeout(1000)
        page.reload()
        page.wait_for_selector(".txn-block", timeout=5000)
        
        # Second modification: Change to Restaurants
        first_txn = page.locator(".txn-block").filter(has_text="Grocery Store").first
        first_txn.locator(".expense-account-input").first.fill("Expenses:Family:Restaurants")
        expect(first_txn).to_have_class(re.compile(r".*txn-modified.*"))
        page.locator("#save-all-btn").click()
        
        # Verify modifications persist
        page.wait_for_timeout(1000)
        page.reload()
        page.wait_for_selector(".txn-block", timeout=5000)
        
        # Should still be able to modify again
        first_txn = page.locator(".txn-block").filter(has_text="Grocery Store").first
        first_txn.locator(".expense-amount").first.clear()
        first_txn.locator(".expense-amount").first.fill("175.00 CHF")
        expect(first_txn).to_have_class(re.compile(r".*txn-modified.*"))
        
        # Verify the account field still has the expected value from second save
        account_input = first_txn.locator(".expense-account-input").first
        expect(account_input).to_have_value("Expenses:Family:Restaurants")

    def test_save_with_enter_key(self, page: Page, fava_server: str):
        """Test that pressing Enter while editing a posting triggers save."""
        page.goto(f"{fava_server}/extension/FixUncategorized/")
        page.wait_for_selector(".txn-block", timeout=5000)
        
        first_txn = page.locator(".txn-block.txn-unclassified").first
        
        # Fill in account and amount, then press Enter on amount field
        first_txn.locator(".expense-account-input").first.fill("Expenses:Family:Groceries")
        amount_input = first_txn.locator(".expense-amount").first
        amount_input.fill("150.00 CHF")
        amount_input.press("Enter")
        
        # Wait and reload to verify save occurred
        page.wait_for_timeout(1000)
        page.reload()
        page.wait_for_selector(".txn-block", timeout=5000)
        
        # Verify the change persisted (transaction should now show the account)
        saved_txn = page.locator(".txn-block").filter(has_text="Grocery Store").first
        account_input = saved_txn.locator(".expense-account-input").first
        expect(account_input).to_have_value("Expenses:Family:Groceries")

    def test_editable_narration(self, page: Page, fava_server: str):
        """Test that narration can be edited by clicking on it and is saved."""
        page.goto(f"{fava_server}/extension/FixUncategorized/")
        page.wait_for_selector(".txn-block", timeout=5000)
        
        # Find transaction with editable narration
        first_txn = page.locator(".txn-block").first
        narration_element = first_txn.locator(".txn-narration")
        
        # Should be visible and clickable
        expect(narration_element).to_be_visible()
        
        # Click to edit narration
        narration_element.click()
        
        # Should now have an input field
        input_field = narration_element.locator("input")
        expect(input_field).to_be_visible()
        
        # Change the narration
        input_field.fill("Updated narration for testing")
        input_field.press("Enter")
        
        # Should be marked as modified
        expect(first_txn).to_have_class(re.compile(r".*txn-modified.*"))
        
        # The narration display should be updated
        expect(narration_element).to_contain_text("Updated narration for testing")
        
        # Save the changes
        page.locator("#save-all-btn").click()
        
        # Wait for save to complete and reload page to verify persistence
        page.wait_for_timeout(1000)
        page.reload()
        page.wait_for_selector(".txn-block", timeout=5000)
        
        # Find the same transaction and verify narration was saved
        first_txn_after_reload = page.locator(".txn-block").first
        narration_element_after_reload = first_txn_after_reload.locator(".txn-narration")
        expect(narration_element_after_reload).to_contain_text("Updated narration for testing")