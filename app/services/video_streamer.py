import asyncio
import io
import math
import random
import time
from typing import AsyncGenerator, Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
import numpy as np

from app.config import settings

class VideoStreamer:
    def __init__(self):
        self.uav_frame_idx = 0
        self.ugv_frame_idx = 0
        self.uav_noise_level = 0.12  # 0.0 to 1.0
        self.ugv_noise_level = 0.10
        self.uav_flir_thermal = True
        self.ugv_night_vision = True
        
        # Simulated target positions in frame
        self.active_targets: Dict[str, Dict[str, Any]] = {}
        
        # Load default system font or PIL fallback
        try:
            self.font = ImageFont.load_default()
        except Exception:
            self.font = None

    def add_target_in_view(self, drone_type: str, target_type: str, bbox: Tuple[int, int, int, int], confidence: float):
        """Places a target in the simulated camera view for snapshotting."""
        self.active_targets[drone_type] = {
            "type": target_type,
            "bbox": bbox,
            "confidence": confidence,
            "timestamp": time.time()
        }

    def clear_targets_in_view(self, drone_type: str):
        if drone_type in self.active_targets:
            del self.active_targets[drone_type]

    def _draw_osd_uav(self, draw: ImageDraw.Draw, w: int, h: int, telemetry: Dict[str, Any], frame_idx: int):
        """Draws tactical military UAV HUD (On-Screen Display)."""
        color_primary = (0, 240, 255) if not self.uav_flir_thermal else (255, 180, 0)
        color_alert = (255, 40, 70)
        color_dim = (0, 180, 190) if not self.uav_flir_thermal else (180, 120, 0)

        cx, cy = w // 2, h // 2
        alt = telemetry.get("altitude", 65.0)
        speed = telemetry.get("speed", 12.4)
        heading = telemetry.get("heading", 45.0)
        pitch = telemetry.get("pitch", 0.0)
        roll = telemetry.get("roll", 0.0)
        lat = telemetry.get("lat", settings.DEFAULT_LAT)
        lon = telemetry.get("lon", settings.DEFAULT_LON)
        batt = telemetry.get("battery", 88.0)
        mode = telemetry.get("mode", "AUTO")

        # 1. Outer Reticle & Crosshair
        draw.line([(cx - 40, cy), (cx - 15, cy)], fill=color_primary, width=2)
        draw.line([(cx + 15, cy), (cx + 40, cy)], fill=color_primary, width=2)
        draw.line([(cx, cy - 40), (cx, cy - 15)], fill=color_primary, width=2)
        draw.line([(cx, cy + 15), (cx, cy + 40)], fill=color_primary, width=2)
        draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], outline=color_primary, width=1)

        # 2. Artificial Horizon Pitch Ladder
        roll_rad = math.radians(roll)
        pitch_px = int(pitch * 2.5)
        ladder_w = 50
        
        for p in [-20, -10, 10, 20]:
            offset_y = cy - pitch_px + int(p * 2.5)
            if 60 < offset_y < h - 60:
                # Rotate ladder lines by roll
                x1 = cx - ladder_w
                x2 = cx + ladder_w
                # Simplified level lines
                draw.line([(x1, offset_y), (x1 + 25, offset_y)], fill=color_dim, width=1)
                draw.line([(x2 - 25, offset_y), (x2, offset_y)], fill=color_dim, width=1)
                draw.text((x2 + 5, offset_y - 4), f"{p:+02d}", fill=color_dim, font=self.font)

        # 3. Left Speed Tape
        draw.rectangle([10, cy - 80, 50, cy + 80], outline=color_dim, width=1)
        draw.text((14, cy - 10), f"{speed:4.1f}", fill=color_primary, font=self.font)
        draw.text((14, cy + 6), "M/S", fill=color_dim, font=self.font)

        # 4. Right Altitude Tape
        draw.rectangle([w - 55, cy - 80, w - 10, cy + 80], outline=color_dim, width=1)
        draw.text((w - 50, cy - 10), f"{alt:4.0f}", fill=color_primary, font=self.font)
        draw.text((w - 48, cy + 6), "ALT-M", fill=color_dim, font=self.font)

        # 5. Top Heading Tape
        draw.rectangle([cx - 100, 10, cx + 100, 32], outline=color_dim, width=1)
        compass_text = f"HDG: {int(heading)%360:03d}° | {['N','NE','E','SE','S','SW','W','NW'][int((heading+22.5)/45)%8]}"
        draw.text((cx - 55, 14), compass_text, fill=color_primary, font=self.font)
        # Center pip
        draw.polygon([(cx, 32), (cx - 4, 38), (cx + 4, 38)], fill=color_primary)

        # 6. Top Left Tactical Indicators (Blinking REC & Channel)
        rec_blink = (frame_idx // 15) % 2 == 0
        if rec_blink:
            draw.ellipse([15, 15, 25, 25], fill=color_alert)
        draw.text((32, 14), "ANALOG CH-01 [5.8GHz FPV]", fill=color_primary, font=self.font)
        draw.text((15, 32), f"MODE: {mode} | BATT: {batt:.1f}% ({21.6 + batt*0.03:.1f}V)", fill=color_primary, font=self.font)

        # 7. Bottom Coordinates & Telemetry Bar
        coord_text = f"GPS: {lat:.6f}°N {lon:.6f}°E | FOV: 84° FLIR IR"
        draw.rectangle([10, h - 35, w - 10, h - 10], outline=color_dim, width=1)
        draw.text((18, h - 28), coord_text, fill=color_primary, font=self.font)
        draw.text((w - 110, h - 28), f"TIME: {time.strftime('%H:%M:%S')}", fill=color_primary, font=self.font)

        # 8. Render AI Target Bounding Boxes if active
        if "UAV" in self.active_targets:
            tgt = self.active_targets["UAV"]
            bx1, by1, bx2, by2 = tgt["bbox"]
            color_box = (0, 255, 120) if "LIFE" in tgt["type"] else (255, 20, 50)
            draw.rectangle([bx1, by1, bx2, by2], outline=color_box, width=2)
            # Corner markers
            cl = 8
            draw.line([(bx1, by1), (bx1 + cl, by1)], fill=color_box, width=3)
            draw.line([(bx1, by1), (bx1, by1 + cl)], fill=color_box, width=3)
            draw.line([(bx2, by2), (bx2 - cl, by2)], fill=color_box, width=3)
            draw.line([(bx2, by2), (bx2, by2 - cl)], fill=color_box, width=3)
            label = f"AI: {tgt['type']} ({tgt['confidence']*100:.0f}%)"
            draw.rectangle([bx1, by1 - 16, bx1 + 140, by1], fill=(0, 0, 0, 180))
            draw.text((bx1 + 3, by1 - 14), label, fill=color_box, font=self.font)

    def _draw_osd_ugv(self, draw: ImageDraw.Draw, w: int, h: int, telemetry: Dict[str, Any], frame_idx: int):
        """Draws tactical military UGV Ground Rover HUD."""
        color_green = (20, 255, 120)
        color_dim = (10, 160, 80)
        color_warn = (255, 170, 0)

        cx, cy = w // 2, h // 2
        speed = telemetry.get("speed", 4.2)
        batt = telemetry.get("battery", 92.0)
        heading = telemetry.get("heading", 180.0)
        lat = telemetry.get("lat", settings.DEFAULT_LAT - 0.0004)
        lon = telemetry.get("lon", settings.DEFAULT_LON + 0.0005)
        obs_dist = telemetry.get("obstacle_distance", 3.8)
        motor_temp = telemetry.get("motor_temp", 42.5)

        # 1. Ground Guide Lines (Drive perspective)
        draw.line([(w * 0.25, h), (cx - 20, cy + 40)], fill=color_dim, width=2)
        draw.line([(w * 0.75, h), (cx + 20, cy + 40)], fill=color_dim, width=2)
        # Distance markers on ground
        for y_line in [h - 40, h - 80, h - 120]:
            frac = (y_line - (cy + 40)) / (h - (cy + 40))
            x_left = (cx - 20) + (w * 0.25 - (cx - 20)) * frac
            x_right = (cx + 20) + (w * 0.75 - (cx + 20)) * frac
            draw.line([(x_left, y_line), (x_right, y_line)], fill=color_dim, width=1)

        # 2. LiDAR Proximity Radar Widget
        radar_cx, radar_cy = 70, h - 75
        draw.ellipse([radar_cx - 40, radar_cy - 40, radar_cx + 40, radar_cy + 40], outline=color_dim, width=1)
        draw.ellipse([radar_cx - 20, radar_cy - 20, radar_cx + 20, radar_cy + 20], outline=color_dim, width=1)
        # Radar sweep hand
        sweep_angle = (frame_idx * 6) % 360
        rad = math.radians(sweep_angle)
        draw.line([(radar_cx, radar_cy), (radar_cx + 38 * math.cos(rad), radar_cy + 38 * math.sin(rad))], fill=color_green, width=1)
        draw.text((radar_cx - 30, radar_cy + 45), f"LIDAR: {obs_dist:.1f}m", fill=color_green, font=self.font)

        # 3. Top Info Bar
        draw.text((15, 14), "UGV GROUND ROVER [CH-02 2.4GHz TELEMETRY]", fill=color_green, font=self.font)
        draw.text((15, 30), f"SPEED: {speed:.1f} km/h | GEAR: D | TEMP: {motor_temp:.1f}°C", fill=color_green, font=self.font)
        draw.text((w - 180, 14), f"BATT: {batt:.1f}% | HDG: {int(heading)%360:03d}°", fill=color_green, font=self.font)

        # 4. Center Obstacle Reticle
        if obs_dist < 2.0:
            draw.rectangle([cx - 40, cy - 30, cx + 40, cy + 30], outline=(255, 30, 40), width=2)
            draw.text((cx - 32, cy - 8), "COLLISION WARN", fill=(255, 30, 40), font=self.font)
        else:
            draw.rectangle([cx - 30, cy - 20, cx + 30, cy + 20], outline=color_green, width=1)

        # 5. Bottom GPS Status
        draw.text((15, h - 22), f"POS: {lat:.6f}°N {lon:.6f}°E | NIGHT VISION ACTIVE", fill=color_green, font=self.font)

        # 6. Target box if in UGV view
        if "UGV" in self.active_targets:
            tgt = self.active_targets["UGV"]
            bx1, by1, bx2, by2 = tgt["bbox"]
            color_box = (0, 255, 120) if "LIFE" in tgt["type"] else (255, 20, 50)
            draw.rectangle([bx1, by1, bx2, by2], outline=color_box, width=2)
            label = f"AI: {tgt['type']} ({tgt['confidence']*100:.0f}%)"
            draw.text((bx1, by1 - 14), label, fill=color_box, font=self.font)

    def generate_synthetic_scene(self, drone_type: str, w: int, h: int, frame_idx: int) -> np.ndarray:
        """Generates realistic synthetic analog drone camera scene (thermal or night vision)."""
        np.random.seed(frame_idx % 1000)
        
        if drone_type == "UAV":
            # Aerial Thermal FLIR Scene
            # Dark ground terrain with thermal hot spots
            base = np.zeros((h, w, 3), dtype=np.uint8)
            # Sky/Ground gradient
            ground_y = int(h * 0.35 + math.sin(frame_idx * 0.02) * 15)
            # Sky (cold = dark purplish / black)
            base[:ground_y, :] = [15, 10, 25]
            # Ground (warmer earth textures)
            base[ground_y:, :] = [30, 25, 35]

            # Add roads / terrain contours
            road_x = int(w * 0.5 + math.sin(frame_idx * 0.03) * 40)
            base[ground_y:, max(0, road_x - 30):min(w, road_x + 30)] = [50, 40, 55]

            # Heat signatures (thermal bright spots)
            # Hot spot 1: Building / structure
            b_x, b_y = int(w * 0.3), int(ground_y + 60)
            base[b_y:b_y+40, b_x:b_x+50] = [180, 140, 60]  # Thermal amber

            # Target heat signature if active
            if "UAV" in self.active_targets:
                bx1, by1, bx2, by2 = self.active_targets["UAV"]["bbox"]
                if "LIFE" in self.active_targets["UAV"]["type"]:
                    # Living human body heat signature: intense bright yellow/white core
                    base[by1:by2, bx1:bx2] = [255, 230, 120]
                else:
                    # Casualty / Dead body: cooler thermal signature
                    base[by1:by2, bx1:bx2] = [120, 90, 110]
        else:
            # UGV Ground Night-Vision Scene
            base = np.zeros((h, w, 3), dtype=np.uint8)
            # Dark forest/rubble terrain with night vision green luminescence
            base[:, :] = [10, 35, 15]
            # Ground plane
            ground_y = int(h * 0.45)
            base[ground_y:, :] = [15, 60, 25]
            # Obstacles / rocks
            obs_x = int(w * 0.6 + math.cos(frame_idx * 0.02) * 20)
            base[ground_y + 20:ground_y + 70, obs_x:obs_x + 60] = [30, 110, 45]

            if "UGV" in self.active_targets:
                bx1, by1, bx2, by2 = self.active_targets["UGV"]["bbox"]
                base[by1:by2, bx1:bx2] = [50, 210, 90]

        return base

    def apply_analog_effects(self, frame_np: np.ndarray, noise_level: float, frame_idx: int) -> np.ndarray:
        """Applies CRT scanlines, analog static noise, and RF glitches."""
        h, w, _ = frame_np.shape

        # 1. Analog RF White Noise / Static
        if noise_level > 0.01:
            noise = np.random.randint(0, 256, (h, w), dtype=np.uint8)
            noise_mask = np.random.random((h, w)) < (noise_level * 0.35)
            for c in range(3):
                frame_np[noise_mask, c] = noise[noise_mask]

        # 2. Horizontal Scanlines (Analog CRT look)
        frame_np[::2, :] = (frame_np[::2, :].astype(np.float32) * 0.82).astype(np.uint8)

        # 3. Occasional horizontal sync tearing / glitch
        if random.random() < 0.06:
            glitch_y = random.randint(0, h - 15)
            shift = random.randint(-12, 12)
            frame_np[glitch_y:glitch_y + 8, :] = np.roll(frame_np[glitch_y:glitch_y + 8, :], shift, axis=1)

        return frame_np

    def render_frame(self, drone_type: str, telemetry: Dict[str, Any]) -> bytes:
        """Renders a single analog video frame with HUD overlay as JPEG bytes."""
        w, h = settings.VIDEO_WIDTH, settings.VIDEO_HEIGHT
        
        if drone_type == "UAV":
            self.uav_frame_idx += 1
            f_idx = self.uav_frame_idx
            noise = self.uav_noise_level
        else:
            self.ugv_frame_idx += 1
            f_idx = self.ugv_frame_idx
            noise = self.ugv_noise_level

        # 1. Generate base scene
        scene = self.generate_synthetic_scene(drone_type, w, h, f_idx)
        
        # 2. Apply analog noise and scanlines
        scene = self.apply_analog_effects(scene, noise, f_idx)

        # 3. Draw OSD HUD overlay
        img = Image.fromarray(scene)
        draw = ImageDraw.Draw(img)

        if drone_type == "UAV":
            self._draw_osd_uav(draw, w, h, telemetry, f_idx)
        else:
            self._draw_osd_ugv(draw, w, h, telemetry, f_idx)

        # 4. Encode to JPEG
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75)
        return buf.getvalue()

    def capture_snapshot(
        self,
        drone_type: str,
        target_type: str,
        confidence: float,
        telemetry: Dict[str, Any]
    ) -> Tuple[str, bytes]:
        """Captures a high-resolution snapshot with AI detection annotations."""
        w, h = 800, 600
        # Determine bbox in center
        bx1, by1, bx2, by2 = int(w * 0.38), int(h * 0.35), int(w * 0.62), int(h * 0.65)
        self.add_target_in_view(drone_type, target_type, (bx1, by1, bx2, by2), confidence)

        scene = self.generate_synthetic_scene(drone_type, w, h, 100)
        img = Image.fromarray(scene)
        draw = ImageDraw.Draw(img)

        # Draw specific target annotation
        box_color = (0, 255, 120) if "LIFE" in target_type else (255, 40, 60)
        draw.rectangle([bx1, by1, bx2, by2], outline=box_color, width=3)
        label = f"[{target_type}] CONF: {confidence*100:.1f}% | GPS: {telemetry.get('lat', 0):.6f}, {telemetry.get('lon', 0):.6f}"
        draw.rectangle([bx1, by1 - 22, bx1 + 360, by1], fill=(0, 0, 0, 200))
        draw.text((bx1 + 4, by1 - 18), label, fill=box_color, font=self.font)

        # Save to storage
        filename = f"detection_{drone_type.lower()}_{int(time.time()*1000)}.jpg"
        filepath = settings.SNAPSHOT_DIR / filename
        img.save(filepath, format="JPEG", quality=85)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        raw_bytes = buf.getvalue()

        # Clear target after snapshot
        asyncio.get_event_loop().call_later(4.0, self.clear_targets_in_view, drone_type)

        return str(filepath), raw_bytes

video_streamer = VideoStreamer()
