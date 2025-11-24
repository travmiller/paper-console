# Project: PC-1 (Paper Console)

**A dedicated, offline-first device that curates the digital world into a physical artifact.**
*Status: V1 Prototype (Digital Twin Complete)*
*Date: November 2025*

---

## 1. Project Vision
To build a "Calm Technology" appliance that respects user attention.
* **No Screens:** Output is physical thermal paper.
* **No Subscriptions:** User-owned API keys or local algorithms.
* **Heirloom Quality:** Walnut, Brass, and archival-grade paper.
* **Universal Channels:** Fully configurable channels (News, Email, Webhooks, Games, Notes, Calendar).

---

## 2. Quick Start (Digital Twin)
You can run the entire system on your PC without the hardware to test logic and the "printer" output.

### A. Backend (The Brain)
The Python FastAPI server handles logic, data fetching, and "Virtual Hardware" drivers.

```bash
# 1. Activate Virtual Env (Windows)
source venv/Scripts/activate

# 2. Run Server (Auto-reloads on code changes)
uvicorn app.main:app --reload --port 8000
```
*   **API Docs / Control Panel:** [http://localhost:8000/docs](http://localhost:8000/docs)
*   **Mock Output:** Watch your Terminal window. The "Printer" writes text there.

### B. Frontend (The Settings App)
A React app for configuring the device (City, Timezone, Channels, etc).

```bash
cd web
npm install  # First time only
npm run dev
```
*   **URL:** [http://localhost:5173](http://localhost:5173)
*   **Features:** 
  * Location search and configuration
  * Channel type selection and configuration
  * Channel reordering (up/down arrows)
  * Dynamic list management (RSS feeds, Calendar sources)
  * Reset all settings to defaults

---

## 3. Configuration
Configuration is handled entirely via the **Frontend UI** (React web interface).

### Global Settings
*   **Location:** City name, Latitude, Longitude, Timezone (with search functionality).
*   **Time Format:** 12-hour (AM/PM) or 24-hour format.

### Channel Configuration
*   **8 Channel Positions:** Each position (1-8) represents a slot on the rotary dial.
*   **Modular System:** Channels are containers. You can assign **multiple modules** to a single channel (e.g., "News" followed by "Weather" followed by a "Sudoku" puzzle).
*   **Reordering:** 
    *   **Channels:** Use the Up/Down arrows next to the Channel title to swap entire channels.
    *   **Modules:** Use the arrow buttons within a channel card to change the print order of modules.
*   **Scheduled Printing:** Click the clock icon on any channel to schedule it to print automatically at specific times of day, regardless of the dial position.

### Module Types
Each module is an independent instance with its own configuration:

1.  **News API:**
    *   **Features:** Prints Top Headlines from NewsAPI.
    *   **Config:** NewsAPI Key.
2.  **RSS Feeds:**
    *   **Features:** Prints articles from custom RSS feeds.
    *   **Config:** Multiple RSS Feed URLs.
3.  **Weather:**
    *   **Features:** Prints current weather + forecast (OpenMeteo).
    *   **Config:** Uses Global Location.
4.  **Email Inbox:**
    *   **Features:** Connects via IMAP to print unread emails.
    *   **Config:** Host, User, App Password, Auto-Poll Interval.
5.  **Sudoku:**
    *   **Features:** Generates a Sudoku puzzle.
    *   **Config:** Difficulty Level (Medium/Hard).
6.  **Astronomy:**
    *   **Features:** Prints Sunrise, Sunset, Moon Phase.
    *   **Config:** Uses Global Location.
7.  **Calendar:**
    *   **Features:** Fetches and prints upcoming events from iCal calendars.
    *   **Config:** Multiple named calendar sources (Label + iCal URL), Days to Show.
8.  **Webhook:**
    *   **Features:** Makes a GET/POST request to any URL and prints the result.
    *   **Config:** Label, URL, Method, Headers, Body, JSON Path.
9.  **Text / Note:**
    *   **Features:** Prints a static text note.
    *   **Config:** Label, Content.

### Universal Channel System
The system uses a fully modular paradigm.
*   **Settings File:** `config.json` (Managed automatically).
*   **Auto-Save:** All changes to settings, modules, and channel assignments are saved instantly.
*   **Reset:** You can reset to factory defaults via the UI "Reset All Settings" button.
*   **Default Channels:** The system comes pre-configured with example channels to demonstrate the capabilities.

### Environment Variables
Legacy secrets can still be set in `.env`, but UI configuration is preferred.

```ini
# Optional Defaults (overridden by UI settings)
NEWS_API_KEY=your_key_here
OPENWEATHER_API_KEY=your_key_here
EMAIL_USER=paperconsole.test@gmail.com
EMAIL_PW=app_password
```

---

## 4. Software Architecture & Modules
**Philosophy:** Local-First, API-Agnostic, Privacy-Centric.

### Tech Stack
* **OS:** Raspberry Pi OS Lite (64-bit).
* **Backend:** Python 3.12 + FastAPI (API & Logic).
* **Frontend:** React + Vite + Tailwind CSS v4 (Hosted locally on the Pi for Settings).
* **Database:** `config.json` (JSON file for settings persistence).
* **Key Dependencies:** 
  * `icalendar` & `python-dateutil` (Calendar parsing)
  * `feedparser` (RSS feed parsing)
  * `pytz` (Timezone handling)
  * `requests` (HTTP requests for APIs/webhooks)

### Available Modules
The device has 8 positions on the rotary dial. Each channel can contain multiple modules executed in order.

1.  **News API:**
    *   **Features:** Prints Top Headlines from NewsAPI.
    *   **Config:** NewsAPI Key.
    *   **Sources:** NewsAPI (top headlines).
2.  **RSS Feeds:**
    *   **Features:** Prints articles from custom RSS feeds.
    *   **Config:** Multiple RSS Feed URLs.
    *   **Sources:** Custom RSS feeds (unlimited).
3.  **Weather:**
    *   **Features:** Prints current weather + forecast (OpenMeteo).
    *   **Config:** None (Uses Global Location from General settings).
    *   **Sources:** Open-Meteo API (no key required).
4.  **Email Inbox:**
    *   **Features:** Connects via IMAP to print unread emails.
    *   **Config:** Host, User, App Password, Polling Interval.
    *   **Auto-Poll:** Checks for new emails at configurable intervals (default 60s), regardless of dial position.
5.  **Sudoku:**
    *   **Features:** Generates a Sudoku puzzle (Medium/Hard difficulty).
    *   **Config:** Difficulty Level.
6.  **Astronomy:**
    *   **Features:** Prints Sunrise, Sunset, Moon Phase/Illumination for the current location.
    *   **Config:** None (Uses Global Location).
7.  **Calendar:**
    *   **Features:** Fetches and prints upcoming events from iCal calendars (Google Calendar, Apple Calendar, etc.).
    *   **Config:** Multiple named calendar sources (Label + iCal URL), Days to Show (1-7 days ahead).
    *   **Sources:** Supports both public and secret iCal URLs. Can merge multiple calendars.
    *   **Features:** Handles recurring events, timezone-aware scheduling, event expansion.
8.  **Webhook:**
    *   **Features:** Makes a GET/POST request to any URL and prints the result.
    *   **Config:** Label, URL, Method (GET/POST), Headers (JSON), Body (optional), JSON Path (for extraction).
    *   **Use Cases:** Dad Jokes, Random Facts, IoT Status, Home Assistant triggers, Custom APIs.
9.  **Text / Note:**
    *   **Features:** Prints a static text note stored in memory.
    *   **Config:** Label, Content (multi-line text).
    *   **Use Case:** Wifi Password for guests, To-Do list, Quick reference notes.

---

## 5. Hardware Architecture
### Core Electronics
* **Compute:** Raspberry Pi Zero 2 W (Headless).
* **Printer:** Mini Thermal Receipt Printer (QR204 58mm TTL/USB).
* **Power:** 5V 4A Power Supply (Barrel Jack) -> Green Terminal Adapter.
* **Storage:** SanDisk Ultra 32GB (A1 Class).

### The Physical Interface (Console Layout)
* **Top Deck:**
    *   **Channel Selector:** 1-Pole 8-Position Rotary Switch.
    *   **Trigger:** Brass Momentary Push Button.
*   **Front Face:**
    *   **Output:** Brass Bezel Slot (Paper Ejection).
    *   **Indicator:** None (Silent). Feedback is mechanical/auditory.

---

## 6. Moving to Hardware (Next Steps)
To turn this code into a physical device:

### 1. Hardware List
*   **Compute:** Raspberry Pi Zero 2 W.
*   **Printer:** QR204 / CSN-A2 (TTL Serial).
*   **Input:** 1-Pole 8-Position Rotary Switch + Momentary Button.

### 2. Driver Swap
Currently, `app/drivers/printer_mock.py` just `print()`s to console.
You need to:
1.  Install `pyserial`.
2.  Create `app/drivers/printer_serial.py`.
3.  Update `app/main.py` to use the real driver when running on Linux.

```python
# Example Serial Driver Logic
import serial
class PrinterDriver:
    def __init__(self):
        self.ser = serial.Serial('/dev/serial0', 19200)
    def print_text(self, text):
        self.ser.write(text.encode('gbk'))
        self.ser.write(b'\n')
```

### 3. GPIO Integration
Replace `app/drivers/dial_mock.py` with `RPi.GPIO` logic to read the physical pins of the rotary switch.

---

## 7. Troubleshooting
*   **NewsAPI Returns 0 Articles:** Check if your API key is valid and if you are on the free tier (sometimes aggressive caching returns empty lists). Try adding RSS feeds as an alternative.
*   **RSS Feeds Not Working:** Ensure RSS feed URLs are valid and accessible. Check the terminal for `[NEWS] Fetching X RSS feeds...` messages.
*   **Email Auth Failed:** Ensure you are using a **Google App Password**, not your main password. Ensure 2FA is enabled.
*   **Calendar Not Showing Events:** Verify your iCal URL is correct (works in browser). Check that events exist in the date range (default is 2 days). Check terminal for `[CALENDAR]` error messages.
*   **Weather Wrong:** Check `config.json` Lat/Long via the UI location search feature.
*   **Printer Width:** Adjust `printer_width` in config if lines wrap unexpectedly (standard is 32 chars).
*   **Channel Not Triggering:** Verify the channel type is set correctly in the UI and that the config is saved.

---

## 8. Directory Structure
```text
/pc-1
├── /app
│   ├── main.py            # Entry point & Event Router
│   ├── config.py          # Pydantic Models & Settings Manager
│   ├── /drivers
│   │   ├── printer_mock.py# Console "Printer"
│   │   ├── dial_mock.py   # Virtual Rotary Switch
│   ├── /modules
│   │   ├── news.py        # NewsAPI Logic
│   │   ├── rss.py         # RSS Feed Logic
│   │   ├── weather.py     # Weather Logic (Open-Meteo)
│   │   ├── astronomy.py   # Local Astronomy Logic
│   │   ├── email_client.py# IMAP Logic
│   │   ├── sudoku.py      # Sudoku Logic
│   │   ├── webhook.py     # Generic API/Webhook Logic
│   │   ├── text.py        # Static Text Logic
│   │   ├── calendar.py    # iCal Calendar Parsing Logic
│   └── /web               # React + Vite + Tailwind CSS Frontend
├── /scripts
│   └── install.sh         # One-step setup script (TODO)
├── config.json            # User Settings (GitIgnore)
├── .env                   # Secrets (GitIgnore)
├── requirements.txt       # Python dependencies
└── readme.md              # This file
```
