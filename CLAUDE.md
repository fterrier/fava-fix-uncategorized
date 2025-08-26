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

## Testing

Both unit tests and end-to-end tests should be implemented:
- Unit tests for backend logic (posting validation, transaction processing)
- E2E tests for frontend functionality using Playwright