# Skyscanner Ticket Finding Handbook

> A practical guide to how this Playwright-based Skyscanner scraper works — covering the full automation flow, CAPTCHA bypass, price comparison, and how to adapt it for other Skyscanner projects.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Full Automation Flow](#2-full-automation-flow)
3. [CSV-Driven Route Configuration](#3-csv-driven-route-configuration)
4. [Bypassing the Human Check (CAPTCHA)](#4-bypassing-the-human-check-captcha)
5. [Scraping Ticket Data](#5-scraping-ticket-data)
6. [Price Comparison Engine](#6-price-comparison-engine)
7. [Email Reporting](#7-email-reporting)
8. [How to Adapt for Another Project](#8-how-to-adapt-for-another-project)
9. [Convenience Scripts & Commands](#9-convenience-scripts--commands)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   skyscanner_test.py (913 LOC)              │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Browser Setup │  │ CAPTCHA      │  │ Price Comparison │  │
│  │ (fixture)     │─▶│ Bypass       │─▶│ Engine           │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│         │                   │                   │            │
│         ▼                   ▼                   ▼            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Modal Handler│  │ Ticket       │  │ HTML Report +    │  │
│  │              │  │ Scraper      │  │ Email via SMTP   │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Single-file architecture** — all logic lives in `skyscanner_test.py`. No classes, no src dir, just top-level functions + one pytest test.

**Stack:** Python 3.11+, Playwright (Chromium, headed mode), pytest, BeautifulSoup4, Gmail SMTP/IMAP.

---

## 2. Full Automation Flow

```
pytest launches test_skyscanner()
    │
    ├── [1] Read old email via IMAP ──────────────────────────┐
    │      read_last_sent_flight_email()                      │
    │      → parses HTML table from last "Flight Details"     │
    │      → builds old_flights_dict {key: old_price}         │
    │                                                         │
    ├── [2] browserSkyscanner fixture                         │
    │      → persistent Chromium context                      │
    │      → temp profile at /tmp/skyscanner_{uuid}           │
    │      → --disable-blink-features=AutomationControlled    │
    │                                                         │
    ├── [3] FOR EACH ROW IN flightInfoList.csv:               │
    │      │                                                  │
    │      ├─ Build Skyscanner URL                            │
    │      │  www.skyscanner.com.tr/tasima/ucak-bileti/       │
    │      │  {from}/{to}/{YYMMDD}/?...&stops=!oneStop,...    │
    │      │                                                  │
    │      ├─ page.goto(url)                                  │
    │      ├─ wait 4s                                         │
    │      ├─ checkAndCloseModal()   ← popup killer           │
    │      ├─ passCaptcha()          ← HUMAN CHECK BYPASS     │
    │      ├─ Find tickets via FlightsTicket_container         │
    │      ├─ FOR EACH ticket:                                │
    │      │   ├─ Scrape price, airline, departure/arrival,   │
    │      │   │   duration, layovers                         │
    │      │   ├─ Build compare_key                           │
    │      │   ├─ Look up old price from old_flights_dict     │
    │      │   ├─ calculate_diff() → color-coded diff         │
    │      │   └─ Append to flightList                        │
    │      │                                                  │
    ├── [4] Generate HTML report (flightDetails.html)         │
    │      → styled table with green/red price diffs          │
    │                                                         │
    └── [5] send_html_email()                                 │
           → Gmail SMTP SSL (port 465)                       │
           → sends report to configured recipient
```

---

## 3. CSV-Driven Route Configuration

Two CSV files act as the route database:

**`flightInfoList.csv`** (primary, 4 routes):
```csv
from,to,date,provider
MUC,ASR,19.07.2026,ucuzabilet
MUC,ASR,20.07.2026,ucuzabilet
...
```

**`flightInfoList2.csv`** (secondary, 30 routes — alternate file, not wired in active test).

The code reads `flightInfoList.csv`, iterates rows, builds Skyscanner URLs:

```python
url = f"https://www.skyscanner.com.tr/tasima/ucak-bileti/{fromStr}/{toStr}/{departDate}/?adultsv2=1&cabinclass=economy&childrenv2=&ref=home&rtn=0&preferdirects=false&outboundaltsenabled=false&inboundaltsenabled=false&stops=!oneStop,!twoPlusStops"
```

**Key URL parameters:**
| Param | Value | Meaning |
|-------|-------|---------|
| `adultsv2` | 1 | 1 adult |
| `cabinclass` | economy | Economy class |
| `rtn` | 0 | One-way (no return) |
| `stops` | `!oneStop,!twoPlusStops` | **Direct flights only** (no layovers) |

Date conversion: `DD.MM.YYYY` → `YYMMDD` via `convertDateFormat()`.

---

## 4. Bypassing the Human Check (CAPTCHA)

This is the **core challenge** of the project. The function `passCaptcha()` implements a multi-layer anti-detection system.

### 4.1 Browser Fingerprint Tampering (Layer 1)

In the `browserSkyscanner` fixture (`skyscanner_test.py:30-34`):

```python
context = playwright.chromium.launch_persistent_context(
    user_data_dir=temp_profile,
    headless=False,
    args=["--disable-blink-features=AutomationControlled"]
)
```

- `--disable-blink-features=AutomationControlled` removes the `navigator.webdriver` flag that normally identifies Playwright as automation.
- Uses a **fresh temp profile** each run (`/tmp/skyscanner_{uuid}`) — no cookie persistence, no fingerprint buildup.
- `headless=False` — the browser is always visible. Skyscanner detects headless Chrome more aggressively.

**Note:** `playwright-stealth` is installed (`requirements.txt`) but **never imported**. To enable it, add:
```python
from playwright_stealth import stealth_sync
# after page creation:
stealth_sync(page)
```

### 4.2 CAPTCHA Detection (Layer 2)

`passCaptcha()` (`skyscanner_test.py:341-506`) detects CAPTCHA via three strategies:

```python
# Strategy A: URL check
if "captcha" in current_url.lower():

# Strategy B: Frame inspection
for i, frame in enumerate(frames):
    if "captcha" in frame.url.lower() or "verify" in frame.url.lower():
        captcha_frame = frame

# Strategy C: Frame locator fallback (CSS selectors)
captcha_frame = page.frame_locator(
    'iframe[title*="human"], iframe[title*="verification"], iframe[title*="challenge"]'
).content_frame
```

If all fail, it falls back to `page.frames[-1]` (the last frame).

### 4.3 Automated Button Interaction (Layer 3 — the bypass itself)

Once the CAPTCHA frame is identified:

1. **Scroll** to page 1/3 height
2. **Find the button** via multiple selectors:
   - XPath: `//*[contains(text(), "Press") or contains(text(), "press") or contains(text(), "Hold")]`
   - CSS: `[aria-label*="Press"]`, `button:has-text("Press")`, `[class*="captcha"]`, `[class*="verify"]`, `[class*="challenge"]`
3. **Bezier mouse movement** to the button:
   - Moves from viewport center → button center
   - Quadratic Bezier curve with 20 steps (50ms delay each)
   - Uses `page.mouse.move()` with a slight upward arc
4. **Hold-and-wait pattern** (the key technique for Cloudflare Turnstile / hCaptcha):
   - `page.mouse.down()` — presses and holds
   - Holds for **12 seconds**
   - Every 100ms, jitters mouse ±2px randomly (emulating human micro-tremors)
   - Releases with `page.mouse.up()`
5. **Wait 3 seconds** for the CAPTCHA to resolve

### 4.4 What CAPTCHA Type Is This For?

The "Press" + "Hold" pattern with 12-second hold strongly indicates **Cloudflare Turnstile** (the "Press and Hold" widget) or a similar challenge. This does NOT work for:
- Image recognition (reCAPTCHA v2)
- Audio CAPTCHAs
- Cloudflare JS "5-second shield" challenges

### 4.5 Modal Management (Layer 4 — supporting layer)

`checkAndCloseModal()` (`skyscanner_test.py:90-138`) uses four strategies:

```python
# 1. Accessibility labels
close_labels = ["İletişim kutusunu kapatın", "Close dialog", "Close"]

# 2. CSS class patterns
"button[class*='CloseButton_close_button_container']"
"button[class*='BpkCloseButton']"

# 3. "Devam Et" button (payment screen)
page.get_by_role("button", name="Devam Et")

# 4. Force-click with force=True to bypass overlay elements
```

### 4.6 Gaps in the Current Anti-Detection

| Gap | Impact | Fix |
|-----|--------|-----|
| `playwright-stealth` not imported | Missing 20+ stealth JS injections | `stealth_sync(page)` |
| No viewport set | Default 800×600 = bot signal | `context.set_viewport_size(...)` |
| No user-agent override | Chromium default UA | `page.set_extra_http_headers(...)` |
| No geolocation/timezone spoofing | Turkish site may detect | `context.add_init_script(...)` |
| `simulate_human_mouse_movement()` unused | Better cubic-Bezier exists but not wired | Call it from `passCaptcha` |
| No retry logic | Single attempt, then navigates away | Wrap in 3-5 retry loop |

---

## 5. Scraping Ticket Data

After bypassing CAPTCHA, ticket scraping uses Playwright selectors (`skyscanner_test.py:755-823`):

```python
# Ticket container (current Skyscanner UI)
ticket_container = page.locator("div[class*='FlightsTicket_container']")

# Per-ticket scraping:
price_text     = ticket.locator("div[class*='Price_mainPrice']").inner_text()
airline        = ticket.locator("div[class*='LegDetails_container'] img").get_attribute("alt")
departure_time = ticket.locator("div[class*='RoutePartial_routePartialDepart'] > span").inner_text()
arrival_time   = ticket.locator("div[class*='RoutePartial_routePartialArrive'] > span").inner_text()
flight_duration = ticket.locator("div[class*='Stops_stopsContainer'] > span").inner_text()
aktarma        = ticket.locator("div[class*='Stops_stopsRow'] > span").inner_text()
```

All text fields are normalized via `normalize_flight_field()` which strips whitespace, newlines, and lowercases.

**Important:** Skyscanner frequently changes CSS class names. The `class*=` partial-match selectors help survive minor changes, but a full UI redesign will break all selectors. When that happens, inspect the page and update the class patterns.

---

## 6. Price Comparison Engine

### 6.1 Old Price Retrieval

`read_last_sent_flight_email()` (`skyscanner_test.py:525-607`) connects to Gmail via IMAP:

1. IMAP SSL to `imap.gmail.com`
2. Selects the Gönderilmiş (Sent) folder (`"[Gmail]/G&APY-nderilmi&AV8- Postalar"`)
3. Searches for `TO "gsarikurk@gmail.com" SUBJECT "Flight Details Report"`
4. Gets the **latest matching email**
5. Extracts HTML body
6. Parses via `parse_flight_table()` — BeautifulSoup reads `<table>` headers and rows
7. Returns a dict with all flights and their prices

### 6.2 Diff Calculation

```python
compare_key = f"{fromStr}-{toStr}-{row[2]}-{departure_time}-{arrival_time}-{airline}".lower().strip()
old_price_str = old_flights_dict.get(compare_key, "N/A")
diff_text, diff_val, status_color = calculate_diff(price_text, old_price_str)
```

`calculate_diff()` (`skyscanner_test.py:508-523`):
- Computes `((new - old) / old) * 100`
- **Green** (`#d4edda`) = price dropped
- **Red** (`#f8d7da`) = price increased
- **White** = no change or first record

### 6.3 The Unique Flight Key

```
{from}-{to}-{departDate}-{departure_time}-{arrival_time}-{airline}
```

Example: `muc-asr-19.07.2026-09:00-12:30-sunexpress`

This key must match exactly between old and new runs for comparison to work. Small formatting differences (whitespace, casing, +1 day markers) are normalized away.

---

## 7. Email Reporting

### 7.1 Sending (`send_html_email`, line 304)

```python
host = "smtp.gmail.com"
port = 465  # SSL
with smtplib.SMTP_SSL(host, port) as server:
    server.login(username, app_password)
    server.send_message(msg)
```

- Uses Gmail **App Password** (not regular password) — requires 2FA enabled
- Detects if content is HTML by checking for `<html`, `<table`, or leading `<`
- Sends multi-part: plain text fallback + HTML alternative

### 7.2 HTML Report Structure (line 831)

```
┌────────┬──────┬────────────┬────────┬──────────┬──────────┬──────────┬─────────┬───────────┬────────┬──────────┬─────────┐
│  From  │  To  │ Depart Date│Depart T│ Arrival T│ Duration │ Aktarma │ Airline │ Old Price │  Price │   Diff   │   URL   │
├────────┼──────┼────────────┼────────┼──────────┼──────────┼──────────┼─────────┼───────────┼────────┼──────────┼─────────┤
│  MUC   │ ASR  │ 19.07.2026 │ 09:00  │  12:30   │   3h30m  │  Direkt  │ SunExp  │  8.480 TL │8.200 TL│-280 TL   │[Bilete] │
│        │      │            │        │          │          │          │         │           │        │(-3.3%)   │  Git    │
└────────┴──────┴────────────┴────────┴──────────┴──────────┴──────────┴─────────┴───────────┴────────┴──────────┴─────────┘
```

Rows are color-coded: green for price drops, red for increases.

### 7.3 .env Configuration

```env
APP_PASSWORD=your_gmail_app_password
FROM_MAIL=suleymansarikurk@gmail.com
TO_MAIL=gsarikurk@gmail.com
```

---

## 8. How to Adapt for Another Project

If you want to use this pattern in a different Skyscanner project (or any similar travel/flight site):

### 8.1 Files to Copy As-Is

| File | Purpose |
|------|---------|
| `skyscanner_test.py` | All logic — copy and modify |
| `requirements.txt` | Dependencies |
| `.env.sample` | Credential template |
| `flightInfoList.csv` | Route configuration (customize) |

### 8.2 Things You'll Need to Change

1. **URL template** (line 746) — Skyscanner might change URL structure, or you might target a different locale/domain
2. **CSS selectors** (lines 757, 765, 767, 772, 778, 784, 791) — Skyscanner's class names change frequently. Inspect the page and update partial class matches
3. **CAPTCHA selectors** (lines 374, 381-389) — button text, iframe titles, and challenge type may differ
4. **IMAP folder name** (line 532) — non-English Gmail uses UTF-7 encoded folder names. Turkish: `[Gmail]/G&APY-nderilmi&AV8- Postalar`, English: `[Gmail]/Sent Mail`
5. **Email search criteria** (line 543) — match your report subject line
6. **Email to/from addresses** in `.env`

### 8.3 If Skyscanner Updates Their UI (Selector Breaking)

When CSS class names change, you'll get empty ticket counts. Fix:

```bash
# Run with headed mode and watch the browser
pytest ./skyscanner_test.py::test_skyscanner -sv --headed
```

Then in Chrome DevTools on the Skyscanner page:
- Inspect a ticket card → find a stable selector
- Update the partial class pattern in `page.locator("div[class*='NEW_CLASS_NAME']")`

### 8.4 Improving Reliability Checklist

- [ ] Import and call `stealth_sync(page)` from `playwright-stealth`
- [ ] Set `page.set_viewport_size({"width": 1920, "height": 1080})`
- [ ] Set a real user-agent: `page.set_extra_http_headers({"User-Agent": "..."})`
- [ ] Wire `simulate_human_mouse_movement()` into `passCaptcha()` instead of the inline Bezier
- [ ] Add retry loop (3 attempts) around `passCaptcha()`
- [ ] Consider `page.route()` to block unnecessary resources (images, fonts) for speed
- [ ] Add `page.wait_for_selector()` instead of `page.wait_for_timeout()` for element readiness

---

## 9. Convenience Scripts & Commands

### Run the scraper

```bash
pytest ./skyscanner_test.py::test_skyscanner -sv --headed
```

### Run with a different CSV

Edit the `open('flightInfoList.csv', ...)` line to point to `flightInfoList2.csv` or a custom file.

### Debug CAPTCHA failures

When CAPTCHA bypass fails, the script saves `debug_captcha_page.html` — inspect it to understand the page structure and update selectors.

### Quick environment setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.sample .env  # then edit .env with your credentials
```

---

> **Last updated:** June 2026  
> **Codebase:** SkyscannerPythonPlaywright (`skyscanner_test.py`, 913 lines)  
> **CAPTCHA type targeted:** Cloudflare Turnstile / Press-and-Hold challenges
