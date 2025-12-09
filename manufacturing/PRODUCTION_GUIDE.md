# PC-1 Production Imaging Guide

**Target: 20+ units/month with minimal repetition**

---

## Overview

Instead of setting up each Pi from scratch, we create ONE "golden image" with everything pre-installed, then clone it to all SD cards.

**Time comparison:**
- Manual setup per Pi: ~15-20 minutes
- Flash golden image: ~3-5 minutes per card

---

## One-Time Setup: Create the Golden Image

### Step 1: Prepare a Reference Pi

1. **Flash fresh Raspberry Pi OS Lite (64-bit)** to an SD card using Raspberry Pi Imager
   - Enable SSH
   - Set username/password: `pi` / `raspberry` (or your preference)
   - Set locale/timezone
   - Skip WiFi (not needed - device creates its own AP)

2. **Boot the Pi** and SSH in:
   ```bash
   ssh pi@raspberrypi.local
   ```

3. **Clone the project:**
   ```bash
   cd ~
   git clone https://github.com/YOUR_USERNAME/paper-console.git
   cd paper-console
   ```

4. **Run the setup script:**
   ```bash
   chmod +x scripts/setup_pi.sh
   sudo scripts/setup_pi.sh
   ```
   - Accept default hostname `pc-1` (or customize)
   - Wait for all dependencies to install

5. **Verify it works:**
   - Reboot: `sudo reboot`
   - Connect to WiFi hotspot: `PC-1-Setup-XXXX` / `setup1234`
   - Open `http://10.42.0.1` in browser
   - Verify the UI loads

### Step 2: Prepare for Imaging

Run the golden image preparation script:

```bash
cd ~/paper-console
chmod +x scripts/prepare_golden_image.sh
./scripts/prepare_golden_image.sh
```

This script:
- Resets `config.json` to factory defaults
- Clears all logs and history
- Removes saved WiFi networks
- Resets machine-id (each Pi gets unique ID on first boot)
- Optionally zeros free space for better compression

### Step 3: Create the Image

1. **Shut down the Pi:**
   ```bash
   sudo shutdown -h now
   ```

2. **Remove SD card** and insert into your computer

3. **Create image file:**

   **Windows (Win32DiskImager):**
   - Download: https://sourceforge.net/projects/win32diskimager/
   - Select the SD card drive
   - Choose output file: `C:\Code\paper-console\manufacturing\pc1-golden.img`
   - Click "Read"

   **Windows (Raspberry Pi Imager - Backup):**
   - Actually, Pi Imager can't read back. Use Win32DiskImager.

   **Linux/Mac:**
   ```bash
   # Find your SD card (usually /dev/sdX or /dev/mmcblkX)
   lsblk
   
   # Create image (replace sdX with your device)
   sudo dd if=/dev/sdX of=pc1-golden.img bs=4M status=progress
   
   # Compress (recommended - reduces ~4GB to ~1GB)
   gzip pc1-golden.img
   ```

4. **Store the image:**
   - Keep `pc1-golden.img.gz` in this `manufacturing/` folder
   - Back it up to cloud storage!

---

## Daily Production: Flash SD Cards

### Option A: Windows (Recommended)

1. Double-click `manufacturing/flash_sd.bat`
2. Insert SD card
3. Raspberry Pi Imager opens
4. Select: 
   - **Device:** Raspberry Pi Zero 2 W
   - **OS:** Use custom → `manufacturing/pc1-golden.img.gz`
   - **Storage:** Your SD card
5. Click **WRITE** (skip all customization - it's already done!)
6. Eject, insert next card, repeat

### Option B: Command Line (Linux/Mac)

```bash
# Flash directly with dd
gunzip -c pc1-golden.img.gz | sudo dd of=/dev/sdX bs=4M status=progress

# Or use Raspberry Pi Imager CLI
rpi-imager --cli pc1-golden.img.gz /dev/sdX
```

### Option C: Parallel Flashing (High Volume)

For 20+ units, consider:

1. **USB Hub + Multiple Card Readers:**
   - 4-port USB 3.0 hub
   - 4x SD card readers
   - Flash 4 cards simultaneously using different terminal windows

2. **SD Card Duplicator (Hardware):**
   - ~$100-200 for 1-to-7 or 1-to-11 duplicators
   - Insert golden SD, press button, done
   - Example: StarTech 1:7 SD Duplicator

---

## Quality Checklist Per Unit

Quick test before shipping (< 1 minute):

- [ ] Insert SD card into Pi
- [ ] Power on
- [ ] Wait ~30 seconds for boot
- [ ] Check phone/laptop for WiFi network `PC-1-Setup-XXXX`
- [ ] Connect, open `http://10.42.0.1`
- [ ] Verify UI loads
- [ ] Power off, package

---

## Updating the Golden Image

When you push updates to the codebase:

1. Boot a Pi with the current golden image
2. Connect to your WiFi: `sudo nmcli device wifi connect "YourSSID" password "YourPassword"`
3. Pull updates:
   ```bash
   cd ~/paper-console
   git pull
   pip install -r requirements.txt  # if deps changed
   sudo systemctl restart pc-1.service
   ```
4. Test everything works
5. Run `prepare_golden_image.sh`
6. Create new image (increment version: `pc1-golden-v2.img.gz`)

---

## Troubleshooting

**Pi won't boot:**
- Re-flash the SD card
- Try a different SD card (some are flaky)

**WiFi hotspot doesn't appear:**
- Wait 60 seconds after boot
- Check if LED activity (should blink during boot)
- May need to re-image

**Image too large:**
- Run the "zero free space" option in prepare script
- Use `gzip -9` for maximum compression
- Consider smaller SD cards (8GB is plenty)

---

## Hardware Checklist (Before Imaging Day)

- [ ] SD cards (Samsung EVO or SanDisk - avoid cheap cards)
- [ ] Fast SD card reader (USB 3.0)
- [ ] Golden image file backed up
- [ ] Raspberry Pi Imager installed

---

## Time Estimates

| Task | Time |
|------|------|
| Initial golden image setup | 30-45 min (one-time) |
| Flash one SD card | 3-5 min |
| Flash 20 cards sequentially | 60-100 min |
| Flash 20 cards (4 parallel) | 20-30 min |
| Flash 20 cards (hardware duplicator) | 10-15 min |
| Quick test per unit | 1 min |

---

**Pro tip:** Put on a podcast, queue up 4 SD cards, and batch through them. The process becomes almost meditative once you have the rhythm down! 🎧

