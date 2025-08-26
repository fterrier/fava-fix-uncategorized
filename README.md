# Fava Fix Uncategorized

A Fava plugin that provides a user-friendly interface to categorize uncategorized transactions in beancount files.

## Features

- List all transactions with uncategorized postings
- Interactive web interface to categorize expenses and income
- Bulk save functionality
- Filter to show only uncategorized transactions
- Account autocompletion for faster data entry
- Real-time validation of posting formats

## Installation

### From GitHub

```bash
pip install git+https://github.com/fterrier/fava-fix-uncategorized.git
```

### For Development

```bash
git clone https://github.com/fterrier/fava-fix-uncategorized.git
cd fava-fix-uncategorized
pip install -e .[dev]
```

## Usage

1. Add the plugin to your beancount file:

```beancount
plugin "fava_fix_uncategorized"
```

2. Start Fava as usual:

```bash
fava your-ledger.beancount
```

3. Navigate to the "Fix Uncategorized" extension in the Fava web interface.

## Development

### Running Tests

```bash
# Unit tests
pytest tests/unit/

# E2E tests (requires Playwright)
pytest tests/e2e/
```

### Setting up Development Environment

```bash
pip install -e .[dev]
```

## License

GPL-2.0 License. See COPYING file for details.