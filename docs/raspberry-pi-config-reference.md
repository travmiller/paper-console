# Raspberry Pi Configuration Documentation Reference

**Source:** https://www.raspberrypi.com/documentation/computers/configuration.html

This file serves as a reference for Raspberry Pi configuration topics that are relevant to this project.

## Key Configuration Topics

### System Configuration
- **config.txt**: Low-level system configuration file
- **cmdline.txt**: Kernel command line parameters
- **raspi-config**: Interactive configuration tool
- **Network Configuration**: WiFi, Ethernet, hostname settings
- **Serial Port Configuration**: GPIO serial port setup (relevant for thermal printer)

### Hardware Configuration
- GPIO pin configuration
- Serial/UART configuration
- I2C/SPI interfaces
- Camera module setup
- Display configuration

### System Services
- Systemd service configuration
- NetworkManager setup
- Avahi (mDNS) configuration
- Nginx configuration

## Project-Specific References

### Serial Port Setup (for Thermal Printer)
The project uses `/dev/serial0` (GPIO serial) for the thermal printer. Key configuration:
- Disable serial console: `raspi-config nonint do_serial_cons 1`
- Enable serial hardware: `raspi-config nonint do_serial_hw 0`
- User must be in `dialout` group: `usermod -a -G dialout $USER`

### Network Configuration
- Hostname setup via `hostnamectl`
- NetworkManager for WiFi AP mode
- Avahi for mDNS (`.local` hostname resolution)

### System Services
- Systemd service for the application
- Nginx reverse proxy configuration
- Service auto-start on boot

## Quick Links

- [Full Configuration Documentation](https://www.raspberrypi.com/documentation/computers/configuration.html)
- [config.txt Options](https://www.raspberrypi.com/documentation/computers/config_txt.html)
- [Raspberry Pi OS Documentation](https://www.raspberrypi.com/documentation/computers/os.html)

## Notes

This documentation is maintained as a reference. For the most up-to-date information, always refer to the official Raspberry Pi documentation website.
