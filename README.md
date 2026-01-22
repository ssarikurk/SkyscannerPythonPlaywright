# Skyscanner Flight Scraper with Playwright

A Python-based web automation tool that scrapes flight information from Skyscanner, handles CAPTCHA verification, and sends results via email.

## Features

- **Automated Flight Search**: Automatically searches for flights on Skyscanner based on CSV input
- **CAPTCHA Handling**: Implements sophisticated CAPTCHA detection and verification with human-like interactions
- **Modal Management**: Automatically detects and closes popup dialogs and modals
- **Human-like Behavior**: Simulates natural mouse movements and delays to avoid detection
- **Batch Processing**: Processes multiple flight searches from a CSV file
- **Email Reports**: Generates HTML reports and sends them via Gmail SMTP
- **Session Management**: Uses persistent browser contexts with automatic cleanup

## Requirements

- Python 3.7+
- Playwright (with Chromium browser)
- pytest
- python-dotenv
- smtplib (built-in)

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd SkyscannerPythonPlaywright
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers**:
   ```bash
   playwright install chromium
   ```

## Configuration

### Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Gmail SMTP Configuration
FROM_MAIL=your-email@gmail.com
TO_MAIL=recipient@gmail.com
APP_PASSWORD=your-gmail-app-password
```

**Note**: For Gmail SMTP, use an [App Password](https://support.google.com/accounts/answer/185833) rather than your regular password.

### Input CSV Format

Create a `flightInfoList.csv` file with flight search parameters:

```csv
From,To,DepartDate
esb,fra,25.03.2024
fra,esb,28.03.2024
ist,fra,01.04.2024
```

**Date Format**: DD.MM.YYYY

## Usage

### Run the Flight Scraper

```bash
pytest ./skyscanner_test.py::test_skyscanner -sv --headed
```

**Flags**:
- `-sv`: Verbose output
- `--headed`: Show browser window during execution

### What the Script Does

1. Launches a persistent Chromium browser context
2. Navigates to Skyscanner and passes any CAPTCHA challenges
3. Reads flight search parameters from `flightInfoList.csv`
4. For each flight search:
   - Navigates to the search URL
   - Closes any modal dialogs
   - Scrapes flight information (airline, price, provider)
   - Collects ticket details
5. Generates an HTML report with all flight information
6. Sends the report via email to the configured recipient

### Output Files

- **flightDetails.html**: HTML table containing all scraped flight information
- **debug_captcha_page.html**: Debug file (if CAPTCHA verification encounters issues)

## Project Structure

```
SkyscannerPythonPlaywright/
├── README.md                  # This file
├── skyscanner_test.py         # Main test script
├── flightInfoList.csv         # Input flight search parameters
├── flightDetails.html         # Generated HTML report
├── .env                       # Environment variables (not included in repo)
└── __pycache__/               # Python cache directory
```

## Key Functions

### `test_skyscanner(browserSkyscanner)`
Main test function that orchestrates the entire scraping workflow.

### `passCaptcha(url, current_url, page)`
Detects and handles Skyscanner CAPTCHA challenges using human-like mouse movements and timing.

### `checkAndCloseModal(page)`
Identifies and closes various popup dialogs and modals that appear during navigation.

### `simulate_human_mouse_movement(page, start_x, start_y, end_x, end_y)`
Creates natural-looking mouse movements using Bezier curves to avoid bot detection.

### `convertDateFormat(dateStr)`
Converts date format from DD.MM.YYYY to YYMMDD for Skyscanner URLs.

### `send_html_email(message, subject, to_address, from_address)`
Sends HTML-formatted emails via Gmail SMTP with proper HTML/plain text fallback.

## Important Notes

- The script uses `headless=False` to show the browser window, allowing observation of CAPTCHA handling
- Test environments are cleaned up automatically after each session
- The tool respects Skyscanner's user interaction patterns with appropriate delays
- CAPTCHA handling requires manual verification in some cases

## Troubleshooting

### CAPTCHA Not Detected
If the CAPTCHA handling fails, check `debug_captcha_page.html` for the page structure and update selectors accordingly.

### Email Not Sending
- Verify `FROM_MAIL` and `APP_PASSWORD` are correct in `.env`
- Ensure Gmail 2-Factor Authentication is enabled and an App Password is generated
- Check that `TO_MAIL` is a valid email address

### Modal/Dialog Issues
If popups aren't closing properly, the script will retry with multiple selector strategies including:
- Accessibility labels
- CSS class patterns
- Button text content

## Dependencies

See `requirements.txt` for a complete list of dependencies.

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]

## Support

For issues or questions, please [create an issue](link-to-issues) or contact the project maintainer.
