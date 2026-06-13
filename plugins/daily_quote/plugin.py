"""
InkyBerry Daily Quote Plugin
Displays a quote of the day with author attribution.
Fetches from the Quotable API (free, no key).

Button mapping:
  C — fetch a new quote
  D — (falls through to main.py → info overlay)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import requests
from datetime import datetime
from plugins.base_plugin import BasePlugin
from display import BLACK, WHITE

# Fallback quotes in case the API is unreachable
FALLBACK_QUOTES = [
    ("The only way to do great work is to love what you do.",
     "Steve Jobs"),
    ("Simplicity is the ultimate sophistication.",
     "Leonardo da Vinci"),
    ("In the middle of difficulty lies opportunity.",
     "Albert Einstein"),
    ("It does not matter how slowly you go as long as you do not stop.",
     "Confucius"),
    ("What we think, we become.", "Buddha"),
    ("The unexamined life is not worth living.", "Socrates"),
    ("We are what we repeatedly do. Excellence, then, is not an act, but a habit.",
     "Aristotle"),
]


class Plugin(BasePlugin):
    name = "Daily Quote"
    description = "A daily inspirational quote on your e-ink display"

    def __init__(self, config, display):
        super().__init__(config, display)
        quote_cfg = config.get("daily_quote", {})
        self.refresh_interval = quote_cfg.get("refresh_interval", 86400)  # daily
        self.category = quote_cfg.get("category", None)  # e.g. "inspirational", "wisdom"
        self._quote_text = None
        self._quote_author = None

    def update_data(self):
        """Fetch a random quote from the Quotable API."""
        try:
            url = "https://api.quotable.io/random"
            params = {"maxLength": 200}
            if self.category:
                params["tags"] = self.category

            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            self._quote_text = data.get("content", "").strip()
            self._quote_author = data.get("author", "Unknown").strip()
            self.logger.info(
                f"Fetched quote by {self._quote_author}: "
                f"\"{self._quote_text[:60]}...\""
            )

        except Exception as e:
            self.logger.warning(f"Quote API failed: {e}, using fallback")
            import random
            self._quote_text, self._quote_author = random.choice(FALLBACK_QUOTES)

        # Trigger a re-render with the new quote
        # (done automatically by the refresh loop when this is the active plugin)

    def on_button(self, button):
        """C = fetch a new quote."""
        if button == "C":
            self.logger.info("Manual refresh — fetching new quote")
            self.update_data()
            return True  # consuming the button → triggers re-render
        return False

    def render(self):
        """Render the quote elegantly centered on the display."""
        img, draw = self.display.create_canvas(bg_color=WHITE)

        today = datetime.now().strftime("%A, %B %-d")
        header_h = self.display.draw_header(
            draw, "Daily Quote", today,
            compact=True, img=img
        )

        if not self._quote_text:
            self.display.draw_text_block(
                draw, "No quote yet. Press C to fetch one.",
                20, header_h + 40, font_size=22, color=BLACK
            )
            return img

        # ── Layout ──
        usable_y = header_h + 10
        usable_w = self.display.width - 40  # 20px side margins

        # Pick font size based on quote length — bold for impact
        text_len = len(self._quote_text)
        if text_len <= 40:
            font_size = 42
            author_font_size = 20
        elif text_len <= 80:
            font_size = 32
            author_font_size = 18
        elif text_len <= 130:
            font_size = 26
            author_font_size = 16
        else:
            font_size = 22
            author_font_size = 15

        font = self.display.get_font(font_size, bold=True)
        author_font = self.display.get_font(author_font_size, bold=True)
        quote_font = self.display.get_font(font_size + 6, bold=True)  # for the " marks

        # ── Wrap the quote text to fit ──
        lines = self._wrap_quote(self._quote_text, font, usable_w)

        # Calculate total text block height
        line_heights = []
        for line in lines:
            bbox = font.getbbox(line)
            line_heights.append(bbox[3] - bbox[1])
        line_spacing = int(font_size * 0.30)
        text_block_h = sum(line_heights) + line_spacing * (len(lines) - 1)

        # Author line height
        author_bbox = author_font.getbbox(f"— {self._quote_author}")
        author_h = author_bbox[3] - author_bbox[1]

        # Vertical centering
        gap = int(font_size * 0.6)
        total_h = text_block_h + gap + author_h
        start_y = usable_y + max(0, (self.display.height - usable_y - total_h) // 2)

        # ── Draw opening quote mark ──
        first_line = lines[0] if lines else ""
        first_bbox = font.getbbox(first_line)
        first_line_w = first_bbox[2] - first_bbox[0]
        quote_offset = int(font_size * 0.65)
        quote_x = (self.display.width - first_line_w) // 2 - quote_offset
        draw.text(
            (quote_x, start_y - int(font_size * 0.25)),
            "\u201c",  # left double quotation mark
            fill=BLACK, font=quote_font
        )

        # ── Draw each line centered ──
        current_y = start_y
        for line in lines:
            bbox = font.getbbox(line)
            line_w = bbox[2] - bbox[0]
            x = (self.display.width - line_w) // 2
            draw.text((x, current_y), line, fill=BLACK, font=font)
            current_y += (bbox[3] - bbox[1]) + line_spacing

        # ── Draw closing quote mark ──
        last_line = lines[-1]
        last_bbox = font.getbbox(last_line)
        last_line_w = last_bbox[2] - last_bbox[0]
        close_x = (self.display.width + last_line_w) // 2 + int(font_size * 0.15)
        close_y = current_y - line_spacing - (last_bbox[3] - last_bbox[1]) - int(font_size * 0.08)
        draw.text(
            (close_x, close_y),
            "\u201d",  # right double quotation mark
            fill=BLACK, font=quote_font
        )

        # ── Author attribution ──
        author_text = f"— {self._quote_author}"
        author_w = author_bbox[2] - author_bbox[0]
        author_x = (self.display.width - author_w) // 2
        author_y = current_y + gap

        # Decorative line above author
        line_w = min(160, author_w + 60)
        line_x = (self.display.width - line_w) // 2
        draw.rectangle(
            [line_x, author_y - int(author_font_size * 0.25),
             line_x + line_w, author_y - int(author_font_size * 0.25) + 1],
            fill=BLACK
        )

        draw.text((author_x, author_y), author_text, fill=BLACK, font=author_font)

        # ── Bottom hint ──
        hint_font = self.display.get_font(12, bold=True)
        hint_text = "Press C for a new quote"
        hint_bbox = hint_font.getbbox(hint_text)
        hint_w = hint_bbox[2] - hint_bbox[0]
        hint_x = (self.display.width - hint_w) // 2
        draw.text(
            (hint_x, self.display.height - 24),
            hint_text,
            fill=BLACK, font=hint_font
        )

        return img

    def _wrap_quote(self, text, font, max_width):
        """Word-wrap text into lines that fit max_width, preserving whole words."""
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            test = f"{current_line} {word}".strip()
            bbox = font.getbbox(test)
            if (bbox[2] - bbox[0]) <= max_width:
                current_line = test
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)
        return lines or [""]
