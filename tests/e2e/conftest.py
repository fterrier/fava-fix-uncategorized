import pytest
import tempfile
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def test_ledger():
    """Create a temporary beancount file for testing."""
    ledger_content = '''plugin "fava_fix_uncategorized"

1990-01-01 open Assets:Checking
1990-01-01 open Expenses:Family:Unclassified
1990-01-01 open Expenses:Family:Groceries
1990-01-01 open Expenses:Family:Restaurants
1990-01-01 open Income:Salary

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
        return Path(f.name)


@pytest.fixture(scope="session")
def fava_server(test_ledger):
    """Start a Fava server for testing."""
    import socket
    
    # Find an available port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        port = s.getsockname()[1]
    
    # Start Fava server
    process = subprocess.Popen([
        'fava', 
        str(test_ledger),
        '--port', str(port),
        '--host', '127.0.0.1'
    ])
    
    # Wait a moment for server to start
    import time
    time.sleep(2)
    
    yield f"http://127.0.0.1:{port}"
    
    # Cleanup
    process.terminate()
    process.wait()
    test_ledger.unlink()  # Delete the temporary file


@pytest.fixture(scope="session")
def browser():
    """Create a browser instance for testing."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    """Create a new page for each test."""
    page = browser.new_page()
    yield page
    page.close()