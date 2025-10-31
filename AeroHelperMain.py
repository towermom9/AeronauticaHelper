'''
https://aeronautica-helper.vercel.app
https://github.com/SSkipr/AeronauticaHelper
Version 3.0 (PySide6)

Alert Ranking:
[!] Urgent
[*] AutoJoin or other elevated notifications
[$] Logging Info / 'Non-Urgent Notifications' in the UI, can be disabled
'''

# --------------------------------------------------
# Library setup
# --------------------------------------------------
import os
import json
import logging
import re
import sys
import time
import datetime
import io
import base64
import threading
import subprocess
import importlib
import platform
import random
import ctypes

import numpy
import pyautogui
import requests
import easyocr
import torch

from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLineEdit, QLabel, QCheckBox, QMessageBox, QFrame, QHBoxLayout, QHBoxLayout
from PySide6 import QtCore
from PySide6.QtCore import QTimer, QThread, Signal # Changed from pyqtSignal
from PySide6.QtGui import QIcon
from PySide6.QtCore import QByteArray

import resources_rc_pyside6

import pyautogui
import numpy
import easyocr
import pynput
from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Button, Controller as MouseController

class CrossPlatformMouse:
    def __init__(self):
        self.system = platform.system()
        if self.system == "Darwin":
            self.mouse = MouseController()
        else:
            try:
                from mousekey import MouseKey
                self.mouse = MouseKey()
                self.using_mousekey = True
            except ImportError:
                self.mouse = MouseController()
                self.using_mousekey = False

    def left_click_xy_natural(self, x, y, delay=0.3, min_variation=-3, max_variation=3,
                             use_every=4, sleeptime=(0.005, 0.009), print_coords=False, percent=90):
        if self.system == "Darwin" or not self.using_mousekey:
            current_x, current_y = self.mouse.position

            steps = 20
            for i in range(1, steps + 1):
                progress = i / steps
                path_x = current_x + (x - current_x) * progress
                path_y = current_y + (y - current_y) * progress

                if i != steps:
                    path_x += random.randint(min_variation, max_variation)
                    path_y += random.randint(min_variation, max_variation)

                self.mouse.position = (path_x, path_y)
                time.sleep(random.uniform(*sleeptime) * 2)

            self.mouse.position = (x, y)
            time.sleep(delay)
            self.mouse.press(Button.left)
            time.sleep(0.1)
            self.mouse.release(Button.left)
        else:
            self.mouse.left_click_xy_natural(x, y, delay, min_variation, max_variation,
                                           use_every, sleeptime, print_coords, percent)

def get_screen_scaling_factor():
    if platform.system() == "Darwin":
        try:
            from AppKit import NSScreen
            scaling = NSScreen.mainScreen().backingScaleFactor()
            return scaling
        except:
            return 1.0
    elif platform.system() == "Windows":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            return user32.GetDpiForSystem() / 96.0
        except:
            return 1.0
    else:
        return 1.0

def check_platform_requirements():
    if platform.system() == "Darwin":
        try:
            import Quartz
            Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
        except Exception:
            QMessageBox.warning(None, "Accessibility Permission Required",
                "AeroHelper requires accessibility permissions to control the mouse and keyboard.\n\n"
                "Please go to System Preferences → Security & Privacy → Privacy → Accessibility\n"
                "and add this application or Python to the list of allowed apps.")

keyboard = KeyboardController()
cross_mouse = CrossPlatformMouse()
mouse = MouseController()

if platform.system() == "Darwin":
    required_downloads = ['PySide6', 'pyautogui', 'numpy', 'easyocr', 'pynput', 'requests']
else:
    required_downloads = ['PySide6', 'pyautogui', 'numpy', 'easyocr', 'pynput', 'mousekey', 'requests']

missing_imports = []
for library_name in required_downloads:
    try:
        importlib.import_module(library_name)
    except ImportError:
        missing_imports.append(library_name)
if missing_imports:
    for library in missing_imports:
        subprocess.check_call([sys.executable, "-m", "pip", "install", library])

try:
    import torch
    gpu_available = torch.cuda.is_available()
except:
    gpu_available = False

reader = easyocr.Reader(['en'], gpu=gpu_available)

scaling_factor = get_screen_scaling_factor()

def scale_coordinates(x, y):
    return int(x * scaling_factor), int(y * scaling_factor)

# --------------------------------------------------
# Configuration and Logging Setup
# --------------------------------------------------
VERSION = "3"
AIRPORT_ROUTES = {
    # Ignore, just SSkipr's debug routes:
    #"kjerstin field": ["nordspyd arctic airfield"],
    #"nordspyd arctic airfield": ["kjerstin field"],

    "leovetsk international airport": ["auchenburgh airport", "tierdam airfield"],
    "auchenburgh airport": ["leovetsk international airport"],
    "nordspyd arctic airfield": ["tenera palm airfield", "nordspyd arctic airfield"],
    "tenera palm airfield": ["nordspyd arctic airfield"],
    "norman international airport": ["nordspyd arctic airfield", "auchenburgh airport"],
    "tierdam airfield": ["leovetsk international airport"]
}
DATA_FILE = "data.json"
LOG_FILE = "log_data.txt"
WEBHOOK_URL = ""
LEEWAY = 0.3 
MULTIPLIER = 1.9

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - %(message)s')

consecutive_alerts = 0

# --------------------------------------------------
# Autosave Configuration Functions
# --------------------------------------------------
def save_config(data):
    try:
        if "webhook_url" in data:
            data["webhook_url"] = base64.b64encode(data["webhook_url"].encode('utf-8')).decode('utf-8')
        with open(DATA_FILE, "w") as f:
            json.dump(data, f)
        logging.info("[$] Configuration data saved.")
    except Exception as e:
        logging.error("[$] Failed to save config: " + str(e))

def load_config():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                if "webhook_url" in data and data["webhook_url"]:
                    data["webhook_url"] = base64.b64decode(data["webhook_url"].encode('utf-8')).decode('utf-8')
                return data
        except Exception as e:
            logging.error("[$] Failed to load config: " + str(e))
    return {}

# --------------------------------------------------
# Initialize EasyOCR Reader
# --------------------------------------------------
reader = easyocr.Reader(['en'], gpu=gpu_available)

# --------------------------------------------------
# Helper function to click center of a bounding box
# --------------------------------------------------
def click_center(bbox):
    try:
        x = int((bbox[0][0] + bbox[2][0]) / 2)
        y = int((bbox[0][1] + bbox[2][1]) / 2)
        
        if x < 0 or y < 0:
            logging.warning("[!] Invalid coordinates detected in click_center")
            return False
            
        cross_mouse.left_click_xy_natural(x, y, delay=0.3, min_variation=-3, max_variation=3,
                                use_every=4, sleeptime=(0.005, 0.009), print_coords=False, percent=90)
        return True
    except Exception as e:
        logging.error(f"[!] Error in click_center: {str(e)}")
        return False

# --------------------------------------------------
# Reconnect Sequence with Checkpoints
# --------------------------------------------------
def reconnect_sequence():
    attempts = 0
    success = False
    while attempts < 3 and not success:
        ocr_text, ocr_results = capture_and_process_screenshot()
        for res in ocr_results:
            if "Reconnect" in res[1]:
                click_center(res[0])
                alert("[*] 'Reconnect' clicked.", include_screenshot=False)
                success = True
                break
        if not success:
            attempts += 1
            time.sleep(5)
    if not success:
        alert("[!] Failed to click 'Reconnect'.", include_screenshot=False)
        return False

    attempts = 0
    success = False
    time.sleep(15)
    while attempts < 3 and not success:
        time.sleep(1)
        ocr_text, ocr_results = capture_and_process_screenshot()
        for res in ocr_results:
            if "join game" in res[1].lower():
                click_center(res[0])
                alert("[*] 'Join game' clicked.", include_screenshot=False)
                success = True
                break
        if not success:
            attempts += 1
            time.sleep(5)
    if not success:
        alert("[!] Failed to click 'Join game'.", include_screenshot=False)
        return False

    attempts = 0
    success = False
    time.sleep(90)
    while attempts < 3 and not success:
        time.sleep(1)
        ocr_text, ocr_results = capture_and_process_screenshot()
        hide_results = [res for res in ocr_results if res[1] == "Hide"]
        if len(hide_results) == 2:
            for res in hide_results:
                click_center(res[0])
            alert("[*] Two 'Hide' results clicked.", include_screenshot=False)
            success = True
        else:
            attempts += 1
            time.sleep(5)
    if not success:
        alert("[!] Failed to click two 'Hide' results.", include_screenshot=False)
        return False

    attempts = 0
    success = False
    time.sleep(1)
    while attempts < 3 and not success:
        time.sleep(1)
        ocr_text, ocr_results = capture_and_process_screenshot()
        for res in ocr_results:
            if "Continue Flight" in res[1]:
                click_center(res[0])
                alert("[*] 'Continue Flight' clicked.", include_screenshot=False)
                success = True
                break
        if not success:
            attempts += 1
            time.sleep(5)
    if not success:
        alert("[!] Failed to click 'Continue Flight'.", include_screenshot=False)
        return False

    time.sleep(10)
    keyboard.press('e')
    keyboard.release('e')
    alert("[*] 'e' key pressed.", include_screenshot=False)
    time.sleep(15)
    keyboard.press('w')
    time.sleep(3)
    keyboard.release('w')
    alert("[*] Held 'w' for 3 seconds.", include_screenshot=True)
    alert("[*] Rejoined Server", include_screenshot=True)
    return True

# --------------------------------------------------
# Combined Alert Function
# --------------------------------------------------
def alert(message, include_screenshot=False):
    global consecutive_alerts
    if message.startswith("[!]"):
        consecutive_alerts += 1
        message = "@everyone " + message
    else:
        consecutive_alerts = 0
    
    payload = {"content": message}
    try:
        if include_screenshot:
            screenshot = pyautogui.screenshot()
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG")
            buffer.seek(0)
            files = {"file": ("screenshot.png", buffer, "image/png")}
            response = requests.post(WEBHOOK_URL, data={"payload_json": json.dumps(payload)}, files=files)
        else:
            response = requests.post(WEBHOOK_URL, json=payload)
        response.raise_for_status()
        logging.info("[!] Alert sent: " + message)
    except Exception as e:
        logging.error("[!] Failed to send alert: " + str(e))
    
    if consecutive_alerts >= 5:
        logging.error("[!] 5 consecutive error alerts reached. Exiting application.")
        sys.exit(1)
        
    return True

# --------------------------------------------------
# Screenshot Capture and OCR Processing
# --------------------------------------------------
def capture_and_process_screenshot():
    screenshot = pyautogui.screenshot()
    image = numpy.array(screenshot)
    results = reader.readtext(image)
    text = " ".join([res[1] for res in results])
    return text, results

# --------------------------------------------------
# Extracting the Distance Value
# --------------------------------------------------
def extract_distance(ocr_text):
    ocr_text = ocr_text.lower()
    distance_pattern = r"distance:?\s*(\d+(?:[.,]\d+)?)\s*nm"
    match = re.search(distance_pattern, ocr_text, re.IGNORECASE)
    if match:
        try:
            return abs(float(match.group(1).replace(",", ".")))
        except ValueError:
            return None
            
    pattern = r"(\d+(?:[.,]\d+)?)\s*nm"
    matches = re.findall(pattern, ocr_text, re.IGNORECASE)
    if len(matches) >= 2:
        value_str = matches[1].replace(",", ".")
        try:
            return abs(float(value_str))
        except ValueError:
            return None
    elif matches:
        try:
            return abs(float(matches[0].replace(",", ".")))
        except ValueError:
            return None
    return None

def calculate_eta(current_distance, vehicle_speed):
    try:
        eta_hours = current_distance / vehicle_speed
        return eta_hours
    except:
        return None

# --------------------------------------------------
# Extract Bearing Values for AutoSteer
# --------------------------------------------------
def extract_target_bearing(ocr_text):
    ocr_text_lower = ocr_text.lower()
    match = re.search(r"dest(?:ination)?\D+(\d{3})", ocr_text_lower)
    if match:
        try:
            target = int(match.group(1))
            return "dest", target
        except ValueError:
            pass
    pattern = r"(?!clear|trk|hdg)(?!\b\d{1,2}nm\b)(?!\d{3,6}(?=\s?mb\b))(\b[a-z]{4,5}\b)\s+(\d{3})"
    match = re.search(pattern, ocr_text_lower)
    if match:
        try:
            dest = match.group(1)
            target = int(match.group(2))
            if dest in ["knots", "games", "windy"]:
                return "OCR Error", target
            else:
                return dest, target
        except ValueError:
            return None
    return None

def extract_current_bearing(ocr_text):
    ocr_text = ocr_text.lower()
    match = re.search(r"trk\s*(\d{3})\s+\d{3}\s+hdg", ocr_text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None

# --------------------------------------------------
# AutoSteer Function
# --------------------------------------------------
def run_autosteer(ocr_text):
    result = extract_target_bearing(ocr_text)
    current_bearing = extract_current_bearing(ocr_text)
    if result is not None and current_bearing is not None:
        dest, target = result
        logging.info(f"[$] AutoSteer - Target Bearing: {target}, Current Bearing: {current_bearing}")
        diff = abs(current_bearing - target)
        if target < current_bearing:
            key_to_press = 'a'
        elif target > current_bearing:
            key_to_press = 'd'
        else:
            logging.info("[$] AutoSteer - No difference in bearing, no steering required.")
            return

        if diff > 35:
            hold_duration = 7 * MULTIPLIER
        elif 15 <= diff <= 34:
            hold_duration = 5 * MULTIPLIER
        elif 11 <= diff <= 15:
            hold_duration = 3 * MULTIPLIER
        elif 6 <= diff <= 10:
            hold_duration = 2 * MULTIPLIER
        elif 3 <= diff <= 5:
            hold_duration = 1 * MULTIPLIER
        elif 1 <= diff < 3:
            hold_duration = 0.75 * MULTIPLIER
        else:
            logging.info("[$] AutoSteer - Difference too small, no steering adjustment needed.")
            return

        logging.info(f"[$] AeroHelper AutoSteer - Pressing {key_to_press} for {hold_duration} sec (difference: {diff})")
        keyboard.press(key_to_press)
        time.sleep(hold_duration)
        keyboard.release(key_to_press)
    else:
        if result is None and current_bearing is None:
            alert("[!] AutoSteer - Target and current bearing not found in OCR text.", include_screenshot=False)
        elif result is None:
            alert("[!] AutoSteer - Target not found in OCR text.", include_screenshot=False)
        elif current_bearing is None:
            alert("[!] AutoSteer - Current bearing not found in OCR text.", include_screenshot=False)
        else:
            alert("[!] AutoSteer - Outstanding OCR error.", include_screenshot=False)
        logging.warning("[!] AutoSteer - Target or current bearing not found in OCR text.")

# --------------------------------------------------
# Check for End Sail Button Function
# --------------------------------------------------
def check_for_end_sail():
    ocr_text, ocr_results = capture_and_process_screenshot()
    for res in ocr_results:
        if "end sail" in res[1].lower():
            bbox = res[0]
            x = int((bbox[0][0] + bbox[2][0]) / 2)
            y = int((bbox[0][1] + bbox[2][1]) / 2)
            
            button_region = pyautogui.screenshot(region=(x-20, y-10, 40, 20))
            button_rgb = numpy.array(button_region)
            
            avg_red = numpy.mean(button_rgb[:, :, 0])
            avg_green = numpy.mean(button_rgb[:, :, 1])
            avg_blue = numpy.mean(button_rgb[:, :, 2])
            
            is_reddish = (avg_red > 1.5 * avg_blue) and (avg_red > 1.5 * avg_green)
            
            if not is_reddish:
                click_center(res[0])
                time.sleep(0.5)
                click_center(res[0])
                logging.info("[*] Clicked 'End Sail' button")
                return True, False
            else:
                logging.info("[*] 'End Sail' button is red (cannot be clicked yet)")
                return True, True
    
    return False, False

# --------------------------------------------------
# Main Application Logic (for each cycle)
# --------------------------------------------------
class MainLogicThread(QThread):
    finished = Signal(object)

    def __init__(self, prev_distance, prev_time, start_distance, false_arrival_counter, alert_counter,
                   cycle_count, start_time, auto_steer_enabled, webhook_logging_enabled,
                   stop_distance, vehicle_top_speed, autopilot_mode=False, autopilot_callback=None):
        super().__init__()
        self.params = (prev_distance, prev_time, start_distance, false_arrival_counter, alert_counter,
                       cycle_count, start_time, auto_steer_enabled, webhook_logging_enabled,
                       stop_distance, vehicle_top_speed)
        self.autopilot_mode = autopilot_mode
        self.autopilot_callback = autopilot_callback

    def run(self):
        try:
            results = run_main_logic(*self.params, autopilot_mode=self.autopilot_mode, autopilot_callback=self.autopilot_callback)
            self.finished.emit(results)
        except Exception as e:
            logging.error(f"[!] Error in MainLogicThread: {str(e)}")
            self.finished.emit(None)

def run_main_logic(prev_distance, prev_time, start_distance, false_arrival_counter, alert_counter,
                   cycle_count, start_time, auto_steer_enabled, webhook_logging_enabled,
                   stop_distance, vehicle_top_speed, autopilot_mode=False, autopilot_callback=None):
    cycle_count += 1

    if autopilot_mode and not autopilot_callback:
        return prev_distance, prev_time, start_distance, false_arrival_counter, alert_counter, cycle_count

    screen_width, screen_height = pyautogui.size()
    x, y = screen_width // 2, screen_height // 2
    
    cross_mouse.left_click_xy_natural(x, y, delay=0.3, min_variation=-3, max_variation=3,
                                use_every=4, sleeptime=(0.005, 0.009), print_coords=False, percent=90)

    keyboard.type('5')
    formatted_time = datetime.datetime.now().strftime("%I:%M:%S %p")
    current_time = time.time()
    ocr_text, ocr_results = capture_and_process_screenshot()
    logging.info("[$] OCR text: " + ocr_text)

    hide_results = [res for res in ocr_results if res[1] in ("Hide", "> Hide")]
    for res in hide_results:
        click_center(res[0])
        alert("[*] Chat/Player UI was expanded. Successfully closed.", include_screenshot=False)

    current_distance = extract_distance(ocr_text)
    if current_distance is None:
        if autopilot_mode and autopilot_callback:
            target_info = extract_target_bearing(ocr_text)
            current_bearing_val = extract_current_bearing(ocr_text)
            if target_info is None and current_bearing_val is None and "disconnect" not in ocr_text.lower() and "join game" not in ocr_text.lower():
                alert("[!] ROBLOX crashed.", include_screenshot=True)
            else:
                alert("[!] ROBLOX disconnected.", include_screenshot=True)
                reconnect_sequence()
        alert_counter += 1
        prev_time = current_time
        return prev_distance, prev_time, start_distance, false_arrival_counter, alert_counter, cycle_count

    logging.info(f"[$] Extracted Distance: {current_distance} nm")
    if prev_distance is not None and prev_time is not None:
        elapsed = current_time - prev_time
        expected_distance = vehicle_top_speed * (elapsed / 3600)
        threshold = expected_distance - LEEWAY
        movement = prev_distance - current_distance

        if abs(movement) > 20:
            logging.warning(f"[*] OCR Error: Movement value too high: {movement:.2f} nm")
            movement = 0.01
            return prev_distance, prev_time, start_distance, false_arrival_counter, alert_counter, cycle_count

        logging.info(f"[$] Elapsed: {elapsed:.2f} sec, Expected: {expected_distance:.2f} nm, Threshold: {threshold:.2f} nm")
        logging.info(f"[$] Movement this cycle: {movement:.2f} nm")
        if webhook_logging_enabled:
            if cycle_count % 5 == 0 and movement != 0:
                eta_hours = (current_distance / movement) / 60
                completion = (((start_distance - current_distance) / start_distance) * 100) if start_distance and start_distance > 0 else 0
                alert(f"[?] ETA: {eta_hours:.2f} Hours, {completion:.2f}% Completed.", include_screenshot=True)
            alert(f"[$] Elapsed: {elapsed:.2f} sec, Movement: {movement:.2f} nm, Distance: {current_distance} nm", include_screenshot=False)
        if movement == 0:
            alert(f"[!] Possible island collision!", include_screenshot=True)
            alert_counter += 1
            
            if autopilot_mode and false_arrival_counter >= 2:
                if autopilot_callback:
                    alert("[*] Vehicle has stopped. Initiating AutoPilot final phase.", include_screenshot=False)
                    autopilot_callback()
    else:
        alert("[$] System Start", include_screenshot=False)
        alert(f"[$] AeroHelper System Start time: {formatted_time}", include_screenshot=False)
        start_distance = current_distance
        movement = 0

    prev_distance = current_distance
    prev_time = current_time

    if current_distance < stop_distance:
        if not autopilot_mode:
            keyboard.press("z")
            time.sleep(0.1)
            keyboard.release("z")
            alert("[!] Boat needs manual docking. Vehicle is currently stopping.", include_screenshot=True)
            false_arrival_counter += 1
            alert_counter += 1
            
            if false_arrival_counter >= 3:
                alert("[!] Vehicle has stopped, closing System.", include_screenshot=True)
                alert(f"[!] Total elapsed time: {current_time - start_time:.2f} seconds.", include_screenshot=False)
                sys.exit()
        
        elif autopilot_mode and autopilot_callback:
            keyboard.press("z")
            time.sleep(0.3)
            keyboard.release("z")
            
            alert("[*] Destination reached. Starting AutoPilot Phase 2.", include_screenshot=False)
            if autopilot_callback:
                autopilot_callback()
                return prev_distance, prev_time, start_distance, 0, alert_counter, cycle_count
    else:
        if false_arrival_counter >= 1:
            alert("[!] False Arrival detected, Vehicle is resuming trip.", include_screenshot=False)
            false_arrival_counter = 0
            keyboard.press('w')
            time.sleep(3)
            keyboard.release('w')

    if auto_steer_enabled:
        if not autopilot_mode or (autopilot_mode and autopilot_callback):
            threading.Thread(target=run_autosteer, args=(ocr_text,)).start()
            if webhook_logging_enabled:
                try:
                    res = extract_target_bearing(ocr_text)
                    if res:
                        dest, target = res
                        current_bearing = extract_current_bearing(ocr_text)
                        if current_bearing is not None:
                            alert(f"[$] AutoSteer: Current: {current_bearing}, Target: {target}", include_screenshot=False)
                except Exception as e:
                    logging.error(f"[!] Error in AutoSteer logging: {str(e)}")

    if movement is not None and movement > 0 and alert_counter > 0:
        alert_counter = 0

    return prev_distance, prev_time, start_distance, false_arrival_counter, alert_counter, cycle_count


# --------------------------------------------------
# Helper functions for AutoPilot
# --------------------------------------------------
class AutoPilotThread(QThread):
    finished = Signal(bool) # MODIFIED: Changed from pyqtSignal to Signal

    def __init__(self, is_final_phase=False):
        super().__init__()
        self.is_final_phase = is_final_phase
    
    def retry_action(self, action, max_attempts=3, description="action"):
        for attempt in range(max_attempts):
            if action():
                logging.info(f"[$] Successfully completed {description}")
                return True
            time.sleep(1)
            logging.info(f"[$] Retry {attempt+1}/{max_attempts} for {description}")
        logging.error(f"[!] Failed to complete {description} after {max_attempts} attempts")
        return False
    
    def final_phase(self):
        logging.info("[$] Starting final phase of AutoPilot")
        alert("[*] Starting final phase of AutoPilot", include_screenshot=False)
        
        time.sleep(15)
        
        max_attempts = 10
        found_end_sail = False
        is_red = False
        docking_attempts = 0
        
        while docking_attempts < max_attempts:

            found_end_sail, is_red = check_for_end_sail()
            
            if found_end_sail and not is_red:
                logging.info("[$] End Sail button is clickable, proceeding to next job")
                alert("[*] End Sail button is clickable, proceeding to next job", include_screenshot=False)
                time.sleep(5)
                return self.initial_phase()
            
            elif found_end_sail and is_red:
                docking_attempts += 1
                logging.info(f"[$] End Sail button is red. Starting precision docking attempt {docking_attempts}")
                alert(f"[*] End Sail button is red. Starting precision docking attempt {docking_attempts}", include_screenshot=False)
                
                logging.info("[$] Moving forward slightly")
                keyboard.press('w')
                time.sleep(3)
                keyboard.release('w')
                
                time.sleep(3 * MULTIPLIER)
                
                ocr_text, ocr_results = capture_and_process_screenshot()
                current_distance = extract_distance(ocr_text)
                if current_distance is not None:
                    logging.info(f"[$] Current distance after movement: {current_distance} nm")
                    
                    if current_distance > 0.1:
                        logging.info("[$] Still too far from dock, moving forward more")
                        keyboard.press('w')
                        time.sleep(3)
                        keyboard.release('w')
                    elif current_distance < 0:
                        logging.info("[$] Overshot dock, moving backward")
                        keyboard.press('z')
                        time.sleep(20 * MULTIPLIER)
                        keyboard.release('z')
                    else:
                        logging.info("[$] At good docking distance, stopping")
                        keyboard.press('z')
                        time.sleep(0.3)
                        keyboard.release('z')

                time.sleep(3)
                continue
            
            else:
                logging.warning(f"[!] End Sail button not found on attempt {docking_attempts}")
                if docking_attempts >= max_attempts/2:
                    alert("[!] Cannot find End Sail button. Check if you're at the correct dock.", include_screenshot=True)
                time.sleep(3)
            
        if docking_attempts >= max_attempts:
            logging.error("[!] Maximum docking attempts reached and End Sail button still red/not found")
            alert("[!] Maximum docking attempts reached. Manual intervention required.", include_screenshot=True)
            return False
        
        return False
    
    def initial_phase(self):
        logging.info("[$] Starting initial phase of AutoPilot")
        alert("[*] Starting initial phase of AutoPilot", include_screenshot=False)
        
        def check_refuel():
            ocr_text, ocr_results = capture_and_process_screenshot()
            for res in ocr_results:
                if "refuel" in res[1].lower():
                    click_center(res[0])
                    click_center(res[0])
                    return True
            return False
        
        check_refuel()
        time.sleep(2)
        
        def check_menu():
            ocr_text, ocr_results = capture_and_process_screenshot()
            return "return to lobby" in ocr_text.lower()
        
        if not self.retry_action(check_menu, description="menu check"):
            logging.error("[!] Must start from lobby menu.")
            alert("[!] Must start from lobby menu.", include_screenshot=True)
            return False
        
        Aocr_text, Aocr_results = capture_and_process_screenshot()
        
        def click_jobs():
            ocr_text, ocr_results = capture_and_process_screenshot()
            for res in ocr_results:
                if "jobs" in res[1].lower():
                    click_center(res[0])
                    return True
            return False
        
        if not self.retry_action(click_jobs, description="clicking jobs button"):
            logging.error("[!] Could not find jobs button.")
            alert("[!] Could not find jobs button.", include_screenshot=True)
            return False

        airport_matches = []
        
        def find_current_airport():
            nonlocal airport_matches
            airport_matches = []
            for airport in AIRPORT_ROUTES.keys():
                if airport in Aocr_text.lower():
                    airport_matches.append(airport)
            return len(airport_matches) == 1
        
        if not self.retry_action(find_current_airport, description="finding current airport"):
            if len(airport_matches) > 1:
                error_msg = f"[!] Multiple airports detected: {', '.join(airport_matches)}"
            else: 
                error_msg = "[!] No valid airport detected. Ensure you are using one of the supported airports."
            logging.error(error_msg)
            alert(error_msg, include_screenshot=True)
            return False
        
        current_airport = airport_matches[0]
        logging.info(f"[$] Found airport: {current_airport}")
        alert(f"[*] Found airport: {current_airport}", include_screenshot=False)

        destinations = AIRPORT_ROUTES[current_airport]
        best_wp = 0
        best_dest = None
        search_coords = None
        destination_found = False
        
        for attempt in range(3):
            if destination_found:
                break
                
            logging.info(f"[$] Destination finding attempt {attempt+1}/3")
            
            for dest in destinations:
                def click_search():
                    nonlocal search_coords
                    ocr_text, ocr_results = capture_and_process_screenshot()
                    for res in ocr_results:
                        if res[1].strip().lower() == "search":
                            search_coords = res[0]
                            click_center(res[0])
                            time.sleep(1)
                            keyboard.type(dest)
                            time.sleep(1)
                            return True
                    return False

                if not self.retry_action(click_search, max_attempts=5, description=f"searching for {dest}"):
                    continue
                    
                def click_transport():
                    time.sleep(3)  # Idrk why this works but it does so its a keeper
                    ocr_text, ocr_results = capture_and_process_screenshot()
                    for res in ocr_results:
                        res_text_no_spaces = res[1].lower().replace(" ", "")
                        search_text_no_spaces = f"transportto{dest}".lower().replace(" ", "")
                        if search_text_no_spaces in res_text_no_spaces:
                            click_center(res[0])
                            return True
                    
                    logging.info(f"[$] OCR results when looking for transport to {dest}:")
                    for res in ocr_results:
                        logging.info(f"[$] OCR text: {res[1]}")
                    
                    return False
                
                if not self.retry_action(click_transport, max_attempts=5, description=f"selecting transport to {dest}"):
                    if search_coords:
                        x = int((search_coords[0][0] + search_coords[2][0]) / 2)
                        y = int((search_coords[0][1] + search_coords[2][1]) / 2)
                        cross_mouse.left_click_xy_natural(x, y, delay=0.3, min_variation=-3, max_variation=3,
                                        use_every=4, sleeptime=(0.005, 0.009), print_coords=False, percent=90)
                        time.sleep(0.5)
                        
                        for _ in range(40):
                            keyboard.press(Key.backspace)
                            time.sleep(0.05)
                            keyboard.release(Key.backspace)
                        for _ in range(40):
                            keyboard.press(Key.delete)
                            time.sleep(0.05)
                            keyboard.release(Key.delete)
                        time.sleep(0.5)
                    continue
                
                wp_found = False
                def get_wp_value():
                    nonlocal best_wp, best_dest, wp_found
                    ocr_text, ocr_results = capture_and_process_screenshot()
                    wp_match = re.search(r"wp:\s*(\d+)", ocr_text.lower())
                    if wp_match:
                        wp = int(wp_match.group(1))
                        logging.info(f"[$] Found WP: {wp} for destination: {dest}")
                        if wp > best_wp:
                            best_wp = wp
                            best_dest = dest
                        wp_found = True
                        return True
                    return False
                
                if self.retry_action(get_wp_value, max_attempts=3, description=f"getting WP value for {dest}"):
                    destination_found = True
                
                if search_coords:
                    x = int((search_coords[0][0] + search_coords[2][0]) / 2)
                    y = int((search_coords[0][1] + search_coords[2][1]) / 2)
                    cross_mouse.left_click_xy_natural(x, y, delay=0.3, min_variation=-3, max_variation=3,
                                    use_every=4, sleeptime=(0.005, 0.009), print_coords=False, percent=90)
                    time.sleep(0.5)
                    
                    for _ in range(40):
                        keyboard.press(Key.backspace)
                        time.sleep(0.05)
                        keyboard.release(Key.backspace)
                    for _ in range(40):
                        keyboard.press(Key.delete)
                        time.sleep(0.05)
                        keyboard.release(Key.delete)
                    time.sleep(0.5)
            
            if not destination_found and attempt < 2:
                logging.info("[$] No destinations found, refreshing the jobs page")
                if not self.retry_action(click_jobs, description="refreshing jobs page"):
                    logging.error("[!] Failed to refresh jobs page")
                time.sleep(3)
        
        if not best_dest:
            logging.error("[!] Could not find any valid destinations, refreshing the jobs page")
            alert("[!] Could not find any valid destinations, refreshing the jobs page", include_screenshot=True)
            if not self.retry_action(click_jobs, description="refreshing jobs page"):
                logging.error("[!] Failed to refresh jobs page")
            time.sleep(3)
        
        logging.info(f"[$] Best destination: {best_dest} with WP: {best_wp}")
        alert(f"[*] Best destination: {best_dest} with WP: {best_wp}", include_screenshot=False)
        
        def select_best_job():
            ocr_text, ocr_results = capture_and_process_screenshot()
            for res in ocr_results:
                if res[1].strip().lower() == "search":
                    search_coords = res[0]
                    click_center(res[0])
                    time.sleep(0.5)
                    keyboard.type(best_dest)
                    time.sleep(1)
                    
                    ocr_text, ocr_results = capture_and_process_screenshot()
                    for res in ocr_results:
                        res_text_no_spaces = res[1].lower().replace(" ", "")
                        search_text_no_spaces = f"transportto{best_dest}".lower().replace(" ", "")
                        if search_text_no_spaces in res_text_no_spaces:
                            click_center(res[0])
                            time.sleep(0.5)
                            
                            if search_coords:
                                x = int((search_coords[0][0] + search_coords[2][0]) / 2)
                                y = int((search_coords[0][1] + search_coords[2][1]) / 2)
                                cross_mouse.left_click_xy_natural(x, y, delay=0.3, min_variation=-3, max_variation=3,
                                            use_every=4, sleeptime=(0.005, 0.009), print_coords=False, percent=90)
                                time.sleep(0.5)
                                
                                for _ in range(40):
                                    keyboard.press(Key.backspace)
                                    time.sleep(0.05)
                                    keyboard.release(Key.backspace)
                                for _ in range(40):
                                    keyboard.press(Key.delete)
                                    time.sleep(0.05)
                                    keyboard.release(Key.delete)
                                time.sleep(0.5)
                            
                            return True
                    
                    logging.error(f"[!] Could not find transport button for {best_dest}")
                    alert(f"[!] Could not find transport button for {best_dest}", include_screenshot=True)
                    return False
            return False
        
        if not self.retry_action(select_best_job, description="selecting best job"):
            logging.error("[!] Could not select the best job.")
            alert("[!] Could not select the best job.", include_screenshot=True)
            return False
        
        def click_begin():
            ocr_text, ocr_results = capture_and_process_screenshot()
            for res in ocr_results:
                if "begin" in res[1].lower():
                    click_center(res[0])
                    return True
            return False
        
        if not self.retry_action(click_begin, description="clicking begin"):
            logging.error("[!] Could not find begin button.")
            alert("[!] Could not find begin button.", include_screenshot=True)
            return False
        
        time.sleep(10)
        keyboard.press('e')
        keyboard.release('e')
        logging.info("[*] 'e' key pressed to start engine.")
        alert("[*] 'e' key pressed to start engine.", include_screenshot=False)

        time.sleep(30)

        keyboard.press('w')
        time.sleep(3)
        keyboard.release('w')
        logging.info("[*] Held 'w' for 3 seconds to accelerate.")
        alert("[*] Held 'w' for 3 seconds to accelerate.", include_screenshot=False)
        
        self.finished.emit(True)
        return True
    
    def run(self):
        try:
            time.sleep(5)
            logging.info(f"[$] AutoPilot {'final' if self.is_final_phase else 'initial'} phase started")
            
            if self.is_final_phase:
                success = self.final_phase()
            else:
                success = self.initial_phase()
                
            if not success:
                self.finished.emit(False)
            
        except Exception as e:
            logging.error(f"[!] AutoPilot Error: {str(e)}")
            alert(f"[!] AutoPilot Error: {str(e)}", include_screenshot=True)
            self.finished.emit(False)

class AeroHelperApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint) # MODIFIED: Enum path
        self.config = load_config()
        self.autopilot_mode = False
        self.autopilot_ready = False
        self.autopilot_thread = None
        self.autopilot_final_phase = False
        self.start_mid_mission = False
        self.set_app_icon()
        
        check_platform_requirements()
        
        self.init_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.run_AeroHelper_Logic)
        self.is_running = False

        self.previous_distance = None
        self.previous_time = None
        self.start_distance = None
        self.false_arrival_counter = 0
        self.alert_counter = 0
        self.cycle_count = 0
        self.start_time = time.time()

        self.auto_steer_enabled = False
        self.webhook_logging_enabled = False

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.remaining_cycle_time = 0
        
    def set_app_icon(self):
        try:
            icon = QIcon(":/icon.png") 
            self.setWindowIcon(icon)
        except Exception as e:
            logging.error(f"[!] Failed to set application icon: {str(e)}")

    def init_ui(self):
        self.setWindowTitle('AeroHelper v' + VERSION)

        if platform.system() == "Darwin":
            self.setStyleSheet("""
                QWidget {
                    font-size: 13px;
                }
                QPushButton {
                    padding: 5px;
                    border-radius: 4px;
                }
            """)
        
        start_container = QWidget()
        start_layout = QVBoxLayout(start_container)
        
        self.start_button = QPushButton('Start', self)
        self.start_button.clicked.connect(self.toggle_logic)
        start_layout.addWidget(self.start_button)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine) # MODIFIED: Enum path
        separator.setFrameShadow(QFrame.Shadow.Sunken) # MODIFIED: Enum path
        start_layout.addWidget(separator)

        layout = QVBoxLayout(self)
        layout.addWidget(start_container)
        
        self.autosteer_button = QPushButton('AutoSteer', self)
        self.autosteer_button.clicked.connect(self.toggle_AutoSteer)
        self.autopilot_button = QPushButton('AutoPilot', self)
        self.autopilot_button.clicked.connect(self.toggle_AutoPilot)
        self.mid_mission_checkbox = QCheckBox("Start AutoPilot mid-mission", self)
        self.mid_mission_checkbox.stateChanged.connect(self.toggle_mid_mission)
        self.mid_mission_checkbox.setEnabled(False)
        self.webhooknotif_button = QPushButton('Debug Notifications', self)
        self.webhooknotif_button.clicked.connect(self.toggle_WebhookNotif)

        self.ship_speed_input = QLineEdit(self)
        self.ship_speed_input.setPlaceholderText("Enter vehicle's top speed")
        self.ship_speed_label = QLabel("Vehicle's Top Speed (Knots)", self)

        self.stop_distance_input = QLineEdit(self)
        self.stop_distance_input.setPlaceholderText("1-5 Recommended")
        self.stop_distance_label = QLabel("Stop Distance from Destination (nm)", self)

        self.cycle_interval_label = QLabel("System Cycle Interval (Minutes)", self)
        cycle_layout = QHBoxLayout()
        self.cycle_interval_input = QLineEdit(self)
        self.cycle_interval_input.setPlaceholderText("1-3 Recommended")
        self.cycle_timer_label = QLabel("00:00", self)
        cycle_layout.addWidget(self.cycle_interval_input)
        cycle_layout.addWidget(self.cycle_timer_label)

        self.leeway_label = QLabel("Leeway (nm)", self)
        self.leeway_input = QLineEdit(self)
        self.leeway_input.setPlaceholderText("0.3 Recommended")
        
        self.multiplier_label = QLabel("Turning Multiplier", self)
        self.multiplier_input = QLineEdit(self)
        self.multiplier_input.setPlaceholderText("Keep between .5-2. Ensure no auscultation")
        
        self.webhook_url_label = QLabel("Webhook URL", self)
        self.webhook_url_input = QLineEdit(self)
        self.webhook_url_input.setPlaceholderText("Enter Webhook URL")
        
        if self.config:
            self.webhook_url_input.setText(self.config.get("webhook_url", "YOUR_WEBHOOK_URL"))
            self.ship_speed_input.setText(str(self.config.get("ship_top_speed")))
            self.stop_distance_input.setText(str(self.config.get("stop_distance")))
            self.cycle_interval_input.setText(str(self.config.get("cycle_interval")))
            self.leeway_input.setText(str(self.config.get("leeway")))
            self.multiplier_input.setText(str(self.config.get("multiplier")))
        
        layout.addWidget(self.autopilot_button)
        layout.addWidget(self.mid_mission_checkbox)
        layout.addWidget(self.autosteer_button)
        layout.addWidget(self.webhooknotif_button)
        layout.addWidget(self.ship_speed_label)
        layout.addWidget(self.ship_speed_input)
        layout.addWidget(self.stop_distance_label)
        layout.addWidget(self.stop_distance_input)
        layout.addWidget(self.cycle_interval_label)
        layout.addLayout(cycle_layout)
        layout.addWidget(self.leeway_label)
        layout.addWidget(self.leeway_input)
        layout.addWidget(self.multiplier_label)
        layout.addWidget(self.multiplier_input)
        layout.addWidget(self.webhook_url_label)
        layout.addWidget(self.webhook_url_input)
        self.setLayout(layout)
        self.setGeometry(300, 300, 300, 450)
        
    def toggle_AutoSteer(self):
        if not self.auto_steer_enabled:
            self.auto_steer_enabled = True
            self.autosteer_button.setText('AutoSteer ✓')
        else:
            self.auto_steer_enabled = False
            self.autosteer_button.setText('AutoSteer')

    def toggle_AutoPilot(self):
        if self.autopilot_mode:
            self.autopilot_mode = False
            self.autopilot_button.setText('AutoPilot')
            self.autopilot_ready = False
            self.autopilot_final_phase = False
            self.mid_mission_checkbox.setEnabled(False)
            self.mid_mission_checkbox.setChecked(False)
            self.start_mid_mission = False
            
            if not self.is_running:
                self.ship_speed_input.setDisabled(False)
                self.stop_distance_input.setDisabled(False)
                self.cycle_interval_input.setDisabled(False)
                self.leeway_input.setDisabled(False)
                self.multiplier_input.setDisabled(False)
                self.webhook_url_input.setDisabled(False)
        else:
            self.autopilot_mode = True
            self.autopilot_button.setText('AutoPilot ✓')
            self.mid_mission_checkbox.setEnabled(True)
            
            self.auto_steer_enabled = True
            self.autosteer_button.setText('AutoSteer ✓')
            
            self.ship_speed_input.setDisabled(True)
            self.stop_distance_input.setDisabled(True)
            self.cycle_interval_input.setDisabled(True)
            self.leeway_input.setDisabled(True)
            self.multiplier_input.setDisabled(True)
            self.webhook_url_input.setDisabled(True)
    
    def start_autopilot_thread(self, is_final_phase=False):
        if self.autopilot_thread and self.autopilot_thread.isRunning():
            self.autopilot_thread.terminate()
            self.autopilot_thread.wait()
            
        try:
            self.autopilot_final_phase = is_final_phase
            self.autopilot_thread = AutoPilotThread(is_final_phase=is_final_phase)
            self.autopilot_thread.finished.connect(self.on_autopilot_finished)
            self.autopilot_thread.start()
            logging.info(f"[$] AutoPilot {'final' if is_final_phase else 'initial'} phase started")
        except Exception as e:
            logging.error(f"[!] AutoPilot Error: {str(e)}")
            alert(f"[!] Failed to start AutoPilot: {str(e)}", include_screenshot=False)
            QMessageBox.critical(self, "Error", f"AutoPilot failed to start: {str(e)}")

    def on_autopilot_finished(self, success=False):
        if self.autopilot_final_phase:
            if success:
                self.autopilot_final_phase = False
                self.previous_distance = None
                self.previous_time = None
                self.start_distance = None
                self.false_arrival_counter = 0
                alert("[*] New job started successfully. AutoPilot cycle complete.", include_screenshot=False)
            else:
                alert("[!] Failed to complete AutoPilot final phase. Manual intervention required.", include_screenshot=True)
                QMessageBox.warning(self, "AutoPilot Warning", "Failed to complete final phase. Manual intervention required.")
        else:
            if success:
                self.autopilot_ready = True
                alert("[*] AutoPilot initial phase complete. Using AutoSteer for navigation.", include_screenshot=False)
                self.timer.start(self.cycle_interval)
            else:
                self.autopilot_mode = False
                self.autopilot_ready = False
                self.autopilot_button.setText('AutoPilot')
                self.is_running = False
                self.start_button.setText('Start')
                
            if not self.is_running:
                self.ship_speed_input.setDisabled(False)
                self.stop_distance_input.setDisabled(False)
                self.cycle_interval_input.setDisabled(False)
                self.leeway_input.setDisabled(False)
                self.multiplier_input.setDisabled(False)
                self.webhook_url_input.setDisabled(False)
                
                QMessageBox.critical(self, "AutoPilot Error", "Failed to initialize AutoPilot. Check the logs for details.")

    def toggle_WebhookNotif(self):
        if not self.webhook_logging_enabled:
            self.webhook_logging_enabled = True
            self.webhooknotif_button.setText('Debug Notifications ✓')
        else:
            self.webhook_logging_enabled = False
            self.webhooknotif_button.setText('Debug Notifications')
    
    def toggle_logic(self):
        global LEEWAY, MULTIPLIER, WEBHOOK_URL
        if self.is_running:
            self.is_running = False
            self.start_button.setText('Resume')
            self.timer.stop()
            self.countdown_timer.stop()
            
            if hasattr(self, 'main_logic_thread') and self.main_logic_thread.isRunning():
                self.main_logic_thread.terminate()
                self.main_logic_thread.wait()
            
            if self.autopilot_mode and self.autopilot_thread and self.autopilot_thread.isRunning():
                self.autopilot_thread.terminate()
                self.autopilot_thread.wait()
                self.autopilot_ready = False
                self.autopilot_final_phase = False
            
            logging.info("[!] AeroHelper paused.")
            alert("[!] AeroHelper paused.", include_screenshot=False)
            
            if not self.autopilot_mode:
                self.ship_speed_input.setDisabled(False)
                self.stop_distance_input.setDisabled(False)
                self.cycle_interval_input.setDisabled(False)
                self.leeway_input.setDisabled(False)
                self.multiplier_input.setDisabled(False)
                self.webhook_url_input.setDisabled(False)
                
            return
        
        try:
            if not self.ship_speed_input.text().strip():
                error_msg = "Vehicle's Top Speed is required"
                logging.error(f"[!] {error_msg}")
                alert(f"[!] {error_msg}", include_screenshot=False)
                QMessageBox.critical(self, "Error", error_msg)
                return
                
            if not self.stop_distance_input.text().strip():
                error_msg = "Stop Distance is required"
                logging.error(f"[!] {error_msg}")
                alert(f"[!] {error_msg}", include_screenshot=False)
                QMessageBox.critical(self, "Error", error_msg)
                return
                
            if not self.cycle_interval_input.text().strip():
                error_msg = "Cycle Interval is required"
                logging.error(f"[!] {error_msg}")
                alert(f"[!] {error_msg}", include_screenshot=False)
                QMessageBox.critical(self, "Error", error_msg)
                return
                
            if not self.leeway_input.text().strip():
                error_msg = "Leeway is required"
                logging.error(f"[!] {error_msg}")
                alert(f"[!] {error_msg}", include_screenshot=False)
                QMessageBox.critical(self, "Error", error_msg)
                return
                
            if not self.multiplier_input.text().strip():
                error_msg = "Turning Multiplier is required"
                logging.error(f"[!] {error_msg}")
                alert(f"[!] {error_msg}", include_screenshot=False)
                QMessageBox.critical(self, "Error", error_msg)
                return
                
            webhook_url = self.webhook_url_input.text().strip()
            if webhook_url:
                if not webhook_url.startswith('https://'):
                    error_msg = "Webhook URL must start with 'https://'"
                    logging.error(f"[!] {error_msg}")
                    alert(f"[!] {error_msg}", include_screenshot=False)
                    QMessageBox.critical(self, "Error", error_msg)
                    return
            else:
                error_msg = "Webhook URL is required"
                logging.error(f"[!] {error_msg}")
                alert(f"[!] {error_msg}", include_screenshot=False)
                QMessageBox.critical(self, "Error", error_msg)
                return

            self.stop_distance = float(self.stop_distance_input.text())

            if self.previous_distance is None:
                try:
                    self.cycle_interval = int(float(self.cycle_interval_input.text()) * 60 * 1000)
                    vehicle_top_speed = float(self.ship_speed_input.text())
                    LEEWAY = float(self.leeway_input.text())
                    MULTIPLIER = float(self.multiplier_input.text())
                    WEBHOOK_URL = webhook_url

                    config_data = {
                        "webhook_url": WEBHOOK_URL,
                        "ship_top_speed": vehicle_top_speed,
                        "stop_distance": self.stop_distance,
                        "cycle_interval": float(self.cycle_interval) / (60 * 1000),
                        "leeway": LEEWAY,
                        "multiplier": MULTIPLIER,
                    }
                    save_config(config_data)
                    
                    self.ship_speed_input.setDisabled(True)
                    self.stop_distance_input.setDisabled(True)
                    self.cycle_interval_input.setDisabled(True)
                    self.leeway_input.setDisabled(True)
                    self.multiplier_input.setDisabled(True)
                    self.webhook_url_input.setDisabled(True)
                except Exception as e:
                    error_msg = f"Invalid input values: {str(e)}"
                    logging.error(f"Error starting AeroHelper: {error_msg}")
                    alert(f"[!] {error_msg}", include_screenshot=False)
                    QMessageBox.critical(self, "Error", error_msg)
                    return

            if self.autopilot_mode:
                if self.start_mid_mission:
                    is_valid_mission = self.check_mid_mission_destination()
                    if not is_valid_mission:
                        return
                    
                    self.autopilot_ready = True
                    self.is_running = True
                    self.start_button.setText('Pause')
                    self.timer.start(self.cycle_interval)
                    logging.info("[!] AeroHelper started in mid-mission AutoPilot mode.")
                    alert("[*] AeroHelper started in mid-mission AutoPilot mode.", include_screenshot=False)
                    return
                elif not self.autopilot_ready and not self.autopilot_final_phase:
                    self.start_autopilot_thread(is_final_phase=False)
                    self.is_running = True
                    self.start_button.setText('Pause')
                    logging.info("[!] AeroHelper started in AutoPilot mode.")
                    alert("[*] AeroHelper started in AutoPilot mode.", include_screenshot=False)
                    return
            
            self.is_running = True
            self.start_button.setText('Pause')
            
            self.save_current_config()

            self.cycle_interval = int(float(self.cycle_interval_input.text()) * 60 * 1000)
            self.remaining_cycle_time = self.cycle_interval / 1000
            self.update_countdown()
            self.countdown_timer.start(1000)

            self.timer.start(self.cycle_interval)
            logging.info("[!] AeroHelper " + ("started" if self.previous_distance is None else "resumed") + ".")
            alert("[*] AeroHelper " + ("started" if self.previous_distance is None else "resumed") + ".", include_screenshot=False)
            if self.previous_distance is not None:
                self.run_AeroHelper_Logic()


        except ValueError as e:
            error_msg = "Invalid number format. Please check your inputs."
            logging.error(f"Error parsing inputs: {error_msg}")
            alert(f"[!] {error_msg}", include_screenshot=False)
            QMessageBox.critical(self, "Error", error_msg)

    def run_AeroHelper_Logic(self):
        if not self.is_running:
            return

        self.remaining_cycle_time = self.cycle_interval / 1000
        self.update_countdown()
            
        if self.autopilot_mode and not self.autopilot_ready:
            return
            
        if self.autopilot_final_phase:
            return

        if hasattr(self, 'main_logic_thread') and self.main_logic_thread.isRunning():
            logging.info("[$] Main logic thread is already running. Skipping this cycle.")
            return

        self.remaining_cycle_time = self.cycle_interval / 1000
        self.update_countdown()

        try:
            vehicle_speed = float(self.ship_speed_input.text())
            
            self.main_logic_thread = MainLogicThread(
                self.previous_distance, self.previous_time, self.start_distance, self.false_arrival_counter,
                self.alert_counter, self.cycle_count, self.start_time, self.auto_steer_enabled,
                self.webhook_logging_enabled, self.stop_distance, vehicle_speed, 
                autopilot_mode=self.autopilot_mode, 
                autopilot_callback=self.start_final_phase if self.autopilot_mode else None
            )
            self.main_logic_thread.finished.connect(self.on_main_logic_finished)
            self.main_logic_thread.start()

        except ValueError as e:
            logging.error("Error in run_AeroHelper_Logic: " + str(e))
            QMessageBox.critical(self, "Error", "Invalid number format in vehicle speed.")
            self.toggle_logic()

    def on_main_logic_finished(self, results):
        if results:
            (self.previous_distance, self.previous_time, self.start_distance, 
             self.false_arrival_counter, self.alert_counter, self.cycle_count) = results
        else:
            logging.error("[!] Main logic thread failed to return results.")
            # Optionally, handle the error, e.g., by stopping the timer
            # self.toggle_logic()

    def update_countdown(self):
        if self.remaining_cycle_time > 0:
            self.remaining_cycle_time -= 1
            mins, secs = divmod(self.remaining_cycle_time, 60)
            self.cycle_timer_label.setText(f"{int(mins):02d}:{int(secs):02d}")

    def toggle_mid_mission(self, state):
        self.start_mid_mission = (state == 2)

    def check_mid_mission_destination(self):
        try:
            ocr_text, ocr_results = capture_and_process_screenshot()
            
            transport_pattern = r"transport\s*to\s*(.+?)\s*safely"
            match = re.search(transport_pattern, ocr_text.lower())
            
            if match:
                destination = match.group(1).strip()
                logging.info(f"[$] Mid-mission destination detected: {destination}")

                supported_airports = set()
                for airports in AIRPORT_ROUTES.values():
                    for airport in airports:
                        supported_airports.add(airport)
                
                supported_airports.update(AIRPORT_ROUTES.keys())
                
                destination_no_spaces = destination.replace(" ", "").lower()
                for airport in supported_airports:
                    airport_no_spaces = airport.replace(" ", "").lower()
                    if destination_no_spaces in airport_no_spaces or airport_no_spaces in destination_no_spaces:
                        logging.info(f"[$] Destination '{destination}' matches supported airport '{airport}'")
                        alert(f"[*] Starting mid-mission to '{airport}'", include_screenshot=False)
                        return True
                
                error_msg = f"Destination '{destination}' is not in the list of supported airports"
                logging.error(f"[!] {error_msg}")
                alert(f"[!] {error_msg}", include_screenshot=True)
                QMessageBox.critical(self, "Error", error_msg)
                return False
            else:
                error_msg = "No transport mission detected. Please ensure you're in a mission"
                logging.error(f"[!] {error_msg}")
                alert(f"[!] {error_msg}", include_screenshot=True)
                QMessageBox.critical(self, "Error", error_msg)
                return False
                
        except Exception as e:
            error_msg = f"Error checking mid-mission destination: {str(e)}"
            logging.error(f"[!] {error_msg}")
            alert(f"[!] {error_msg}", include_screenshot=True)
            QMessageBox.critical(self, "Error", error_msg)
            return False

    def start_final_phase(self):
        self.start_autopilot_thread(is_final_phase=True)

    def save_current_config(self):
        config_data = {
            "webhook_url": self.webhook_url_input.text(),
            "ship_top_speed": self.ship_speed_input.text(),
            "stop_distance": self.stop_distance_input.text(),
            "cycle_interval": self.cycle_interval_input.text(),
            "leeway": self.leeway_input.text(),
            "multiplier": self.multiplier_input.text()
        }
        save_config(config_data)

    def closeEvent(self, event):
        self.save_current_config()
        logging.info("[!] AeroHelper settings saved on exit.")
        super().closeEvent(event)
# --------------------------------------------------
# Application Entry Point
# --------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AeroHelperApp()
    window.show()
    sys.exit(app.exec()) # In PySide6, app.exec() is preferred over app.exec_()
