"""
InkDash Stock Tracker Plugin
Displays stock prices with intraday sparkline charts using yfinance.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plugins.base_plugin import BasePlugin
from display import BLACK, WHITE, GREEN, RED, ORANGE, BLUE
from datetime import datetime
import pytz
import tzlocal


class Plugin(BasePlugin):
    name = "Stocks"
    description = "Track stock prices with intraday charts"

    def __init__(self, config, display):
        super().__init__(config, display)
        stock_cfg = config.get("stocks", {})
        # Support both old "tickers" and new "ticker_groups" format
        if "ticker_groups" in stock_cfg:
            self.ticker_groups = stock_cfg["ticker_groups"]
        else:
            self.ticker_groups = [stock_cfg.get("tickers",
                                                ["AMZN", "Z", "VOO", "NVDA"])]
        self.group_index = 0
        self.tickers = self.ticker_groups[0]
        self.refresh_interval = stock_cfg.get("refresh_interval", 900)
        self._stock_data = {}
        # Timezone from config, default Pacific
        # Timezone: auto-detect from Pi system, config.yaml can override
        # Timezone: always use Pi's system timezone
        self.tz = tzlocal.get_localzone()

    def on_button(self, button):
        """D button cycles through ticker groups."""
        if button == "D" and len(self.ticker_groups) > 1:
            self.group_index = (self.group_index + 1) % len(self.ticker_groups)
            self.tickers = self.ticker_groups[self.group_index]
            self.logger.info(f"Switched to ticker group: {self.tickers}")
            self.update_data()
            return True
        return False

    def update_data(self):
        """Fetch latest stock data and intraday history from Yahoo Finance."""
        try:
            import yfinance as yf

            self.logger.info(f"Fetching data for: {self.tickers}")
            data = {}
            for ticker in self.tickers:
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.fast_info

                    price = info.last_price if hasattr(info, 'last_price') else 0
                    prev_close = info.previous_close if hasattr(info, 'previous_close') else price

                    change = price - prev_close
                    change_pct = (change / prev_close * 100) if prev_close else 0

                    day_high = info.day_high if hasattr(info, 'day_high') else price
                    day_low = info.day_low if hasattr(info, 'day_low') else price

                    # Fetch intraday data (5-min intervals, last 1 day)
                    hist = stock.history(period="1d", interval="5m")
                    intraday_prices = []
                    intraday_times = []
                    if not hist.empty and 'Close' in hist.columns:
                        intraday_prices = hist['Close'].dropna().tolist()
                        # Convert timestamps to local timezone
                        for ts in hist['Close'].dropna().index:
                            try:
                                local_ts = ts.astimezone(self.tz)
                                intraday_times.append(local_ts.strftime("%H:%M"))
                            except Exception:
                                intraday_times.append("")

                    # If market is closed or no intraday, try 2-day with 15m
                    if len(intraday_prices) < 5:
                        hist = stock.history(period="2d", interval="15m")
                        if not hist.empty and 'Close' in hist.columns:
                            intraday_prices = hist['Close'].dropna().tolist()
                            intraday_times = []
                            for ts in hist['Close'].dropna().index:
                                try:
                                    local_ts = ts.astimezone(self.tz)
                                    intraday_times.append(local_ts.strftime("%H:%M"))
                                except Exception:
                                    intraday_times.append("")

                    data[ticker] = {
                        "price": price,
                        "change": change,
                        "change_pct": change_pct,
                        "prev_close": prev_close,
                        "day_high": day_high,
                        "day_low": day_low,
                        "intraday": intraday_prices,
                        "intraday_times": intraday_times,
                    }
                    self.logger.info(
                        f"  {ticker}: ${price:.2f} ({change_pct:+.2f}%) "
                        f"[{len(intraday_prices)} chart points]"
                    )
                except Exception as e:
                    self.logger.error(f"  Error fetching {ticker}: {e}")
                    data[ticker] = None

            self._stock_data = data
            now_local = datetime.now(self.tz)
            self._last_update = now_local.strftime("%H:%M %Z")

        except ImportError:
            self.logger.error("yfinance not installed! Run: pip install yfinance")
            self._stock_data = {}

    def _draw_sparkline(self, draw, prices, times, prev_close, x, y, width, height):
        """Draw an intraday sparkline chart with time labels."""
        if len(prices) < 2:
            font = self.display.get_font(14)
            draw.text((x + 10, y + height // 2 - 7), "No chart data",
                      fill=BLACK, font=font)
            return

        # Reserve space at bottom for time labels
        time_label_h = 16
        chart_h = height - time_label_h
        chart_y = y

        min_price = min(min(prices), prev_close)
        max_price = max(max(prices), prev_close)
        price_range = max_price - min_price

        if price_range == 0:
            price_range = max_price * 0.01 if max_price > 0 else 1
            min_price -= price_range / 2
            max_price += price_range / 2
            price_range = max_price - min_price

        # Chart border
        draw.rectangle([x, chart_y, x + width, chart_y + chart_h], outline=BLACK)

        # Previous close dashed reference line
        if min_price <= prev_close <= max_price:
            ref_y = chart_y + chart_h - int((prev_close - min_price) / price_range * chart_h)
            ref_y = max(chart_y + 1, min(chart_y + chart_h - 1, ref_y))
            for dx in range(0, width, 8):
                x1 = x + dx
                x2 = min(x + dx + 4, x + width)
                draw.line([(x1, ref_y), (x2, ref_y)], fill=BLACK, width=1)

        # Line color based on performance
        current_price = prices[-1]
        line_color = GREEN if current_price >= prev_close else RED

        # Build sparkline points
        points = []
        step_x = width / (len(prices) - 1)
        for i, p in enumerate(prices):
            px = x + int(i * step_x)
            py = chart_y + chart_h - int((p - min_price) / price_range * chart_h)
            py = max(chart_y + 1, min(chart_y + chart_h - 1, py))
            px = max(x + 1, min(x + width - 1, px))
            points.append((px, py))

        # Draw the sparkline
        for i in range(len(points) - 1):
            draw.line([points[i], points[i + 1]], fill=line_color, width=2)

        # Subtle fill under the line
        baseline = chart_y + chart_h
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            for sx in range(x1, x2, 3):
                if x2 != x1:
                    t = (sx - x1) / (x2 - x1)
                    sy = int(y1 + t * (y2 - y1))
                else:
                    sy = y1
                draw.line([(sx, sy), (sx, baseline)], fill=line_color, width=1)

        # Current price dot
        if points:
            last = points[-1]
            r = 3
            draw.ellipse([last[0] - r, last[1] - r, last[0] + r, last[1] + r],
                         fill=line_color)

        # Time axis labels
        time_font = self.display.get_font(11)
        label_y = chart_y + chart_h + 2
        if times and len(times) >= 2:
            # Show start, middle, and end times
            labels = [
                (x + 2, times[0]),
                (x + width // 2 - 12, times[len(times) // 2]),
                (x + width - 32, times[-1]),
            ]
            for lx, lt in labels:
                if lt:
                    draw.text((lx, label_y), lt, fill=BLACK, font=time_font)


    def _get_market_status(self):
        """Return market status string if markets are closed, else empty."""
        try:
            import pytz
            et = pytz.timezone("America/New_York")
            now_et = datetime.now(et)
            weekday = now_et.weekday()  # 0=Mon, 6=Sun
            hour, minute = now_et.hour, now_et.minute
            time_mins = hour * 60 + minute

            if weekday >= 5:  # Saturday/Sunday
                return "Markets Closed"
            elif time_mins < 9 * 60 + 30:  # Before 9:30 AM ET
                return "Pre-Market"
            elif time_mins >= 16 * 60:  # After 4:00 PM ET
                return "After Hours"
            else:
                return ""  # Market is open
        except Exception:
            return ""

    def render(self):
        """Render stock data with intraday charts."""
        img, draw = self.display.create_canvas(bg_color=WHITE)

        update_time = getattr(self, '_last_update', '--:--')
        market_status = self._get_market_status()
        subtitle = f"Updated {update_time}"
        if market_status:
            subtitle = f"{market_status}  •  {subtitle}"
        header_h = self.display.draw_header(
            draw, "Stock Tracker", subtitle,
            compact=True, img=img
        )

        if not self._stock_data:
            self.display.draw_text_block(
                draw, "No data. Press C to refresh.",
                20, header_h + 40, font_size=24, color=RED
            )
            return img

        num_stocks = len(self.tickers)
        usable_h = self.display.height - header_h - 5
        row_h = usable_h // num_stocks

        chart_width = 260

        for i, ticker in enumerate(self.tickers):
            y = header_h + (i * row_h)
            data = self._stock_data.get(ticker)

            if i > 0:
                self.display.draw_divider(draw, y, color=BLACK, thickness=1)

            y_pad = y + 4

            if data is None:
                font = self.display.get_font(22, bold=True)
                draw.text((15, y_pad + 10), ticker, fill=BLACK, font=font)
                err_font = self.display.get_font(18)
                draw.text((120, y_pad + 12), "Error fetching data",
                          fill=RED, font=err_font)
                continue

            # ── Left: ticker + price + change ──
            ticker_font = self.display.get_font(22, bold=True)
            draw.text((12, y_pad), ticker, fill=BLACK, font=ticker_font)

            price = data["price"]
            price_font = self.display.get_font(28, bold=True)
            draw.text((12, y_pad + 26), f"${price:,.2f}", fill=BLACK, font=price_font)

            change = data["change"]
            change_pct = data["change_pct"]
            is_positive = change >= 0
            arrow = "+" if is_positive else ""
            change_color = GREEN if is_positive else RED
            change_str = f"{arrow}{change:.2f} ({arrow}{change_pct:.2f}%)"
            change_font = self.display.get_font(16, bold=True)
            draw.text((12, y_pad + 58), change_str, fill=change_color, font=change_font)

            # ── Middle: day high / low ──
            mid_x = 220
            hl_label_font = self.display.get_font(13)
            hl_val_font = self.display.get_font(16, bold=True)

            day_high = data.get("day_high", price)
            day_low = data.get("day_low", price)

            draw.text((mid_x, y_pad + 5), "H:", fill=BLACK, font=hl_label_font)
            draw.text((mid_x + 18, y_pad + 3), f"${day_high:,.2f}",
                       fill=BLACK, font=hl_val_font)

            draw.text((mid_x, y_pad + 28), "L:", fill=BLACK, font=hl_label_font)
            draw.text((mid_x + 18, y_pad + 26), f"${day_low:,.2f}",
                       fill=BLACK, font=hl_val_font)

            # Prev close
            prev_close = data.get("prev_close", price)
            draw.text((mid_x, y_pad + 51), "PC:", fill=BLACK, font=hl_label_font)
            draw.text((mid_x + 25, y_pad + 49), f"${prev_close:,.2f}",
                       fill=BLACK, font=hl_val_font)

            # ── Right: intraday chart ──
            chart_x = self.display.width - chart_width - 8
            chart_h = row_h - 10
            chart_y = y_pad + 2

            self._draw_sparkline(
                draw,
                data.get("intraday", []),
                data.get("intraday_times", []),
                prev_close,
                chart_x, chart_y, chart_width, chart_h
            )

        return img
