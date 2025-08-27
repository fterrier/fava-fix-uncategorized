import pytest
from fava_fix_uncategorized import normalize_and_validate_posting, replace_unclassified_posting


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
        
        # When no new postings provided, original should remain unchanged
        assert "Expenses:Family:Unclassified" in result
        assert result.strip() == entry_str.strip()

    def test_preserve_indentation(self):
        entry_str = """2024-01-01 * "Test"
    Assets:Checking      -100.00 CHF
    Expenses:Family:Unclassified"""
        
        new_postings = [{"account": "Expenses:Food", "amount": "100.00 CHF"}]
        result = replace_unclassified_posting(entry_str, new_postings)
        
        lines = result.split('\n')
        # Should preserve the 4-space indentation
        assert any(line.startswith("    Expenses:Food") for line in lines)

    def test_replace_with_invalid_posting_format(self):
        """Test that replace_unclassified_posting handles invalid posting formats gracefully."""
        entry_str = """2024-01-01 * "Test"
  Assets:Checking      -100.00 CHF
  Expenses:Family:Unclassified"""
        
        # Include some invalid postings that should be skipped
        new_postings = [
            {"account": "Expenses:Food", "amount": "100.00 CHF"},  # Valid
            {"account": "Expenses:Transport", "amount": "invalid_amount"},  # Invalid - will be skipped
            {"account": "Expenses:Shopping", "amount": "50.00 CHF"},  # Valid
        ]
        
        result = replace_unclassified_posting(entry_str, new_postings)
        
        lines = result.split('\n')
        # Should include valid postings
        assert any("Expenses:Food 100.00 CHF" in line for line in lines)
        assert any("Expenses:Shopping 50.00 CHF" in line for line in lines)
        # Invalid posting should be skipped (not included)
        assert not any("invalid_amount" in line for line in lines)
        # Should still add the unclassified line with 0 amount
        assert any("Expenses:Family:Unclassified 0 CHF" in line for line in lines)