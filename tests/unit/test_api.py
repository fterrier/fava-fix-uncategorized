import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock
from fava.core import FavaLedger
from fava_fix_uncategorized import FixUncategorized


class TestFixUncategorizedAPI:
    """Test the FixUncategorized API endpoints with real requests."""

    def assert_transaction(self, txn, expected):
        """Helper to assert transaction fields"""
        for key, value in expected.items():
            assert txn[key] == value

    @pytest.fixture
    def test_ledger_file(self):
        """Create a temporary beancount file for testing."""
        ledger_content = '''1980-05-12 custom "fava-extension" "fava_fix_uncategorized"

1990-01-01 open Assets:Checking
1990-01-01 open Expenses:Family:Unclassified
1990-01-01 open Expenses:Family:Groceries
1990-01-01 open Expenses:Family:Restaurants
1990-01-01 open Expenses:BusinessStukas:Office
1990-01-01 open Income:BusinessStukas:Consulting
1990-01-01 open Income:Salary
1990-01-01 open Liabilities:CreditCard

2024-01-01 * "Grocery Store" "Weekly groceries"
  Assets:Checking              -150.00 CHF
  Expenses:Family:Unclassified  150.00 CHF

2024-02-03 * "Employer Inc" "Monthly salary payment"
  Assets:Checking             2500.00 CHF
  Income:Salary              -2000.00 CHF
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.beancount', delete=False) as f:
            f.write(ledger_content)
            f.flush()  # Ensure content is written to disk
            temp_path = Path(f.name)
        
        try:
            yield temp_path
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.fixture
    def extension(self, test_ledger_file):
        """Create a FixUncategorized extension with a real ledger."""
        # Load the ledger and force it to process entries
        ledger = FavaLedger(test_ledger_file)
        ledger.load_file()  # Force loading of the beancount file
        extension = FixUncategorized(ledger)
        return extension

    def test_expense_accounts_filtering(self, extension):
        """Test that expense_accounts returns the correct filtered accounts."""
        result = extension.expense_accounts()
        
        # Should return exactly these accounts from our test beancount file
        # (sorted, as per the implementation)
        expected_accounts = [
            "Expenses:BusinessStukas:Office",
            "Expenses:Family:Groceries", 
            "Expenses:Family:Restaurants",
            "Income:BusinessStukas:Consulting"
        ]
        
        assert result == expected_accounts

    def test_list_endpoint_returns_all_transactions(self, extension):
        """Test the list endpoint returns all transactions with proper structure."""
        # Mock Flask request context
        from flask import Flask
        app = Flask(__name__)
        
        with app.test_request_context('/?time='):
            response = extension.list()
            data = json.loads(response.data)
            
            assert data["success"] is True
            assert "transactions" in data
            transactions = data["transactions"]
            
            # Should have the expected number of transactions from our test data
            assert len(transactions) == 2
            transactions_by_date = {t["date"]: t for t in transactions}
            
            # Transaction 1: Grocery Store (2024-01-01)
            self.assert_transaction(transactions_by_date["2024-01-01"], {
                "date": "2024-01-01",
                "narration": "Weekly groceries",
                "payee": "Grocery Store",
                "errors": None,
                "unclassified": True,
                "postings": [{"account": "Assets:Checking", "amount": "-150.00 CHF", "editable": False}]
            })
            
            # Transaction 2: Employer Inc (2024-02-03)
            salary_txn = transactions_by_date["2024-02-03"]
            self.assert_transaction(salary_txn, {
                "date": "2024-02-03",
                "narration": "Monthly salary payment",
                "payee": "Employer Inc",
                "unclassified": False,
                "postings": [
                    {"account": "Assets:Checking", "amount": "2500.00 CHF", "editable": False},
                    {"account": "Income:Salary", "amount": "-2000.00 CHF", "editable": True}
                ]
            })
            
            # Check that all transactions have required structure
            required_fields = ["lineno", "hash", "date", "narration", "payee", "errors", "postings", "unclassified"]
            for txn in transactions:
                for field in required_fields:
                    assert field in txn

    def test_list_endpoint_filters_by_time(self, extension):
        """Test the list endpoint filters transactions by time parameter."""
        from flask import Flask
        app = Flask(__name__)
        
        # Test with no time filter
        with app.test_request_context('/'):
            response = extension.list()
            data = json.loads(response.data)
            
            assert data["success"] is True
            transactions = data["transactions"]
            all_transactions_count = len(transactions)
        
        # Test filtering to January 2024
        with app.test_request_context('/?time=2024-02'):
            response = extension.list()
            data = json.loads(response.data)
            
            assert data["success"] is True
            transactions = data["transactions"]
            transactions_by_date = {t["date"]: t for t in transactions}
            
            # Should have same or fewer transactions when filtered
            assert len(transactions) < all_transactions_count
            
            # Transaction 2: Employer Inc (2024-02-03)
            self.assert_transaction(transactions_by_date["2024-02-03"], {
                "date": "2024-02-03",
                "narration": "Monthly salary payment",
                "payee": "Employer Inc",
                "unclassified": False,
                "postings": [
                    {"account": "Assets:Checking", "amount": "2500.00 CHF", "editable": False},
                    {"account": "Income:Salary", "amount": "-2000.00 CHF", "editable": True}
                ]
            })

    def test_list_endpoint_handles_errors_gracefully(self, extension):
        """Test that the list endpoint properly attaches errors to transactions."""
        from flask import Flask
        app = Flask(__name__)
        
        with app.test_request_context('/'):
            response = extension.list()
            data = json.loads(response.data)
            
            assert data["success"] is True
            transactions = data["transactions"]
            transactions_by_date = {t["date"]: t for t in transactions}
            
            # The salary transaction (2024-02-03) should have an error due to unbalanced postings
            salary_txn = transactions_by_date["2024-02-03"]
            
            # The unbalanced transaction should have an error attached
            assert "errors" in salary_txn
            assert len(salary_txn["errors"]) > 0, "Should have at least one error"
            
            # Check that the error message mentions the imbalance
            error_messages = " ".join(salary_txn["errors"])
            assert any(keyword in error_messages.lower() for keyword in ["balance", "imbalance", "sum"]), \
                f"Error should mention balance/imbalance: {error_messages}"

    def test_save_endpoint_returns_error_when_hash_not_found(self, extension):
        """Test that the save endpoint validates input properly."""
        from flask import Flask
        app = Flask(__name__)
        
        # Test with empty request data
        with app.test_request_context('/', json={}):
            result = extension.save()
            assert result["success"] is True
            assert result["data"] == []
        
        # Test with transactions but no postings
        test_data = {
            "transactions": [{
                "hash": "test_hash",
                "lineno": 1,
                "postings": []
            }]
        }
        
        with app.test_request_context('/', json=test_data):
            result = extension.save()
            # The result might be a tuple (dict, status_code) when there's an error
            if isinstance(result, tuple):
                result, status_code = result
                assert status_code == 500
            # If it doesn't find the entry, it should raise an error
            assert result["success"] is False

    def test_save_endpoint_rejects_invalid_postings(self, extension, test_ledger_file):
        """Test that the save endpoint rejects invalid posting amounts."""
        from flask import Flask
        app = Flask(__name__)
        
        # Get original file content
        original_content = test_ledger_file.read_text()
        
        # Get a real uncategorized transaction from the ledger first
        with app.test_request_context('/'):
            list_response = extension.list()
            list_data = json.loads(list_response.data)
            
        # Find first uncategorized transaction
        uncategorized_txns = [t for t in list_data["transactions"] if t["unclassified"]]
        assert uncategorized_txns, "No uncategorized transactions found for testing"
        uncategorized_txn = uncategorized_txns[0]
        
        # Test with invalid amount format
        test_data = {
            "transactions": [{
                "hash": uncategorized_txn["hash"],
                "lineno": uncategorized_txn["lineno"],
                "postings": [
                    {"account": "Expenses:Family:Groceries", "amount": "400 ABCD"}  # Invalid currency
                ]
            }]
        }
        
        with app.test_request_context('/', json=test_data):
            result = extension.save()
            # Should succeed but skip the invalid posting and fall back to Unclassified
            assert result["success"] is True
            assert isinstance(result["data"], list)
            
            # Verify file was modified (invalid posting skipped, falls back to default)
            modified_content = test_ledger_file.read_text()
            assert modified_content != original_content, "File should be modified even with invalid posting"
            # Should not contain the invalid currency but should have the fallback
            assert "ABCD" not in modified_content, "Invalid currency should not appear in file"
            assert "Expenses:Family:Unclassified" in modified_content, "Should fall back to Unclassified posting"

    def test_save_endpoint_with_valid_data(self, extension, test_ledger_file):
        """Test the save endpoint with valid transaction data and verify file modification."""
        from flask import Flask
        app = Flask(__name__)
        
        # Get original file content
        original_content = test_ledger_file.read_text()
        
        # Get a real uncategorized transaction from the ledger
        with app.test_request_context('/'):
            list_response = extension.list()
            list_data = json.loads(list_response.data)
        
        # Find first uncategorized transaction
        uncategorized_txns = [t for t in list_data["transactions"] if t["unclassified"]]
        assert uncategorized_txns, "No uncategorized transactions found for testing"
        
        uncategorized_txn = uncategorized_txns[0]
        
        # Prepare save data with new postings
        save_data = {
            "transactions": [{
                "hash": uncategorized_txn["hash"],
                "lineno": uncategorized_txn["lineno"],
                "postings": [
                    {"account": "Expenses:Family:Groceries", "amount": "150.00 CHF"}
                ]
            }]
        }
        
        # Attempt to save the transaction
        with app.test_request_context('/', json=save_data):
            result = extension.save()
            
            # Verify the response structure
            assert result["success"] is True
            assert isinstance(result["data"], list)
            assert len(result["data"]) == 1
            
            # Verify file was actually modified
            modified_content = test_ledger_file.read_text()
            assert modified_content != original_content, "File content should have changed after save"
            assert "Expenses:Family:Groceries" in modified_content, "New account should appear in file"

    def test_save_endpoint_saves_narration_changes(self, extension, test_ledger_file):
        """Test that the save endpoint saves narration changes when provided."""
        from flask import Flask
        app = Flask(__name__)
        
        # Get original file content
        original_content = test_ledger_file.read_text()
        
        # Get a transaction from the ledger
        with app.test_request_context('/'):
            list_response = extension.list()
            list_data = json.loads(list_response.data)
        
        # Get transactions by date
        transactions_by_date = {t["date"]: t for t in list_data["transactions"]}
        grocery_txn = transactions_by_date["2024-01-01"]  # Grocery Store transaction
        
        # Prepare save data with narration change
        save_data = {
            "transactions": [{
                "hash": grocery_txn["hash"],
                "lineno": grocery_txn["lineno"],
                "postings": [
                    {"account": "Expenses:Family:Groceries", "amount": "150.00 CHF"}
                ],
                "narration": "Updated weekly groceries shopping"
            }]
        }
        
        # Attempt to save the transaction
        with app.test_request_context('/', json=save_data):
            result = extension.save()
            
            # Verify the response structure
            assert result["success"] is True
            assert isinstance(result["data"], list)
            assert len(result["data"]) == 1
            
            # Verify file was modified with new narration
            modified_content = test_ledger_file.read_text()
            assert modified_content != original_content, "File content should have changed after save"
            assert "Updated weekly groceries shopping" in modified_content, "New narration should appear in file"
            assert "Expenses:Family:Groceries" in modified_content, "New account should appear in file"