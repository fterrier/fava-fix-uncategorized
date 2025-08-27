import pytest
import tempfile
import subprocess
import socket
import time
import os
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def test_ledger():
    """Create a temporary beancount file for testing."""
    ledger_content = '''1980-05-12 custom "fava-extension" "fava_fix_uncategorized"

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
    """Start a Fava server with the plugin enabled for testing."""
    
    # Find available port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        port = s.getsockname()[1]
    
    # Set up environment with plugin source in Python path
    plugin_src_path = Path(__file__).parent.parent.parent / "src"
    env = os.environ.copy()
    env['PYTHONPATH'] = str(plugin_src_path) + ":" + env.get('PYTHONPATH', '')
    
    print(f"Starting Fava on http://127.0.0.1:{port}")
    
    # Start fava server
    process = subprocess.Popen(
        ['fava', str(test_ledger), '--port', str(port), '--host', '127.0.0.1'],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for server to start
    time.sleep(5)
    
    try:
        # Check if server is running
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise RuntimeError(f"Fava server failed to start. stdout: {stdout.decode()}, stderr: {stderr.decode()}")
        
        # Follow redirect to get the correct base URL
        response = requests.get(f"http://127.0.0.1:{port}", timeout=5, allow_redirects=False)
        if response.status_code in [301, 302]:
            redirect_url = response.headers.get('Location', '')
            # Extract ledger base from redirect (e.g. /beancount/income_statement/ -> beancount)
            ledger_base = redirect_url.strip('/').split('/')[0]
            base_url = f"http://127.0.0.1:{port}/{ledger_base}"
        else:
            # Fallback
            base_url = f"http://127.0.0.1:{port}/beancount"
        
        print(f"Using base URL: {base_url}")
        yield base_url
        
    finally:
        # Cleanup
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        test_ledger.unlink()


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