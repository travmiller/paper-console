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

## 5. Hardware Setup Guide

### Prerequisites
1. **Raspberry Pi Zero 2 W** with Raspberry Pi OS Lite installed
2. **Thermal Printer** (QR204/CSN-A2 or compatible 58mm TTL/USB thermal printer)
3. **1-Pole 8-Position Rotary Switch**
4. **Momentary Push Button** (optional, for manual trigger)
5. **Power Supply:** 5V 4A Power Supply (Barrel Jack) -> Green Terminal Adapter.

### 1. Install Dependencies
On your Raspberry Pi, install the required Python packages:

```bash
pip install -r requirements.txt
```
This will install `pyserial` and `RPi.GPIO` along with other dependencies.

### 2. Enable Serial Interface
Enable the serial interface on your Raspberry Pi:
```bash
sudo raspi-config
```
Navigate to:
- **Interface Options** → **Serial Port**
- Enable serial port hardware
- Disable serial login shell (if prompted)

Reboot after making changes:
```bash
sudo reboot
```

### 3. Connect the Thermal Printer
#### USB Connection
If your printer connects via USB:
1. Connect the printer to a USB port on the Raspberry Pi
2. The device should appear as `/dev/ttyUSB0` or `/dev/ttyACM0`
3. Check available serial devices: `ls -l /dev/tty*`

#### TTL Serial Connection
If your printer uses TTL serial:
1. Connect:
   - **VCC** → 5V (Pin 2 or 4)
   - **GND** → Ground (Pin 6 or any GND)
   - **RX** → GPIO 14 (TXD, Pin 8) - **Note:** You may need a level shifter if printer is 3.3V
   - **TX** → GPIO 15 (RXD, Pin 9)
2. Enable serial in `raspi-config` (see step 2)
3. The device will appear as `/dev/serial0` or `/dev/ttyAMA0`

#### Configure Printer Port (if needed)
If your printer is on a different port, you can modify `app/drivers/printer_serial.py`:
```python
printer = PrinterDriver(width=32, port="/dev/ttyUSB0", baudrate=19200)
```

### 4. Connect the Rotary Switch
The 1-pole 8-position rotary switch needs to be connected to GPIO pins:

#### Wiring
- **Common terminal** → GND
- **Position 1** → GPIO 5 (Pin 29)
- **Position 2** → GPIO 6 (Pin 31)
- **Position 3** → GPIO 13 (Pin 33)
- **Position 4** → GPIO 19 (Pin 35)
- **Position 5** → GPIO 26 (Pin 37)
- **Position 6** → GPIO 16 (Pin 36)
- **Position 7** → GPIO 20 (Pin 38)
- **Position 8** → GPIO 21 (Pin 40)

**Note:** These are the default GPIO pins. You can customize them in `app/drivers/dial_gpio.py`.

### 5. Connect the Push Button (Optional)
The push button can be connected to trigger the current channel:

#### Wiring
- **One terminal** → GPIO 18 (Pin 12)
- **Other terminal** → GND
- Add a 10kΩ pull-up resistor between GPIO 18 and 3.3V (or use internal pull-up)

### 6. Network & Auto-Start Setup
To make the device accessible via `http://pc-1.local` (without a port number) and ensure it starts automatically on boot:

1.  **Copy the setup script to your Pi:**
    (You can do this via scp or just create the file on the Pi)

2.  **Run the setup script:**
    ```bash
    cd /home/pi/paper-console
    chmod +x scripts/setup_pi.sh
    sudo scripts/setup_pi.sh
    ```

3.  **Follow the prompts:**
    - Enter your desired hostname (default: `pc-1`)
    - The script will install Nginx (web proxy), Avahi (mDNS), and configure the systemd service.

4.  **Access the device:**
    Open your browser and go to `http://pc-1.local` (or whatever hostname you chose).

---

## 6. Troubleshooting
*   **Printer Not Working:**
    *   Check serial port: `ls -l /dev/tty*`
    *   Check permissions: `sudo usermod -a -G dialout $USER`
    *   Check baud rate matches driver (default 19200).
*   **Dial Not Reading Positions:**
    *   Check wiring: Ensure common terminal is connected to GND.
    *   Test GPIO pins with a simple python script.
*   **NewsAPI Returns 0 Articles:** Check if your API key is valid and if you are on the free tier.
*   **RSS Feeds Not Working:** Ensure RSS feed URLs are valid and accessible.
*   **Email Auth Failed:** Ensure you are using a **Google App Password**, not your main password. Ensure 2FA is enabled.
*   **Calendar Not Showing Events:** Verify your iCal URL is correct. Check that events exist in the date range.
*   **Weather Wrong:** Check `config.json` Lat/Long via the UI location search feature.
*   **Printer Width:** Adjust `printer_width` in config if lines wrap unexpectedly (standard is 32 chars).
*   **Channel Not Triggering:** Verify the channel type is set correctly in the UI and that the config is saved.

---

## 7. GPIO Pin Reference
For Raspberry Pi Zero 2 W (40-pin header):
```
    3.3V  [1]  [2]  5V
   GPIO2  [3]  [4]  5V
   GPIO3  [5]  [6]  GND
   GPIO4  [7]  [8]  GPIO14 (TXD)
     GND  [9]  [10] GPIO15 (RXD)
  GPIO17 [11]  [12] GPIO18 (BTN)
  GPIO27 [13]  [14] GND
  GPIO22 [15]  [16] GPIO23
    3.3V [17]  [18] GPIO24
  GPIO10 [19]  [20] GND
   GPIO9 [21]  [22] GPIO25
  GPIO11 [23]  [24] GPIO8
     GND [25]  [26] GPIO7
   GPIO0 [27]  [28] GPIO1
   GPIO5 [29]  [30] GND
   GPIO6 [31]  [32] GPIO12
  GPIO13 [33]  [34] GND
  GPIO19 [35]  [36] GPIO16
  GPIO26 [37]  [38] GPIO20
   GND   [39]  [40] GPIO21
```

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
│   └── setup_pi.sh        # Setup script (Hostname, Nginx, Systemd)
├── config.json            # User Settings (GitIgnore)
├── .env                   # Secrets (GitIgnore)
├── requirements.txt       # Python dependencies
└── readme.md              # This file
```
