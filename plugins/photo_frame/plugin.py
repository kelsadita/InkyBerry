"""
InkyBerry Photo Frame Plugin
Displays photos from a directory, dithered for the 7-color e-ink display.

Button mapping:
  A / B  -> previous / next plugin (handled by main.py, not intercepted here)
  D      -> next photo (loops)
  Auto-advance every 60 seconds via update_data() scheduler
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import random
from plugins.base_plugin import BasePlugin
from display import BLACK, WHITE, RED
from PIL import Image, ImageFilter
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass  # HEIC/HEIF won't work without pillow-heif


class Plugin(BasePlugin):
    name = "Photo Frame"
    description = "Display photos on your e-ink screen"

    def __init__(self, config, display):
        super().__init__(config, display)
        photo_cfg = config.get("photo_frame", {})
        photo_dir = photo_cfg.get("directory", "~/inkyberry/photos")
        self.photo_dir = os.path.expanduser(photo_dir)
        self.shuffle = photo_cfg.get("shuffle", True)
        self.refresh_interval = photo_cfg.get("interval", 60)  # seconds between auto-advance
        self._photos = []
        self._current_index = 0
        os.makedirs(self.photo_dir, exist_ok=True)
        self._scan_photos()

    def _scan_photos(self):
        """Scan the photo directory for image files."""
        extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".heic", ".heif"}
        self._photos = []
        if os.path.isdir(self.photo_dir):
            for f in sorted(os.listdir(self.photo_dir)):
                if os.path.splitext(f)[1].lower() in extensions:
                    self._photos.append(os.path.join(self.photo_dir, f))
            if self.shuffle:
                # Seeded shuffle: consistent order across restarts
                random.Random(hash(self.photo_dir)).shuffle(self._photos)
        self.logger.info(f"Found {len(self._photos)} photos in {self.photo_dir}")

    def update_data(self):
        """Advance to next photo (called by scheduler every 60s)."""
        if not self._photos:
            self._scan_photos()  # retry finding photos
        if self._photos:
            self._current_index = (self._current_index + 1) % len(self._photos)

    def on_button(self, button):
        """C=prev photo, D=next photo. A/B fall through to main.py (prev/next plugin)."""
        if button in ("C", "D"):
            if not self._photos:
                # No photos loaded — rescan the folder
                self._scan_photos()
                return True  # consumed — triggers re-render with new photos (or same empty msg)
            if button == "C":
                self._current_index = (self._current_index - 1) % len(self._photos)
            else:
                self._current_index = (self._current_index + 1) % len(self._photos)
            return True
        return False  # A/B fall through to main.py → prev/next plugin

    def render(self):
        """Render current photo with blurred background fill for letterboxed areas."""
        img, draw = self.display.create_canvas(bg_color=WHITE)

        if not self._photos:
            self.display.draw_text_block(
                draw, f"No photos found in {self.photo_dir}",
                20, 100, font_size=24, color=RED
            )
            self.display.draw_text_block(
                draw,
                "Add .jpg or .png files to the photos directory "
                "and press C to refresh.",
                20, 160, font_size=20, color=BLACK
            )
            return img

        photo_path = self._photos[self._current_index]
        self.logger.info(f"Displaying: {os.path.basename(photo_path)}")

        try:
            photo = Image.open(photo_path)

            if photo.mode != "RGB":
                photo = photo.convert("RGB")

            dw, dh = self.display.width, self.display.height
            photo_ratio = photo.width / photo.height
            display_ratio = dw / dh

            if photo_ratio > display_ratio:
                # Wider than display — fits to width, letterbox top/bottom
                new_w = dw
                new_h = int(dw / photo_ratio)
            else:
                # Taller than display — fits to height, letterbox left/right
                new_h = dh
                new_w = int(dh * photo_ratio)

            needs_background = (new_w < dw) or (new_h < dh)

            if needs_background:
                # Scale photo to FILL (cover) the display for the blurred bg
                if photo_ratio > display_ratio:
                    bg_h = dh
                    bg_w = int(dh * photo_ratio)
                else:
                    bg_w = dw
                    bg_h = int(dw / photo_ratio)

                bg = photo.resize((bg_w, bg_h), Image.LANCZOS)

                # Crop to display size from center
                bg_x = (bg_w - dw) // 2
                bg_y = (bg_h - dh) // 2
                bg = bg.crop((bg_x, bg_y, bg_x + dw, bg_y + dh))

                # Blur and darken so the foreground photo stands out
                bg = bg.filter(ImageFilter.GaussianBlur(radius=18))
                black = Image.new("RGB", (dw, dh), (0, 0, 0))
                canvas = Image.blend(bg, black, alpha=0.35)
            else:
                canvas = Image.new("RGB", (dw, dh), (0, 0, 0))

            photo_resized = photo.resize((new_w, new_h), Image.LANCZOS)

            offset_x = (dw - new_w) // 2
            offset_y = (dh - new_h) // 2
            canvas.paste(photo_resized, (offset_x, offset_y))

            return canvas

        except Exception as e:
            self.logger.error(f"Error loading photo: {e}")
            self.display.draw_text_block(
                draw, f"Error: {e}", 20, 200, font_size=18, color=RED
            )
            return img
