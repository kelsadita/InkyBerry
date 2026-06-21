# InkyBerry

A custom e-ink display manager for **Raspberry Pi Zero 2 W** and the **Pimoroni Inky Impression 7.3"** (800×480, 7-color). Built as a lightweight, plugin-based alternative to InkyPi with proper button support, readable fonts, and a modular architecture.

## Features

- **Plugin system** — modular architecture, easy to add new displays
- **4-button navigation** — physical buttons for switching plugins, refreshing data, and plugin-specific actions
- **Web dashboard** — local-network UI to configure plugins, manage photos, view a live preview, control the display, and monitor the Pi (see [Web Dashboard](#web-dashboard))
- **Button debouncing** — presses during e-ink refresh (~45s) are dropped, no input queue buildup
- **Dithered grey headers** — TRMNL-inspired compact UI style
- **Screenshot mode** — render any plugin to PNG for debugging without hardware
- **Systemd services** — display manager and web dashboard run on boot, auto-restart on failure

## Plugins

### Stock Tracker

- Configurable ticker groups (D button cycles between them)
- Price, change%, day high/low, previous close
- Intraday sparkline chart (green/red) with time labels
- Market status indicator (Pre-Market / After Hours / Markets Closed)
- Auto-refreshes every 15 minutes

### Weather

- Current conditions with weather icons ([Erik Flowers Weather Icons](https://erikflowers.github.io/weather-icons/))
- Today's high/low, feels like, precipitation %, wind speed
- 24-hour temperature graph with rain probability fill and current time marker
- 7-day forecast (tomorrow onward) with icons, hi/lo temps, rain %
- Auto-detects location from IP (configurable override available)
- Data from [Open-Meteo API](https://open-meteo.com/) (free, no API key required)
- D button toggles °C ↔ °F

### Photo Frame

- Displays photos from a local directory
- Supports JPG, PNG, HEIC/HEIF, BMP, GIF, WebP
- Blurred background fill for letterboxed photos (no ugly white bars)
- Auto-advances on a configurable timer
- C/D buttons for previous/next photo

## Hardware

- **Raspberry Pi Zero 2 W** (or any Pi with GPIO)
- **Pimoroni Inky Impression 7.3"** — 800×480, 7-color e-ink display
- 4 GPIO buttons on pins 5, 6, 16, 24 (built into the Inky Impression)

## Button Mapping

| Button   | Default         | Stocks            | Weather      | Photos         |
| -------- | --------------- | ----------------- | ------------ | -------------- |
| A        | Previous plugin | ←                 | ←            | ←              |
| B        | Next plugin     | →                 | →            | →              |
| C        | Refresh         | Refresh data      | Refresh data | Previous photo |
| D        | Info overlay    | Next ticker group | Toggle °C/°F | Next photo     |
| D (hold) | System info     | System info       | System info  | System info    |

Buttons are handled per-plugin. Each plugin can override C and D for custom behavior while A and B always navigate between plugins.

## Web Dashboard

A lightweight Flask dashboard for configuring and controlling InkyBerry from any browser on your local network — no need to SSH in or edit `config.yaml` by hand. It's designed to run comfortably on the Pi Zero 2 W's 512MB of RAM.

`setup.sh` installs it as its own systemd service (`inkyberry-web`), so once setup completes you can open:

```
http://inkyberry.local:5000
```

Pages:

- **Home** — live PNG preview of what's on the panel, with a download button and one-click refresh. Simulate any of the A/B/C/D button presses remotely.
- **Plugins** — enable/disable and reorder active plugins, edit per-plugin settings, and switch the display to a specific plugin.
- **Photos** — upload, browse (with thumbnails), and delete photo-frame images; trigger a rescan.
- **Schedule** — define time-based rules for the display.
- **Display** — adjust resolution, rotation, and color saturation.
- **Buttons** — remap the GPIO pin assignments for the four buttons.
- **System** — live stats (CPU, memory, temperature, disk, uptime, IP), start/stop/restart the display service, and reboot or shut down the Pi.
- **Logs** — live-streaming `journalctl` output via Server-Sent Events, with level filtering.

The dashboard talks to the running display process over signals (`SIGUSR1`) and a small command file, so refreshes, plugin switches, and button presses take effect immediately. Service control, reboot, and shutdown rely on the passwordless sudoers rules that `setup.sh` installs (`/etc/sudoers.d/inkyberry`).

> **Note:** the dashboard binds to `0.0.0.0:5000` and has no authentication — only expose it on a trusted local network, not the public internet.

## Quick Start

### 1. Clone the repo

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/inkyberry.git
cd inkyberry
```

### 2. Run the setup script

```bash
chmod +x setup.sh install_fonts.sh
./setup.sh
./install_fonts.sh
```

This installs all dependencies, sets up the Python virtual environment, installs the weather icons font, and creates two systemd services (`inkyberry` for the display and `inkyberry-web` for the dashboard). Display text fonts live in `fonts/` and are selectable from plugin settings.

### 3. Install HEIC/HEIF support (optional, for iPhone photos)

```bash
source ~/.virtualenvs/pimoroni/bin/activate
pip install pillow-heif
```

### 4. Edit configuration

```bash
nano ~/inkyberry/config.yaml
```

Customize your stock tickers and preferences. Weather location is auto-detected from IP, and timezone is read from the Pi's system clock.

### 5. Start InkyBerry

```bash
sudo systemctl start inkyberry        # the e-ink display manager
sudo systemctl start inkyberry-web    # the web dashboard
```

Then open **http://inkyberry.local:5000** in a browser on the same network to manage everything from the [web dashboard](#web-dashboard).

## Configuration

All settings live in `config.yaml`:

```yaml
stocks:
  ticker_groups:
    - [AAPL, MSFT, AMZN, GOOG]
    - [META, NFLX, INTC, AMD]
  refresh_interval: 900 # 15 min

weather:
  # Location auto-detected from IP. To override, uncomment:
  # latitude: 40.7128
  # longitude: -74.0060
  # location_name: "New York, NY"
  units: imperial
  refresh_interval: 1800 # 30 min

photo_frame:
  directory: "~/inkyberry/photos"
  interval: 60 # seconds between auto-advance
  shuffle: true
```

Timezone is always read from the Pi's system clock:

```bash
sudo timedatectl set-timezone America/Los_Angeles
```

## Adding Photos

Copy photos from your computer via SCP:

```bash
# Single file
scp photo.jpg pi@inkyberry.local:~/inkyberry/photos/

# Entire folder
rsync -av ~/Pictures/MyAlbum/ pi@inkyberry.local:~/inkyberry/photos/
```

Press C or D to trigger a rescan and start displaying. Photos also auto-detect on the next advance cycle (every 60s by default).

## Screenshots

Render any plugin to PNG without hardware:

```bash
source ~/.virtualenvs/pimoroni/bin/activate
cd ~/inkyberry

python main.py --screenshot            # active plugin
python main.py --screenshot stocks     # specific plugin
python main.py --screenshot weather
python main.py --screenshot photo_frame
```

Saves to `~/inkyberry/screenshot.png`.

## Service Management

Display manager:

```bash
sudo systemctl start inkyberry      # start
sudo systemctl stop inkyberry       # stop (required before manual runs)
sudo systemctl restart inkyberry    # restart
sudo systemctl status inkyberry     # check status
journalctl -u inkyberry -f          # live logs
```

Web dashboard:

```bash
sudo systemctl start inkyberry-web      # start
sudo systemctl stop inkyberry-web       # stop
sudo systemctl restart inkyberry-web    # restart
sudo systemctl status inkyberry-web     # check status
journalctl -u inkyberry-web -f          # live logs
```

**Important:** Always stop the `inkyberry` service before running the display manually, otherwise you'll get a `GPIO busy` error.

## Project Structure

```
inkyberry/
├── main.py              # Boot loop, plugin manager, scheduler, button dispatch
├── display.py           # Inky + Pillow wrapper, dithered headers, font helpers
├── buttons.py           # GPIO button handler (gpiozero) with long-press
├── config.yaml          # All settings
├── geolocation.py       # IP-based location auto-detect with config fallback
├── setup.sh             # One-command installer
├── install_fonts.sh     # Downloads weather icons font
├── fonts/               # Display text fonts + Weather Icons
├── photos/              # Photo frame images (add your own)
├── web/                 # Web dashboard
│   ├── server.py        # Flask API server (config, plugins, photos, system, logs)
│   └── static/
│       └── index.html   # Single-page dashboard UI
└── plugins/
    ├── base_plugin.py   # Abstract base class
    ├── stocks/
    │   └── plugin.py    # Stock tracker with sparkline charts
    ├── weather/
    │   └── plugin.py    # Weather with 24hr graph + 7-day forecast
    └── photo_frame/
        └── plugin.py    # Photo slideshow with blurred backgrounds
```

## Writing a Plugin

Create a new directory under `plugins/` with a `plugin.py`:

```python
from plugins.base_plugin import BasePlugin
from display import BLACK, WHITE

class Plugin(BasePlugin):
    name = "My Plugin"
    description = "Does something cool"

    def __init__(self, config, display):
        super().__init__(config, display)
        self.refresh_interval = 300  # auto-refresh every 5 min

    def update_data(self):
        """Fetch data from an API or other source."""
        pass

    def on_button(self, button):
        """Handle C/D buttons. Return True if handled."""
        return False

    def render(self):
        """Return a PIL Image (800x480, palette mode P or RGB)."""
        img, draw = self.display.create_canvas(bg_color=WHITE)
        header_h = self.display.draw_header(
            draw, "MY PLUGIN", compact=True, img=img
        )
        draw.text((20, header_h + 20), "Hello, e-ink!", fill=BLACK,
                  font=self.display.get_font(32, bold=True))
        return img
```

Then add it to `config.yaml`:

```yaml
plugins:
  active:
    - stocks
    - weather
    - photo_frame
    - my_plugin # directory name under plugins/
```

## Dependencies

- Python 3.11+
- [inky](https://github.com/pimoroni/inky) — Pimoroni display driver
- [Pillow](https://python-pillow.org/) — image rendering
- [yfinance](https://github.com/ranaroussi/yfinance) — stock data
- [requests](https://docs.python-requests.org/) — HTTP client (weather API)
- [gpiozero](https://gpiozero.readthedocs.io/) — GPIO button handling
- [Flask](https://flask.palletsprojects.com/) — web dashboard server
- [PyYAML](https://pyyaml.org/) — config parsing
- [pytz](https://pytz.sourceforge.net/) — timezone handling
- [pillow-heif](https://github.com/bigcat88/pillow_heif) — HEIC/HEIF support (optional)
