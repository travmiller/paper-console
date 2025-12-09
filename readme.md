# PC-1 (Paper Console 1)

**A tiny customizable printer that prints news, weather, emails, games, and other content on demand.**
*Status: V1 Prototype*
*Date: November 2025*

---

* **No Screens:** Output is physical thermal paper.
* **No Subscriptions:** User-owned API keys or local algorithms.
* **Heirloom Quality:** Walnut, Brass, and archival-grade paper.
* **Universal Channels:** Fully configurable channels (News, Email, Webhooks, Games, Notes, Calendar).

![PC-1 Front View](images/pc-1_front.jpg)
*Front view showing the brass rotary dial, push button, and thermal paper output*

---

## 1. Quick Start (Software)

Run the entire system on your PC without hardware to test logic and see "printer" output in the terminal.

**Backend:**
```bash
# Linux / macOS / Git Bash
./run.sh

# Windows CMD
run.bat
```
* **API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **Mock Output:** Watch your Terminal window. The "Printer" writes text there.

**Frontend (Settings UI):**
```bash
cd web
npm install
npm run dev
```
* **URL:** [http://localhost:5173](http://localhost:5173)

---

## 2. Software Installation

### Development Environment

1. **Install Python Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   This installs `pyserial`, `RPi.GPIO`, and other dependencies.

2. **Run the Server:**
   ```bash
   ./run.sh  # or run.bat on Windows test
   ```

### Raspberry Pi Deployment

1. **Install Python Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run Setup Script:**
   ```bash
   cd ~/paper-console
   chmod +x manufacturing/scripts/setup_pi.sh
   sudo manufacturing/scripts/setup_pi.sh
   ```
   The script will:
   - Set hostname (default: `pc-1`)
   - Install Nginx (web proxy) and Avahi (mDNS)
   - Configure systemd service
   - Add user to `lp` group for printer access

3. **Access the Device:**
   Open your browser and go to `http://pc-1.local` (or your chosen hostname).

---

## 3. Configuration

Configuration is handled entirely via the **Web UI** at `http://pc-1.local` (or `http://localhost:8000` if running locally).

### Global Settings
* **Location:** City name, Latitude, Longitude, Timezone (with search functionality)
* **Time Format:** 12-hour (AM/PM) or 24-hour format

### Channel System
* **8 Channel Positions:** Each position (1-8) represents a slot on the rotary dial
* **Modular System:** Channels are containers. You can assign **multiple modules** to a single channel (e.g., "News" followed by "Weather" followed by "Sudoku")
* **Reordering:** 
  * **Channels:** Use Up/Down arrows next to Channel title to swap entire channels
  * **Modules:** Use arrow buttons within a channel card to change print order
* **Scheduled Printing:** Click the clock icon on any channel to schedule automatic printing at specific times

### Module Types

Each module is an independent instance with its own configuration. See [Architecture & Modules](#4-architecture--modules) for detailed information.

Available modules: **News API**, **RSS Feeds**, **Weather**, **Email Inbox**, **Sudoku**, **Maze**, **Astronomy**, **Calendar**, **Webhook**, **Text / Note**, **Checklist**, **Quotes**, **History**.

### Settings Storage
* **Settings File:** `config.json` (auto-saved, gitignored)
* **Reset:** "Reset All Settings" button restores factory defaults

---

## 4. Architecture & Modules

### Tech Stack
* **OS:** Raspberry Pi OS Lite (64-bit)
* **Backend:** Python 3.12 + FastAPI
* **Frontend:** React + Vite + Tailwind CSS v4

### Directory Structure
```
paper-console/
├── app/
│   ├── main.py            # Entry point & Event Router
│   ├── config.py          # Pydantic Models & Settings Manager
│   ├── drivers/
│   │   ├── printer_serial.py  # Hardware printer driver
│   │   ├── printer_mock.py    # Console "Printer" (dev)
│   │   ├── dial_gpio.py       # Hardware dial driver
│   │   └── dial_mock.py       # Virtual Rotary Switch (dev)
│   ├── modules/
│   │   ├── news.py        # NewsAPI Logic
│   │   ├── rss.py         # RSS Feed Logic
│   │   ├── weather.py     # Weather Logic (Open-Meteo)
│   │   ├── astronomy.py  # Local Astronomy Logic
│   │   ├── email_client.py# IMAP Logic
│   │   ├── sudoku.py      # Sudoku Logic
│   │   ├── maze.py        # Maze Generation Logic
│   │   ├── webhook.py     # Generic API/Webhook Logic
│   │   ├── text.py        # Static Text Logic
│   │   ├── calendar.py    # iCal Calendar Parsing Logic
│   │   ├── checklist.py   # Checklist Logic
│   │   ├── quotes.py      # Quotes Logic
│   │   └── history.py     # Historical Events Logic
│   └── web/               # React + Vite + Tailwind CSS Frontend
├── manufacturing/
│   └── scripts/
│       └── setup_pi.sh        # Setup script (Hostname, Nginx, Systemd)
├── run.sh                 # Development server launcher
├── run.bat                # Windows development launcher
├── requirements.txt       # Python dependencies
└── readme.md              # This file
```

### Module Details

**News API:**
* Sources: NewsAPI (top headlines)
* Requires: NewsAPI key

**RSS Feeds:**
* Sources: Custom RSS feeds (unlimited)
* Supports: Any valid RSS feed URL

**Weather:**
* Sources: Open-Meteo API (no key required)
* Uses: Global location from settings

**Email Inbox:**
* Protocol: IMAP
* Auto-Poll: Configurable interval (default 30s)
* Features: Prints unread emails automatically

**Sudoku:**
* Difficulty: Medium or Hard
* Algorithm: Backtracking solver with random generation

**Maze:**
* Difficulty: Medium or Hard
* Algorithm: Recursive backtracking maze generation
* Features: Printable maze with start/end markers

**Astronomy:**
* Features: Sunrise, Sunset, Moon Phase/Illumination
* Uses: Global location from settings

**Calendar:**
* Sources: iCal URLs (Google Calendar, Apple Calendar, etc.)
* Features: 
  * Supports public and secret iCal URLs
  * Merges multiple calendars
  * Handles recurring events
  * Timezone-aware scheduling
  * Event expansion (1-7 days ahead)

**Webhook:**
* Methods: GET or POST
* Features: Custom headers, JSON body, JSON path extraction
* Use Cases: Dad Jokes, Random Facts, IoT Status, Home Assistant triggers, Custom APIs

**Text / Note:**
* Features: Static multi-line text storage
* Use Cases: WiFi passwords, to-do lists, quick reference notes

**Checklist:**
* Features: Printable checklist with checkboxes
* Use Cases: Daily tasks, shopping lists, reminders
* Format: Each item prints with a checkbox `[ ]` for manual checking

**Quotes:**
* Sources: Curated database of ~5,000 quotes
* Features: Random inspirational quotes
* Database: Auto-downloads from GitHub if not present

**History:**
* Sources: Historical events database
* Features: "On This Day" historical events
* Database: Auto-downloads from GitHub if not present

---

## 5. Hardware Setup

### Prerequisites
1. **Raspberry Pi Zero 2 W** with Raspberry Pi OS Lite installed
2. **Thermal Printer** (QR204/CSN-A2 or compatible 58mm TTL thermal printer)
3. **1-Pole 8-Position Rotary Switch**
4. **Momentary Push Button** (x2)
5. **Power Supply:** 5V 5A Power Supply (Barrel Jack) -> Terminal Adapter

### Complete Wiring Tables

#### Thermal Printer (TTL Serial)
| Printer Wire | Pi GPIO | Physical Pin |
|--------------|---------|--------------|
| RX | GPIO 14 (TXD) | Pin 8 |
| TX | GPIO 15 (RXD) | Pin 10 |
| DTR | GPIO 18 | Pin 12 |
| GND | Ground | Pin 14 |
| VCC | 5V | Pin 2 or 4 |

#### Main Button (Print/Cancel)
| Signal | GPIO | Physical Pin |
|--------|------|--------------|
| GND | Ground | Pin 20 |
| Signal | GPIO 25 | Pin 22 |

#### Power Button (Shutdown/Wake)
| Signal | GPIO | Physical Pin |
|--------|------|--------------|
| Signal | GPIO 3 | Pin 5 |
| GND | Ground | Pin 6 |

#### Rotary Dial (8-Position)
| Position | GPIO | Physical Pin |
|----------|------|--------------|
| Common (GND) | Ground | Pin 39 |
| Position 1 | GPIO 5 | Pin 29 |
| Position 2 | GPIO 6 | Pin 31 |
| Position 3 | GPIO 13 | Pin 33 |
| Position 4 | GPIO 19 | Pin 35 |
| Position 5 | GPIO 26 | Pin 37 |
| Position 6 | GPIO 16 | Pin 36 |
| Position 7 | GPIO 20 | Pin 38 |
| Position 8 | GPIO 21 | Pin 40 |

### Visual Pin Layout
```
                    3V3  (1)  (2)  5V [Printer VCC]
                  GPIO2  (3)  (4)  5V
      [Power Btn] GPIO3  (5)  (6)  GND [Power Btn]
                  GPIO4  (7)  (8)  GPIO14/TXD [→ Printer RX]
                    GND  (9)  (10) GPIO15/RXD [← Printer TX]
                 GPIO17 (11)  (12) GPIO18 [Printer DTR]
                 GPIO27 (13)  (14) GND    [Printer GND]
                 GPIO22 (15)  (16) GPIO23
                    3V3 (17)  (18) GPIO24
                 GPIO10 (19)  (20) GND    [Main Btn GND]
                  GPIO9 (21)  (22) GPIO25 [Main Btn]
                 GPIO11 (23)  (24) GPIO8
                    GND (25)  (26) GPIO7
                  GPIO0 (27)  (28) GPIO1
       [Dial P1] GPIO5  (29)  (30) GND
       [Dial P2] GPIO6  (31)  (32) GPIO12
       [Dial P3] GPIO13 (33)  (34) GND
       [Dial P4] GPIO19 (35)  (36) GPIO16 [Dial P6]
       [Dial P5] GPIO26 (37)  (38) GPIO20 [Dial P7]
   [Dial Common] GND    (39)  (40) GPIO21 [Dial P8]
```

### Thermal Printer

**TTL Serial Connection:**
1. Wire according to table above
2. Enable serial in `raspi-config` → Interface Options → Serial Port
3. Device appears as `/dev/serial0`

**Note:** The system auto-detects serial ports in this order:
1. `/dev/serial0` (GPIO Serial - primary)
2. `/dev/ttyUSB0` (USB-to-Serial adapter)
3. `/dev/ttyUSB1` (USB-to-Serial adapter)

### Power Supply

**Shared Power Setup:**
- Use a 5V 5A power supply with a terminal adapter
- Split power in parallel: one branch to Pi, one branch to Printer
- Connect data lines separately
- **Important:** Do not power printer through Pi GPIO pins (insufficient current for printer)

---

## 6. Troubleshooting

### Printer Issues
* **Device Not Found:**
  * Check if `/dev/serial0` exists: `ls -l /dev/serial*`
  * Verify serial is enabled: `raspi-config` → Interface Options → Serial Port
  * Check if console is disabled on serial: `sudo raspi-config` → Advanced → Serial
* **Permission Denied:**
  * Ensure user is in `dialout` group: `groups`
  * Add user: `sudo usermod -a -G dialout $USER` (then log out/in)
* **Nothing Prints:**
  * Verify power supply is adequate (5A minimum)
  * Confirm printer is connected to correct GPIO pins using the wiring table above
  * Make sure the printer is powered on (indicator lights as expected)
  * Check for error/status lights or messages on the printer itself (if available)
  * Test the printer with a simple echo command: `echo "test" > /dev/serial0`
  * Check service logs: `sudo journalctl -u pc-1.service -f`
  * Confirm no other application is holding the serial port open (use `lsof /dev/serial0`)

### Service Issues
  * **Restart Loop:**
  * Service uses `run.sh` to handle port conflicts automatically
  * Restart: `sudo systemctl restart pc-1.service`
  * Check logs: `sudo journalctl -u pc-1.service -f`
  * **Port Already in Use:**
  * `run.sh` automatically kills zombie processes
  * If persistent, reboot: `sudo reboot`

### Module-Specific Issues
* **NewsAPI Returns 0 Articles:** Check if API key is valid and on free tier
* **RSS Feeds Not Working:** Ensure RSS feed URLs are valid and accessible
* **Email Auth Failed:** Use a **Google App Password**, not your main password. Ensure 2FA is enabled
* **Calendar Not Showing Events:** Verify iCal URL is correct. Check that events exist in the date range
* **Weather Wrong:** Check `config.json` Lat/Long via UI location search feature
* **Channel Not Triggering:** Verify channel has modules assigned and config is saved

---
