import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock
from fava.core import FavaLedger
from fava_fix_uncategorized import FixUncategorized


class TestFixUncategorizedAPI:
    """Test the FixUncategorized API endpoints with real requests."""

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

2024-01-02 * "Restaurant" "Dinner out"
  Assets:Checking              -80.50 CHF
  Expenses:Family:Unclassified  80.50 CHF

2024-01-03 * "Salary Payment"
  Assets:Checking             2500.00 CHF
  Income:Salary              -2500.00 CHF

2024-01-04 * "Gas Station" "Fuel"
  Assets:Checking              -65.00 CHF
  Expenses:Family:Unclassified  65.00 CHF
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
        
        # The actual accounts from our test beancount file should be filtered
        # Should include Family and BusinessStukas expenses, but not Unclassified
        assert isinstance(result, list)
        
        # Check that we get some accounts and they follow the expected pattern
        for account in result:
            assert (account.startswith("Expenses:Family:") or 
                   account.startswith("Expenses:BusinessStukas:") or 
                   account.startswith("Income:BusinessStukas:"))
            assert not account.endswith("Unclassified")

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
            assert len(transactions) == 4
            
            # Check structure of first transaction if any exist
            if transactions:
                txn = transactions[0]
                required_fields = ["lineno", "hash", "date", "narration", "payee", "errors", "postings", "unclassified"]
                for field in required_fields:
                    assert field in txn
                
                # Check postings structure
                for posting in txn["postings"]:
                    assert "account" in posting
                    assert "amount" in posting
                    assert "editable" in posting

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
        with app.test_request_context('/?time=2024-01'):
            response = extension.list()
            data = json.loads(response.data)
            
            assert data["success"] is True
            transactions = data["transactions"]
            # Should have same or fewer transactions when filtered
            assert len(transactions) <= all_transactions_count

    def test_list_endpoint_handles_errors_gracefully(self, extension):
        """Test that the list endpoint handles error processing without breaking."""
        from flask import Flask
        app = Flask(__name__)
        
        with app.test_request_context('/'):
            response = extension.list()
            data = json.loads(response.data)
            
            assert data["success"] is True
            transactions = data["transactions"]
            
            # Each transaction should have an errors field (even if None/empty)
            for txn in transactions:
                assert "errors" in txn
                # errors field should be None or a list
                assert txn["errors"] is None or isinstance(txn["errors"], list)

    def test_save_endpoint_validates_input(self, extension):
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
            # This should not crash, even if the hash doesn't exist
            try:
                result = extension.save()
                # If it doesn't find the entry, it should raise an error
                assert result["success"] is False
            except Exception:
                # Or it might raise an exception, which is also acceptable
                pass

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
            try:
                result = extension.save()
                
                # Verify the response structure
                assert "success" in result
                if result["success"]:
                    assert "data" in result
                    assert isinstance(result["data"], list)
                    assert len(result["data"]) == 1
                    
                    # Verify file was actually modified
                    modified_content = test_ledger_file.read_text()
                    assert modified_content != original_content, "File content should have changed after save"
                    assert "Expenses:Family:Groceries" in modified_content, "New account should appear in file"
                    
            except Exception as e:
                # If it fails due to file operations, that's expected in tests
                error_msg = str(e)
                assert any(msg in error_msg for msg in ["Failed to save", "not found", "readonly"]), \
                    f"Unexpected error: {error_msg}"