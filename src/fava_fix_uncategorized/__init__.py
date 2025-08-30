import functools
import logging
import os 
import traceback
import re

from flask import jsonify
from flask import request

from fava.ext import FavaExtensionBase
from fava.ext import extension_endpoint
from fava.helpers import FavaAPIError
from fava.beans.abc import Transaction
from fava.beans.funcs import hash_entry
from fava.core.file import get_entry_slice
from fava.util.date import parse_date


logger = logging.getLogger(__name__)
if loglevel := os.environ.get("LOGLEVEL"):
    logger.setLevel(loglevel.upper())

def api_response(func):
    """return {success: true, data: ...} or {success: false, error: ...}"""

    @functools.wraps(func)
    def decorator(*args, **kwargs):
        try:
            data = func(*args, **kwargs)
            return {"success": True, "data": data}
        except FavaAPIError as e:
            return {"success": False, "error": e.message}, 500
        except Exception as e:  # pylint: disable=broad-exception-caught
            traceback.print_exception(e)
            return {"success": False, "error": str(e)}, 500

    return decorator


def normalize_and_validate_posting(posting):
    """
    Normalize postings: uppercase currency and validate format.
    Ignores misplaced/absent commas and re-formats properly.

    Args:
        postings (dict): Each dict has 'account' and 'amount'.

    Returns:
        dict: Postings with normalized amounts.

    Raises:
        ValueError: If any amount doesn't match required format.
    """
    pattern = re.compile(r"""
        (?P<number>\-?\s*\d+(?:[.,]\d+)*(?:[.]\d{2})?|\d+)  # number with optional commas/decimals
        \s*
        (?P<currency>[A-Za-z]{3})?   # optional 3-letter currency
        $
    """, re.VERBOSE)

    amount = posting.get("amount", "").strip()

    if amount:
        match = pattern.match(amount)
        if not match:
            raise ValueError(f"Invalid amount format: {amount}")

        number = match.group("number").replace(",", "").replace(" ", "")  # remove commas and whitespace
        currency = match.group("currency")

        if currency:
            currency = currency.upper()
        else:
            currency = "CHF"   # default

        posting["amount"] = f"{number} {currency}"
    else:
        posting["amount"] = ""

    return posting


def replace_unclassified_posting(entry_str, new_postings):
    """
    Replace all 'Expenses:' lines with new postings, keeping the smallest indent level.

    Args:
        entry_str (str): Original transaction text.
        new_postings (list[dict]): New postings to add.

    Returns:
        str: Modified transaction text.
    """

    lines = entry_str.splitlines()
    kept_lines = []
    min_indent = None

    for line in lines:
        stripped = line.lstrip()
        indent_len = len(line) - len(stripped)
        if indent_len != 0 and (min_indent is None or indent_len < min_indent):
            min_indent = indent_len
        if not stripped.startswith("Expenses:") and not stripped.startswith("Income:"):
            kept_lines.append(line)

    indent = " " * (min_indent if min_indent is not None else 2)

    validated_postings = []
    for p in new_postings:
        try:
            validated_postings.append(normalize_and_validate_posting(p))
        except Exception:
            # TODO find a better way
            continue

    new_posting_lines = [f"{indent}{p['account']} {p['amount']}" for p in validated_postings]
    if (len(new_posting_lines) == 0):
        new_posting_lines.append(f"{indent}Expenses:Family:Unclassified")
    else:
        new_posting_lines.append(f"{indent}Expenses:Family:Unclassified 0 CHF")

    return "\n".join(kept_lines + new_posting_lines)


def change_narration(entry_str, new_narration):
    """
    Change the narration (second quoted string) in a transaction entry.
    
    Args:
        entry_str (str): Original transaction text.
        new_narration (str): New narration to set.
    
    Returns:
        str: Modified transaction text with updated narration.
    """
    lines = entry_str.splitlines()
    if not lines:
        return entry_str
    
    first_line = lines[0]
    if '*' not in first_line:
        return entry_str
    
    # Strip all double quotes from the new narration to prevent parsing issues
    if new_narration:
        new_narration = new_narration.replace('"', '')
    
    # Parse transaction line: date * "payee" "narration"
    parts = first_line.split('"')
    
    # Check if we have proper quote structure (even number means closed quotes)
    if len(parts) % 2 == 0:
        return entry_str  # Malformed quotes, return unchanged
    
    if len(parts) >= 4:
        # Has both payee and narration: replace narration (index 3)
        if new_narration == "":
            # Remove narration entirely - keep only payee part and trim trailing space
            lines[0] = '"'.join(parts[:3]).rstrip()
        else:
            parts[3] = new_narration
            lines[0] = '"'.join(parts)
    elif len(parts) >= 3:
        # Has only payee: add narration if not empty
        if new_narration:
            # Insert narration: parts[0] + "payee" + parts[2] + " \"" + narration + "\""
            lines[0] = '"'.join(parts[:3]) + ' "' + new_narration + '"'
    
    return "\n".join(lines)


class FixUncategorized(FavaExtensionBase):
    report_title = "Fix Uncategorized"
    has_js_module = True

    @extension_endpoint("save", methods=["POST"])
    @api_response
    def save(self):
        data = request.get_json()
        txns = data.get("transactions", [])

        results = []

        # TODO we should try to save all transactions, and return errors for those that fail only
        for txn in txns:
            hash = txn["hash"]
            lineno = txn["lineno"]

            entry = self.ledger.get_entry(hash)
            if not entry:
                raise FavaAPIError(f"Entry with hash {hash} not found")

            slice_string, sha256sum = get_entry_slice(entry)
            new_string = replace_unclassified_posting(slice_string, txn["postings"])
            
            # Apply narration change if provided
            new_narration = txn.get("narration")
            if new_narration is not None:
                new_string = change_narration(new_string, new_narration)

            try:
                self.ledger.file.save_entry_slice(hash, new_string, sha256sum)
            except Exception as e:
                raise FavaAPIError(f"Failed to save transaction at line {lineno}: {str(e)}")

            results.append({
                "lineno": lineno,
                "hash": hash,
                "existing": entry,
                "slice": slice_string,
                "new_slice": new_string,
            })

        return results

    @extension_endpoint("list", methods=["GET"])
    def list(self):
        # Parse optional "time" query parameter
        time_param = request.args.get("time")
        parsed_time = None
        if time_param:
            try:
                parsed_time = parse_date(time_param)
            except Exception:
                parsed_time = None

        error_map = self._get_errors()
        entries = []
        # Iterate over all transactions, not just uncategorized
        for txn in self.ledger.all_entries_by_type.Transaction:
            if not self._is_in_interval(txn, parsed_time):
                continue
            unclassified = self._has_uncategorized_posting(txn)
            entries.append({
                "lineno": txn.meta.get("lineno"),
                "hash": hash_entry(txn),
                "date": txn.date.isoformat(),
                "narration": txn.narration if txn.payee else "",
                "payee": txn.payee if txn.payee else txn.narration,
                "errors": error_map.get(txn.meta.get("lineno")),
                "postings": [
                    {
                        "account": p.account,
                        "amount": f"{p.units.number} {p.units.currency}" if p.units else "",
                        "editable": p.account.startswith("Expenses:") or p.account.startswith("Income:")
                    }
                    for p in txn.postings
                    if p.account != "Expenses:Family:Unclassified"
                ],
                "unclassified": unclassified
            })
        
        # Include expense accounts in the response for frontend use
        expense_accounts = self.expense_accounts()
        
        return jsonify(success=True, transactions=entries, expense_accounts=expense_accounts)

    def _get_errors(self):
        error_map = {}
        for err in self.ledger.errors:
            if err.source is not None:
                lineno = err.source.get("lineno")
                if lineno is not None:
                    error_map.setdefault(lineno, []).append(err.message)
        return error_map

    def _is_in_interval(self, txn, parsed_time):
        """Return True if txn.date falls within the parsed_time interval.

        parsed_time: tuple (start_date, end_date)
        - start_date or end_date can be None, meaning unbounded.
        """
        if parsed_time is None:
            return True

        start_date, end_date = parsed_time
        d = txn.date

        if start_date is not None and d < start_date:
            return False
        if end_date is not None and d > end_date:
            return False

        return True

    def expense_accounts(self):
        return sorted([
            acc for acc in self.ledger.accounts
            if (acc.startswith("Expenses:Family:") or acc.startswith("Expenses:BusinessStukas:") or acc.startswith("Income:BusinessStukas:")) 
                and not acc.startswith("Expenses:Family:Unclassified")
        ])


    def _has_uncategorized_posting(self, txn):
        for posting in txn.postings:
            if posting.account == "Expenses:Family:Unclassified":
                return True
        return False
    