import pytest
from unittest.mock import Mock, patch
from fava_fix_uncategorized import FixUncategorized, normalize_and_validate_posting, replace_unclassified_posting


class TestNormalizeAndValidatePosting:
    """Test the normalize_and_validate_posting function."""

    def test_valid_amount_with_currency(self):
        posting = {"account": "Expenses:Food", "amount": "123.45 CHF"}
        result = normalize_and_validate_posting(posting)
        assert result["amount"] == "123.45 CHF"

    def test_valid_amount_without_currency_uses_default(self):
        posting = {"account": "Expenses:Food", "amount": "123.45"}
        result = normalize_and_validate_posting(posting)
        assert result["amount"] == "123.45 CHF"

    def test_amount_with_commas(self):
        posting = {"account": "Expenses:Food", "amount": "1,234.56 USD"}
        result = normalize_and_validate_posting(posting)
        assert result["amount"] == "1234.56 USD"

    def test_negative_amount(self):
        posting = {"account": "Expenses:Food", "amount": "-50.00 EUR"}
        result = normalize_and_validate_posting(posting)
        assert result["amount"] == "-50.00 EUR"

    def test_amount_with_spaces(self):
        posting = {"account": "Expenses:Food", "amount": "  123.45   CHF  "}
        result = normalize_and_validate_posting(posting)
        assert result["amount"] == "123.45 CHF"

    def test_empty_amount(self):
        posting = {"account": "Expenses:Food", "amount": ""}
        result = normalize_and_validate_posting(posting)
        assert result["amount"] == ""

    def test_invalid_amount_format(self):
        posting = {"account": "Expenses:Food", "amount": "invalid"}
        with pytest.raises(ValueError, match="Invalid amount format"):
            normalize_and_validate_posting(posting)

    def test_currency_converted_to_uppercase(self):
        posting = {"account": "Expenses:Food", "amount": "100.00 usd"}
        result = normalize_and_validate_posting(posting)
        assert result["amount"] == "100.00 USD"


class TestReplaceUnclassifiedPosting:
    """Test the replace_unclassified_posting function."""

    def test_replace_single_expenses_line(self):
        entry_str = """2024-01-01 * "Test"
  Assets:Checking      -100.00 CHF
  Expenses:Family:Unclassified"""
        
        new_postings = [{"account": "Expenses:Food", "amount": "100.00 CHF"}]
        result = replace_unclassified_posting(entry_str, new_postings)
        
        expected_lines = [
            "2024-01-01 * \"Test\"",
            "  Assets:Checking      -100.00 CHF",
            "  Expenses:Food 100.00 CHF",
            "  Expenses:Family:Unclassified 0 CHF"
        ]
        assert result == "\n".join(expected_lines)

    def test_replace_multiple_expenses_lines(self):
        entry_str = """2024-01-01 * "Test"
  Assets:Checking      -150.00 CHF
  Expenses:Family:Unclassified"""
        
        new_postings = [
            {"account": "Expenses:Food", "amount": "100.00 CHF"},
            {"account": "Expenses:Transport", "amount": "50.00 CHF"}
        ]
        result = replace_unclassified_posting(entry_str, new_postings)
        
        lines = result.split('\n')
        assert "  Expenses:Food 100.00 CHF" in lines
        assert "  Expenses:Transport 50.00 CHF" in lines
        assert "  Expenses:Family:Unclassified 0 CHF" in lines

    def test_preserve_non_expenses_lines(self):
        entry_str = """2024-01-01 * "Test"
  Assets:Checking      -100.00 CHF
  Assets:Savings       100.00 CHF
  Expenses:Family:Unclassified"""
        
        new_postings = [{"account": "Expenses:Food", "amount": "50.00 CHF"}]
        result = replace_unclassified_posting(entry_str, new_postings)
        
        assert "Assets:Checking      -100.00 CHF" in result
        assert "Assets:Savings       100.00 CHF" in result

    def test_no_new_postings_keeps_unclassified(self):
        entry_str = """2024-01-01 * "Test"
  Assets:Checking      -100.00 CHF
  Expenses:Family:Unclassified"""
        
        new_postings = []
        result = replace_unclassified_posting(entry_str, new_postings)
        
        assert "Expenses:Family:Unclassified" in result
        assert "0 CHF" not in result  # Should not add 0 CHF line when no new postings

    def test_preserve_indentation(self):
        entry_str = """2024-01-01 * "Test"
    Assets:Checking      -100.00 CHF
    Expenses:Family:Unclassified"""
        
        new_postings = [{"account": "Expenses:Food", "amount": "100.00 CHF"}]
        result = replace_unclassified_posting(entry_str, new_postings)
        
        lines = result.split('\n')
        # Should preserve the 4-space indentation
        assert any(line.startswith("    Expenses:Food") for line in lines)


class TestFixUncategorizedExtension:
    """Test the FixUncategorized extension class."""

    def setup_method(self):
        self.extension = FixUncategorized()
        self.extension.ledger = Mock()

    def test_expense_accounts_filtering(self):
        # Mock the ledger accounts
        self.extension.ledger.accounts = [
            "Assets:Checking",
            "Expenses:Family:Food",
            "Expenses:Family:Transport", 
            "Expenses:Family:Unclassified",
            "Expenses:BusinessStukas:Office",
            "Income:BusinessStukas:Consulting",
            "Income:Salary",
            "Liabilities:CreditCard"
        ]
        
        result = self.extension.expense_accounts()
        
        expected = [
            "Expenses:BusinessStukas:Office",
            "Expenses:Family:Food",
            "Expenses:Family:Transport",
            "Income:BusinessStukas:Consulting"
        ]
        assert result == expected

    def test_has_uncategorized_posting_true(self):
        # Mock transaction with uncategorized posting
        mock_txn = Mock()
        mock_posting = Mock()
        mock_posting.account = "Expenses:Family:Unclassified"
        mock_txn.postings = [mock_posting]
        
        result = self.extension._has_uncategorized_posting(mock_txn)
        assert result is True

    def test_has_uncategorized_posting_false(self):
        # Mock transaction without uncategorized posting
        mock_txn = Mock()
        mock_posting = Mock()
        mock_posting.account = "Expenses:Family:Food"
        mock_txn.postings = [mock_posting]
        
        result = self.extension._has_uncategorized_posting(mock_txn)
        assert result is False

    def test_in_interval_no_time_filter(self):
        mock_txn = Mock()
        result = self.extension._in_interval(mock_txn, None)
        assert result is True

    @patch('fava_fix_uncategorized.parse_date')
    def test_in_interval_with_time_filter(self, mock_parse_date):
        from datetime import date
        
        mock_txn = Mock()
        mock_txn.date = date(2024, 1, 15)
        
        # Test transaction within interval
        parsed_time = (date(2024, 1, 1), date(2024, 1, 31))
        result = self.extension._in_interval(mock_txn, parsed_time)
        assert result is True
        
        # Test transaction before interval
        parsed_time = (date(2024, 2, 1), date(2024, 2, 28))
        result = self.extension._in_interval(mock_txn, parsed_time)
        assert result is False