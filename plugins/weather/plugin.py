"""
InkDash Weather Plugin
Displays current weather, 24hr temperature graph, and 7-day forecast.
Uses Open-Meteo API (free, no key) and Erik Flowers Weather Icons font.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import requests
from plugins.base_plugin import BasePlugin
from display import BLACK, WHITE, GREEN, BLUE, RED, YELLOW, ORANGE
from geolocation import get_location
from datetime import datetime
from PIL import ImageFont
import pytz
import tzlocal


# Weather Icons font codepoints (from erikflowers/weather-icons)
WI = {
    "day-sunny": "\uf00d",
    "day-cloudy": "\uf002",
    "cloud": "\uf041",
    "cloudy": "\uf013",
    "fog": "\uf014",
    "rain": "\uf019",
    "showers": "\uf01a",
    "sprinkle": "\uf01c",
    "day-rain": "\uf008",
    "day-showers": "\uf009",
    "snow": "\uf01b",
    "day-snow": "\uf00a",
    "thunderstorm": "\uf01e",
    "sleet": "\uf0b5",
    "thermometer": "\uf055",
    "raindrop": "\uf04e",
    "strong-wind": "\uf050",
}

# WMO code -> (description, icon_key)
WMO_CODES = {
    0: ("Clear", "day-sunny"),
    1: ("Clear", "day-sunny"),
    2: ("Partly Cloudy", "day-cloudy"),
    3: ("Overcast", "cloudy"),
    45: ("Fog", "fog"),
    48: ("Fog", "fog"),
    51: ("Drizzle", "sprinkle"),
    53: ("Drizzle", "sprinkle"),
    55: ("Drizzle", "sprinkle"),
    61: ("Light Rain", "day-rain"),
    63: ("Rain", "rain"),
    65: ("Heavy Rain", "rain"),
    66: ("Freezing Rain", "sleet"),
    67: ("Freezing Rain", "sleet"),
    71: ("Light Snow", "day-snow"),
    73: ("Snow", "snow"),
    75: ("Heavy Snow", "snow"),
    77: ("Snow", "snow"),
    80: ("Showers", "day-showers"),
    81: ("Showers", "showers"),
    82: ("Heavy Showers", "showers"),
    85: ("Snow", "snow"),
    86: ("Heavy Snow", "snow"),
    95: ("Storm", "thunderstorm"),
    96: ("Storm", "thunderstorm"),
    99: ("Storm", "thunderstorm"),
}

# Path to weather-icons font (downloaded during setup)
WEATHER_ICONS_FONT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "fonts", "weathericons-regular-webfont.ttf"
)


class Plugin(BasePlugin):
    name = "Weather"
    description = "Current weather, 24hr graph, 7-day forecast"

    def __init__(self, config, display):
        super().__init__(config, display)
        weather_cfg = config.get("weather", {})
        self.lat, self.lon, self.location = get_location(config)
        self.units = weather_cfg.get("units", "metric")
        self.refresh_interval = weather_cfg.get("refresh_interval", 1800)
        self._weather_data = None
        self._wi_fonts = {}
        # Timezone: always use Pi's system timezone
        self.tz = tzlocal.get_localzone()

    def on_button(self, button):
        """D button toggles between metric and imperial units."""
        if button == "D":
            self.units = "imperial" if self.units == "metric" else "metric"
            self.logger.info(f"Switched units to: {self.units}")
            self.update_data()
            return True
        return False

    def _get_wi_font(self, size):
        """Cached weather-icons font loader."""
        if size not in self._wi_fonts:
            font_path = os.path.abspath(WEATHER_ICONS_FONT)
            if os.path.exists(font_path):
                self._wi_fonts[size] = ImageFont.truetype(font_path, size)
            else:
                self.logger.warning(f"Weather icons font not found: {font_path}")
                self._wi_fonts[size] = None
        return self._wi_fonts[size]

    def _draw_icon(self, draw, icon_key, x, y, size=40, color=BLACK):
        """Draw a weather icon at (x, y) with given size."""
        glyph = WI.get(icon_key, WI["cloud"])
        font = self._get_wi_font(size)
        if font is None:
            fallback_font = self.display.get_font(14)
            draw.text((x, y), icon_key[:6], fill=color, font=fallback_font)
            return
        draw.text((x, y), glyph, fill=color, font=font)

    def update_data(self):
        """Fetch weather data from Open-Meteo API."""
        try:
            temp_unit = "fahrenheit" if self.units == "imperial" else "celsius"
            wind_unit = "mph" if self.units == "imperial" else "kmh"
            precip_unit = "inch" if self.units == "imperial" else "mm"

            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={self.lat}&longitude={self.lon}"
                f"&current=temperature_2m,relative_humidity_2m,"
                f"apparent_temperature,weather_code,wind_speed_10m"
                f"&hourly=temperature_2m,precipitation_probability"
                f"&daily=weather_code,temperature_2m_max,temperature_2m_min,"
                f"precipitation_probability_max"
                f"&temperature_unit={temp_unit}"
                f"&wind_speed_unit={wind_unit}"
                f"&precipitation_unit={precip_unit}"
                f"&timezone=auto&forecast_days=8"
            )

            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            self._weather_data = resp.json()
            now_local = datetime.now(self.tz)
            self._last_update = now_local.strftime("%H:%M %Z")
            self.logger.info(f"Weather data fetched for {self.location}")

        except Exception as e:
            self.logger.error(f"Failed to fetch weather: {e}")

    def _draw_temp_graph(self, draw, hourly, x, y, width, height):
        """Draw today's 24hr temperature graph (00-23) with current time marker."""
        temps = hourly.get("temperature_2m", [])
        times = hourly.get("time", [])

        now = datetime.now(self.tz)
        today_str = now.strftime("%Y-%m-%d")

        # Find today's 00:00 index using date string comparison
        # (avoids timezone/DST edge cases with day/month int comparison)
        start_idx = None
        for i, t in enumerate(times):
            if t.startswith(today_str) and t.endswith("T00:00"):
                start_idx = i
                break

        if start_idx is None:
            start_idx = 0

        end_idx = min(start_idx + 24, len(temps))
        graph_temps = temps[start_idx:end_idx]
        graph_times = times[start_idx:end_idx]

        # Hourly precipitation probability for today
        precip_probs = hourly.get("precipitation_probability", [])
        graph_precip = precip_probs[start_idx:end_idx]

        # Fractional hour offset (e.g., 16:30 = 16.5)
        current_hour_frac = now.hour + now.minute / 60.0

        if len(graph_temps) < 3:
            font = self.display.get_font(14)
            draw.text((x + 10, y + height // 2), "No hourly data",
                      fill=BLACK, font=font)
            return

        time_label_h = 14
        temp_label_w = 38
        chart_x = x + temp_label_w
        chart_y = y
        chart_w = width - temp_label_w - 5
        chart_h = height - time_label_h

        data_min = min(graph_temps)
        data_max = max(graph_temps)
        padding = 10 if self.units == "imperial" else 5
        min_t = data_min - padding
        max_t = data_max + padding
        t_range = max_t - min_t

        draw.rectangle([chart_x, chart_y, chart_x + chart_w, chart_y + chart_h],
                       outline=BLACK)

        # Build sparkline points
        points = []
        step_x = chart_w / (len(graph_temps) - 1)
        for i, t in enumerate(graph_temps):
            px = chart_x + int(i * step_x)
            py = chart_y + chart_h - int((t - min_t) / t_range * chart_h)
            py = max(chart_y + 1, min(chart_y + chart_h - 1, py))
            px = max(chart_x + 1, min(chart_x + chart_w - 1, px))
            points.append((px, py))

        # Draw line in BLUE
        for i in range(len(points) - 1):
            draw.line([points[i], points[i + 1]], fill=BLUE, width=2)

        # Blue fill only where precipitation probability > 0
        baseline = chart_y + chart_h
        for i in range(len(points) - 1):
            # Check if this hour has rain chance
            rain_pct = graph_precip[i] if i < len(graph_precip) else 0
            if rain_pct <= 0:
                continue
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            for sx in range(x1, x2, 4):
                if x2 != x1:
                    frac = (sx - x1) / (x2 - x1)
                    sy = int(y1 + frac * (y2 - y1))
                else:
                    sy = y1
                draw.line([(sx, sy), (sx, baseline)], fill=BLUE, width=1)

        # Current time marker at exact fractional hour
        if 0 <= current_hour_frac < len(graph_temps):
            # Interpolate position between hour points
            hour_idx = int(current_hour_frac)
            hour_frac = current_hour_frac - hour_idx
            if hour_idx + 1 < len(points):
                cx1, cy1 = points[hour_idx]
                cx2, cy2 = points[hour_idx + 1]
                cur_x = int(cx1 + hour_frac * (cx2 - cx1))
                cur_y = int(cy1 + hour_frac * (cy2 - cy1))
            else:
                cur_x, cur_y = points[hour_idx]

            # Vertical dashed line
            for vy in range(chart_y + 1, chart_y + chart_h, 4):
                draw.line([(cur_x, vy), (cur_x, vy + 2)], fill=BLACK, width=1)

            # Dot
            r = 4
            draw.ellipse([cur_x - r, cur_y - r, cur_x + r, cur_y + r],
                         fill=BLACK, outline=BLACK)
            draw.ellipse([cur_x - 2, cur_y - 2, cur_x + 2, cur_y + 2],
                         fill=WHITE)

            # Label at dot: current temp + time
            cur_temp = graph_temps[hour_idx] if hour_idx < len(graph_temps) else 0
            temp_sym = "°F" if self.units == "imperial" else "°C"
            time_str = now.strftime("%-I:%M%p").lower()
            dot_label = f"{cur_temp:.0f}{temp_sym} {time_str}"
            dot_font = self.display.get_font(11, bold=True)
            # Position label above or below dot depending on space
            label_bbox = dot_font.getbbox(dot_label)
            label_w = label_bbox[2] - label_bbox[0]
            lx = cur_x - label_w // 2
            # Clamp to chart area
            lx = max(chart_x + 2, min(chart_x + chart_w - label_w - 2, lx))
            if cur_y - chart_y > 25:
                ly = cur_y - 18  # above dot
            else:
                ly = cur_y + 10  # below dot
            draw.text((lx, ly), dot_label, fill=BLACK, font=dot_font)

        # Y-axis labels — every 1°C or 2°F, skip overlaps
        small_font = self.display.get_font(11, bold=True)
        step = 2 if self.units == "imperial" else 1
        label_h = 13
        first_label = int(min_t // step) * step
        last_label = int(max_t // step + 1) * step
        prev_label_y = chart_y + chart_h + 999
        for lt in range(first_label, last_label + step, step):
            if lt < min_t or lt > max_t:
                continue
            ly = chart_y + chart_h - int((lt - min_t) / t_range * chart_h) - 6
            ly = max(chart_y - 2, min(chart_y + chart_h - 6, ly))
            if prev_label_y - ly >= label_h:
                draw.text((x, ly), f"{lt:.0f}°", fill=BLACK, font=small_font)
                gy = ly + 6
                for gx in range(chart_x + 3, chart_x + chart_w, 8):
                    draw.line([(gx, gy), (gx + 3, gy)], fill=BLACK, width=1)
                prev_label_y = ly

        # X-axis time labels — every 2 hours
        label_y = chart_y + chart_h + 1
        for offset in range(0, len(graph_times), 2):
            try:
                dt = datetime.strptime(graph_times[offset], "%Y-%m-%dT%H:%M")
                label = f"{dt.hour:02d}"
            except Exception:
                label = ""
            lx = chart_x + int(offset * step_x) - 6
            lx = min(lx, chart_x + chart_w - 16)
            draw.text((lx, label_y), label, fill=BLACK, font=small_font)

    def render(self):
        """Render weather in 3-row layout.
        Row 1 (25%): current conditions
        Row 2 (40%): 24hr graph (spans full width)
        Row 3 (35%): 7-day forecast
        """
        img, draw = self.display.create_canvas(bg_color=WHITE)

        update_time = getattr(self, '_last_update', '--:--')
        header_h = self.display.draw_header(
            draw, f"Weather — {self.location}", f"{update_time}",
            compact=True, img=img
        )

        if not self._weather_data:
            self.display.draw_text_block(
                draw, "No data. Press C to refresh.",
                20, header_h + 40, font_size=24, color=RED
            )
            return img

        current = self._weather_data.get("current", {})
        daily = self._weather_data.get("daily", {})
        hourly = self._weather_data.get("hourly", {})
        temp_symbol = "°F" if self.units == "imperial" else "°C"

        usable_h = self.display.height - header_h
        row3_h = 130  # forecast: label + day/date + icon + hi/lo + rain
        row1_h = int((usable_h - row3_h) * 0.28)
        row2_h = usable_h - row1_h - row3_h

        row1_y = header_h
        row2_y = row1_y + row1_h
        row3_y = row2_y + row2_h

        # ── Row 1: Current conditions ──
        code = current.get("weather_code", 0)
        desc, icon_key = WMO_CODES.get(code, ("Unknown", "cloud"))

        # Left: icon + big temp
        self._draw_icon(draw, icon_key, 15, row1_y + 8, size=60)

        temp = current.get("temperature_2m", 0)
        temp_font = self.display.get_font(48, bold=True)
        draw.text((90, row1_y + 5), f"{temp:.0f}{temp_symbol}",
                   fill=BLACK, font=temp_font)

        desc_font = self.display.get_font(16, bold=True)
        draw.text((90, row1_y + 58), desc, fill=BLACK, font=desc_font)

        # Today's high/low
        hl_font = self.display.get_font(16, bold=True)
        today_hi = daily.get("temperature_2m_max", [0])[0]
        today_lo = daily.get("temperature_2m_min", [0])[0]
        desc_bbox = desc_font.getbbox(desc)
        hl_x = 90 + (desc_bbox[2] - desc_bbox[0]) + 15
        draw.text((hl_x, row1_y + 58), f"H:{today_hi:.0f}°", fill=RED, font=hl_font)
        draw.text((hl_x + 55, row1_y + 58), f"L:{today_lo:.0f}°", fill=BLUE, font=hl_font)

        # Right: details (feels like, precipitation, wind)
        feels_like = current.get("apparent_temperature", 0)
        wind = current.get("wind_speed_10m", 0)
        # Precipitation chance = today's max precip probability
        todays_precip = 0
        precip_list = daily.get("precipitation_probability_max", [])
        if precip_list:
            todays_precip = precip_list[0]

        # Always show wind in mph as requested
        wind_mph = wind if self.units == "imperial" else wind * 0.621371
        wind_label = "mph"

        detail_x = 340
        detail_y = row1_y + 10
        label_font = self.display.get_font(15, bold=True)
        value_font = self.display.get_font(20, bold=True)
        icon_size = 26

        # Feels like
        self._draw_icon(draw, "thermometer" if "thermometer" in WI else "day-sunny",
                        detail_x, detail_y + 4, size=icon_size)
        draw.text((detail_x + 35, detail_y), "Feels Like",
                   fill=BLACK, font=label_font)
        draw.text((detail_x + 35, detail_y + 18),
                   f"{feels_like:.0f}{temp_symbol}",
                   fill=BLACK, font=value_font)

        # Precipitation (chance of rain)
        p_x = detail_x + 145
        self._draw_icon(draw, "raindrop" if "raindrop" in WI else "rain",
                        p_x, detail_y + 4, size=icon_size)
        draw.text((p_x + 35, detail_y), "Precipitation",
                   fill=BLACK, font=label_font)
        precip_color = BLUE if todays_precip > 30 else BLACK
        draw.text((p_x + 35, detail_y + 18), f"{todays_precip:.0f}%",
                   fill=precip_color, font=value_font)

        # Wind
        w_x = p_x + 175
        self._draw_icon(draw, "strong-wind" if "strong-wind" in WI else "day-sunny",
                        w_x, detail_y + 4, size=icon_size)
        draw.text((w_x + 35, detail_y), "Wind",
                   fill=BLACK, font=label_font)
        draw.text((w_x + 35, detail_y + 18), f"{wind_mph:.0f} {wind_label}",
                   fill=BLACK, font=value_font)

        # Row 1/2 divider
        self.display.draw_divider(draw, row2_y, color=BLACK, thickness=1)

        # ── Row 2: 24hr graph (full width) ──
        graph_x = 10
        graph_y = row2_y + 5
        graph_w = self.display.width - 20
        graph_h = row2_h - 8
        self._draw_temp_graph(draw, hourly, graph_x, graph_y, graph_w, graph_h)

        # Row 2/3 divider
        self.display.draw_divider(draw, row3_y, color=BLACK, thickness=1)

        # ── Row 3: 7-day forecast (no range bar) ──
        graph_label_font = self.display.get_font(14, bold=True)
        forecast_label_y = row3_y + 5
        draw.text((15, forecast_label_y), "7-Day Forecast",
                   fill=BLACK, font=graph_label_font)

        forecast_y = forecast_label_y + 22

        dates = daily.get("time", [])
        maxs = daily.get("temperature_2m_max", [])
        mins = daily.get("temperature_2m_min", [])
        codes = daily.get("weather_code", [])
        precip = daily.get("precipitation_probability_max", [])

        # Skip today (index 0), show next 7 days
        num_days = min(7, len(dates) - 1)
        col_w = (self.display.width - 20) // max(num_days, 1)

        day_font = self.display.get_font(14, bold=True)
        date_font = self.display.get_font(12)
        temp_hi_font = self.display.get_font(16, bold=True)
        temp_lo_font = self.display.get_font(15, bold=True)
        rain_font = self.display.get_font(13, bold=True)

        for i in range(num_days):
            di = i + 1  # skip today
            x = 10 + (i * col_w)

            # Day name + MM/DD
            try:
                dt = datetime.strptime(dates[di], "%Y-%m-%d")
                day_name = dt.strftime("%a")
                date_str = dt.strftime("%-m/%-d")
            except (ValueError, IndexError):
                day_name = f"D{i+1}"
                date_str = ""

            draw.text((x + 5, forecast_y), day_name, fill=BLACK, font=day_font)
            draw.text((x + 5, forecast_y + 16), date_str, fill=BLACK, font=date_font)

            # Icon
            day_code = codes[di] if di < len(codes) else 0
            _, day_icon = WMO_CODES.get(day_code, ("?", "cloud"))
            self._draw_icon(draw, day_icon, x + 5, forecast_y + 30, size=28)

            # High/Low
            hi = maxs[di] if di < len(maxs) else 0
            lo = mins[di] if di < len(mins) else 0
            draw.text((x + 45, forecast_y + 30),
                      f"{hi:.0f}°", fill=RED, font=temp_hi_font)
            draw.text((x + 45, forecast_y + 50),
                      f"{lo:.0f}°", fill=BLUE, font=temp_lo_font)

            # Rain %
            rain = precip[di] if di < len(precip) else 0
            rain_color = BLUE if rain > 30 else BLACK
            draw.text((x + 5, forecast_y + 72),
                      f"{rain:.0f}% rain", fill=rain_color, font=rain_font)

        return img

