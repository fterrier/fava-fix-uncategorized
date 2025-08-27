# Development Notes

This project was created with assistance from Claude Code.

## Plugin Structure

The plugin follows the standard Fava extension pattern:
- Backend Python code in `src/fava_fix_uncategorized/__init__.py`
- Frontend JavaScript in `src/fava_fix_uncategorized/FixUncategorized.js`
- HTML template in `src/fava_fix_uncategorized/templates/FixUncategorized.html`

## Key Features

- Interactive categorization of uncategorized transactions
- Real-time validation of posting formats
- Account autocompletion
- Bulk save functionality
- Error handling and display

## Debugging Guide

### E2E Test Failures

When e2e tests fail (especially with timeouts waiting for `.txn-block` elements), the issue is usually in the backend API endpoints returning 500 errors. Here's how to debug:

#### Step 1: Check if the extension page loads
```bash
# Run a single test to see the basic setup
python -m pytest tests/e2e/test_frontend.py::TestFixUncategorizedFrontend::test_extension_page_loads -v -s
```

If this passes, the extension is loading correctly and the issue is in the API endpoints.

#### Step 2: Test the backend API directly
```bash
# Create a simple test beancount file
cat > test_debug.beancount << 'EOF'
1980-05-12 custom "fava-extension" "fava_fix_uncategorized"
1990-01-01 open Assets:Checking
1990-01-01 open Expenses:Family:Unclassified
2024-01-01 * "Test"
  Assets:Checking              -100.00 CHF
  Expenses:Family:Unclassified  100.00 CHF
EOF

# Start fava server manually with debug output
PYTHONPATH=src fava test_debug.beancount --port 5555 --debug > fava_debug.log 2>&1 &
FAVA_PID=$!

# Wait for server to start
sleep 5

# Test the API endpoint directly
curl -s "http://127.0.0.1:5555/beancount/extension/FixUncategorized/list"

# Check for 500 errors in the logs
cat fava_debug.log

# Cleanup
kill $FAVA_PID
rm test_debug.beancount fava_debug.log
```

#### Step 3: Common Issues and Fixes

1. **500 Internal Server Error in API endpoints**
   - Check `fava_debug.log` for Python tracebacks
   - Common issue: `AttributeError: 'NoneType' object has no attribute 'get'` in `_errors()` method
   - Fix: Add null checks before accessing error attributes

2. **Plugin not loading (404 errors)**
   - Ensure `PYTHONPATH=src` is set when running fava
   - Check that the beancount file has: `custom "fava-extension" "fava_fix_uncategorized"`
   - Verify the plugin is installed: `pip install -e .`

3. **JavaScript errors preventing frontend loading**
   - Check browser console in the debug test output
   - Ensure Awesomplete library loads correctly
   - Verify all DOM elements referenced in JS exist in the HTML template

#### Step 4: Adding Regression Tests

When you fix a bug, always add a unit test to prevent regression:

```python
def test_errors_handles_none_source(self):
    """Test that _errors() handles errors with None source attribute."""
    mock_error = Mock()
    mock_error.source = None  # This caused the original 500 error
    mock_error.message = "Error with None source"
    
    self.extension.ledger.errors = [mock_error]
    
    # This should not raise an AttributeError
    error_map = self.extension._errors()
    assert error_map == {}  # Should be empty since source is None
```

### Server Setup Issues

The e2e tests spawn a fava server automatically. If the server fails to start:

1. Check that no other fava processes are running: `pkill -f fava`
2. Verify the test beancount file is valid: Load it with `beancount.loader.load_file()`
3. Check port availability: The tests use random ports but conflicts can still occur

### Plugin Development Workflow

For rapid iteration during development:
1. Make changes to Python/JS/HTML files
2. Run unit tests: `python -m pytest tests/unit/ -v`
3. Test API manually with curl (as shown above)
4. Run single e2e test: `python -m pytest tests/e2e/test_frontend.py::TestFixUncategorizedFrontend::test_extension_page_loads -v -s`
5. Run full e2e suite: `python -m pytest tests/e2e/ -v`