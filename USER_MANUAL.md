# PC-1 User Manual

Welcome to your **PC-1 Paper Console**! 

This device is a physical interface for your digital life. It prints news, weather, puzzles, games, emails, calendars, quotes, historical events, and more on thermal receipt paper—no screens, no subscriptions, just simple physical information on demand.

---

## 1. Getting Started

### Power On
1. Plug the power adapter into the back of the PC-1.
2. Plug the other end into a wall outlet.
3. Wait about **60 seconds**. The device will start up.
4. Once ready, it will automatically print a **Welcome Message** with further instructions.

### Connecting to WiFi
To get news and weather, the PC-1 needs internet access.

1. On your phone or computer, look for a WiFi network named **`PC-1-Hotspot`**.
2. Connect to it.
3. A "Sign In" page should pop up automatically. If it doesn't, open a browser and type **`http://10.0.0.1`**.
4. Select your home WiFi network from the list and enter your password.
5. The device will save the settings, reboot, and print a confirmation when connected.

---

## 2. Using the Console

The PC-1 is designed to be simple. There are only two controls:

### The Dial (Channels)
The rotary dial has **8 positions** (Channels 1 through 8). 
* Turn the dial to select what you want to print.
* You can customize what each channel does in the settings (see Section 3).

### The Button
* **Press Once:** Prints the content for the currently selected channel.
* **Press During Printing:** **Cancels** the current print job immediately.
* **Hold for 15 Seconds:** Performs a **Factory Reset** (erases all settings and WiFi). Use this only if you need to completely wipe the device.

---

## 3. Customizing Your Content

You can change what prints on each channel using the web interface.

1. Make sure your computer/phone is on the same WiFi as the PC-1.
2. Open a web browser and go to: **[http://pc-1.local](http://pc-1.local)**
   *(Note: On some Android devices, you may need to use the IP address printed on the startup slip, e.g., `http://192.168.1.x`)*

### The Dashboard
* **Channels Tab:** Shows your 8 dial positions. You can drag and drop modules here.
* **Settings Tab:** Set your location (for Weather/Astronomy) and time format.

### Adding Content
1. Click on a Channel (e.g., "Channel 1").
2. Click **"Add Module"**.
3. Choose a module type:
   * **Weather:** Prints current forecast for your location.
   * **News:** Top headlines (requires a free API key).
   * **RSS:** Follow your favorite blogs or podcasts.
   * **Email:** Prints unread emails from your inbox.
   * **Sudoku:** Generates a fresh puzzle (Medium or Hard difficulty).
   * **Maze:** Generates a printable maze puzzle.
   * **Astronomy:** Sunrise, sunset, and moon phase information.
   * **Calendar:** Prints your daily agenda (supports Google/Apple Calendar).
   * **Webhook:** Connect to any API (Dad Jokes, Random Facts, IoT devices, etc.).
   * **Text:** Store a static note (like a WiFi password or shopping list).
   * **Checklist:** Create a printable checklist with checkboxes.
   * **Quotes:** Prints random inspirational quotes.
   * **History:** Prints "On This Day" historical events.

### Scheduling (Alarm Clock)
You can make the PC-1 print automatically at a specific time (e.g., print the news every morning at 8:00 AM).
* Click the **Clock Icon** next to any channel to set a schedule.

---

## 4. Changing Paper

The PC-1 uses standard **58mm Thermal Receipt Paper** (widely available online or at office supply stores).

1. Lift the top brass lever to open the paper hatch.
2. Remove the old core.
3. Place the new roll inside with the **paper feeding from the bottom** (curl facing down).
4. Pull a small amount of paper out.
5. Close the lid until it clicks.
6. Tear off the excess paper.

**Note:** Thermal paper only prints on one side. If it comes out blank, the roll is likely upside down.

---

## 5. Troubleshooting

### Device prints "Connect to WiFi" repeatedly
This means the device cannot reach the internet.
* Check if your internet is down.
* If you changed your WiFi password, hold the button for 15 seconds to Factory Reset, then reconnect.

### Prints are blank or faint
* Ensure the paper is loaded correctly (shiny side facing the print head).
* Check that the power supply is securely connected.

### Paper Jam
1. Open the hatch using the lever.
2. Gently pull out any crumpled paper.
3. **Do not** use sharp objects near the print head (the black bar inside).

### Factory Reset
If the device becomes unresponsive or you want to sell it:
1. Unplug the device.
2. Plug it back in.
3. Press and **HOLD** the main button for **15 seconds**.
4. The device will delete all settings and restart in "Hotspot Mode".
