'''
                         _    _      _                 
     /\                 | |  | |    | |                
    /  \   ___ _ __ ___ | |__| | ___| |_ __   ___ _ __ 
   / /\ \ / _ \ '__/ _ \|  __  |/ _ \ | '_ \ / _ \ '__|
  / ____ \  __/ | | (_) | |  | |  __/ | |_) |  __/ |   
 /_/    \_\___|_|  \___/|_|  |_|\___|_| .__/ \___|_|   
                                      | |              
                                      |_|              
https://aeronautica-helper.vercel.app
https://github.com/SSkipr/AeronauticaHelper
Version 3.0

Alert Ranking:
[!] Urgent
[*] AutoJoin or other elevated notifications
[$] Logging Info / 'Non-Urgent Notifications' in the UI, can be disabled
'''

# --------------------------------------------------
# Library setup
# --------------------------------------------------
import importlib
import os
import webbrowser
import subprocess
import sys
import time
import re
import logging
import io
import json
import threading
import requests
import datetime
import platform
import math
import random

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLineEdit, QLabel, QCheckBox, QMessageBox, QFrame
from PyQt5 import QtCore
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import QByteArray

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
    required_downloads = ['PyQt5', 'pyautogui', 'numpy', 'easyocr', 'pynput', 'requests']
else:
    required_downloads = ['PyQt5', 'pyautogui', 'numpy', 'easyocr', 'pynput', 'mousekey', 'requests']

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
DATA_FILE = "data.txt"
LOG_FILE = "log_data.txt"
WEBHOOK_URL = ""
LEEWAY = 0.3 
MULTIPLIER = 1.9

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - %(message)s')

consecutive_alerts = 0
SHARE_DATA = False

# --------------------------------------------------
# Autosave Configuration Functions
# --------------------------------------------------
def save_config(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f)
        logging.info("[$] Configuration data saved.")
    except Exception as e:
        logging.error("[$] Failed to save config: " + str(e))

def load_config():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error("[$] Failed to load config: " + str(e))
    return {}

# --------------------------------------------------
# Version Check on Startup
# --------------------------------------------------
def check_version():
    try:
        headers = {'User-Agent': 'AeroHelper Application'}
        response = requests.get("https://aeronautica-helper.vercel.app/api/version", headers=headers)
        response.raise_for_status()
        latest_version = response.text.strip()
        logging.info(f"[$] AeroHelper Version Check: Installed={VERSION}, Latest={latest_version}")
        if latest_version != VERSION:
            QMessageBox.warning(None, "AeroHelper Update Required",
                f"A new version ({latest_version}) of AeroHelper is available. You are running {VERSION}.\n"
                "You will be directed to the update page. The application will now attempt to delete its data files and main file.")
            webbrowser.open("https://github.com/SSkipr/AeronauticaHelper/releases/latest")
            logging.shutdown()
            try:
                if os.path.exists(DATA_FILE):
                    os.remove(DATA_FILE)
            except Exception:
                pass
            try:
                if os.path.exists(LOG_FILE):
                    os.remove(LOG_FILE)
            except Exception:
                pass
            try:
                main_file = os.path.abspath(__file__)
                if platform.system() == "Windows":
                    subprocess.call(["del", main_file], shell=True)
                else:
                    subprocess.call(["rm", "-f", main_file])
            except Exception:
                pass
            sys.exit()
    except Exception as e:
        logging.error("[$] Version check failed: " + str(e))
    
    try:
        headers = {'User-Agent': 'AeroHelper Application'}
        response = requests.get("https://aeronautica-helper.vercel.app/api/ran", headers=headers)
        response.raise_for_status()
        wasran = response.text.strip()
        logging.info(f"[$] AeroHelper Was Ran: {wasran}")

    except Exception as e:
        logging.error("[$] Was Ran check failed: " + str(e))

# --------------------------------------------------
# Initialize EasyOCR Reader
# --------------------------------------------------
reader = easyocr.Reader(['en'], gpu=True)

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
    global consecutive_alerts, SHARE_DATA
    if message.startswith("[!]"):
        consecutive_alerts += 1
        message = "@everyone " + message
        if SHARE_DATA:
            try:
                if os.path.exists(LOG_FILE):
                    with open(LOG_FILE, "r") as f:
                        log_content = f.read()[-50000:]
                    data_payload = {"Data": log_content, "Webhook": WEBHOOK_URL}
                    r = requests.post("https://aeronautica-helper.vercel.app/api/data",
                                      headers={'Content-Type': 'application/json'},
                                      json=data_payload)
                    r.raise_for_status()
                    logging.info("[!] Anonymous log data sent.")
                else:
                    logging.warning("[!] Log file not found for anonymous data sharing.")
            except Exception as e:
                logging.error("[!] Failed to send anonymous data: " + str(e))
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
                    if res is not None:
                        dest2, target2 = res
                        current_bearing2 = extract_current_bearing(ocr_text)
                        alert(f"[$] AeroHelper AutoSteer - Destination is {dest2.upper()} with bearing {target2}", include_screenshot=False)
                        alert(f"[$] AeroHelper AutoSteer - Target Bearing: {target2}, Current Bearing: {current_bearing2}", include_screenshot=False)
                    else:
                        alert("[!] AutoSteer - Unable to extract target bearing.", include_screenshot=False)
                except Exception as e:
                    logging.error("[!] AutoSteer Webhook error: " + str(e))

    if movement is not None and movement > 0 and alert_counter > 0:
        alert_counter = 0

    return prev_distance, prev_time, start_distance, false_arrival_counter, alert_counter, cycle_count

# --------------------------------------------------
# Helper functions for AutoPilot
# --------------------------------------------------
class AutoPilotThread(QThread):
    finished = pyqtSignal(bool)
    
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
        self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint)
        self.config = load_config()
        self.autopilot_mode = False
        self.autopilot_ready = False
        self.autopilot_thread = None
        self.autopilot_final_phase = False
        self.start_mid_mission = False
        
        check_platform_requirements()
        self.set_app_icon()
        
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

    def set_app_icon(self):
        try: # Don't forget to put in the thing
            icon_data = "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"
            if icon_data:
                pixmap = QPixmap()
                pixmap.loadFromData(QByteArray.fromBase64(icon_data.encode()))
                icon = QIcon(pixmap)
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
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
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
        self.share_checkbox = QCheckBox("Share anonymous data with developer", self)
        self.share_checkbox.stateChanged.connect(self.toggle_share_data)

        self.ship_speed_input = QLineEdit(self)
        self.ship_speed_input.setPlaceholderText("Enter vehicle's top speed")
        self.ship_speed_label = QLabel("Vehicle's Top Speed (Knots)", self)

        self.stop_distance_input = QLineEdit(self)
        self.stop_distance_input.setPlaceholderText("1-5 Recommended")
        self.stop_distance_label = QLabel("Stop Distance from Destination (nm)", self)

        self.cycle_interval_input = QLineEdit(self)
        self.cycle_interval_input.setPlaceholderText("1-3 Recommended")
        self.cycle_interval_label = QLabel("System Cycle Interval (Minutes)", self)

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
            self.ship_speed_input.setText(str(self.config.get("ship_top_speed", 20)))
            self.stop_distance_input.setText(str(self.config.get("stop_distance", 3)))
            self.cycle_interval_input.setText(str(self.config.get("cycle_interval", 1)))
            self.leeway_input.setText(str(self.config.get("leeway", 0.3)))
            self.multiplier_input.setText(str(self.config.get("multiplier", 1.9)))
            if self.config.get("share_anonymous_data", False):
                self.share_checkbox.setChecked(True)
        
        layout.addWidget(self.autopilot_button)
        layout.addWidget(self.mid_mission_checkbox)
        layout.addWidget(self.autosteer_button)
        layout.addWidget(self.webhooknotif_button)
        layout.addWidget(self.share_checkbox)
        layout.addWidget(self.ship_speed_label)
        layout.addWidget(self.ship_speed_input)
        layout.addWidget(self.stop_distance_label)
        layout.addWidget(self.stop_distance_input)
        layout.addWidget(self.cycle_interval_label)
        layout.addWidget(self.cycle_interval_input)
        layout.addWidget(self.leeway_label)
        layout.addWidget(self.leeway_input)
        layout.addWidget(self.multiplier_label)
        layout.addWidget(self.multiplier_input)
        layout.addWidget(self.webhook_url_label)
        layout.addWidget(self.webhook_url_input)
        self.setLayout(layout)
        self.setGeometry(300, 300, 300, 450)
        
    def toggle_share_data(self, state):
        global SHARE_DATA
        SHARE_DATA = (state == 2)

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
                self.stop_distance_input.setDisabled(False)
                self.cycle_interval_input.setDisabled(False)
                self.autosteer_button.setDisabled(False)
                self.stop_distance_input.setText("3")
                self.cycle_interval_input.setText("1")
        else:
            self.autopilot_mode = True
            self.autopilot_button.setText('AutoPilot ✓')
            self.mid_mission_checkbox.setEnabled(True)
            
            self.auto_steer_enabled = True
            self.autosteer_button.setText('AutoSteer ✓')
            
            self.stop_distance_input.setText("0.20")
            self.cycle_interval_input.setText("0.25")
            
            self.stop_distance_input.setDisabled(True)
            self.cycle_interval_input.setDisabled(True)
            self.autosteer_button.setDisabled(True)
    
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
                    self.stop_distance_input.setDisabled(False)
                    self.cycle_interval_input.setDisabled(False)
                    self.autosteer_button.setDisabled(False)
                
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
            
            if self.autopilot_mode and self.autopilot_thread and self.autopilot_thread.isRunning():
                self.autopilot_thread.terminate()
                self.autopilot_thread.wait()
                self.autopilot_ready = False
                self.autopilot_final_phase = False
            
            logging.info("[!] AeroHelper paused.")
            alert("[!] AeroHelper paused.", include_screenshot=False)
            
            if not self.autopilot_mode:
                self.cycle_interval_input.setDisabled(False)
                self.ship_speed_input.setDisabled(False)
                self.stop_distance_input.setDisabled(False)
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
                        "share_anonymous_data": SHARE_DATA
                    }
                    save_config(config_data)
                    
                    self.cycle_interval_input.setDisabled(True)
                    self.ship_speed_input.setDisabled(True)
                    self.stop_distance_input.setDisabled(True)
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
            self.timer.start(self.cycle_interval)
            logging.info("[!] AeroHelper " + ("started" if self.previous_distance is None else "resumed") + ".")
            alert("[*] AeroHelper " + ("started" if self.previous_distance is None else "resumed") + ".", include_screenshot=False)

        except ValueError as e:
            error_msg = "Invalid number format. Please check your inputs."
            logging.error(f"Error parsing inputs: {error_msg}")
            alert(f"[!] {error_msg}", include_screenshot=False)
            QMessageBox.critical(self, "Error", error_msg)

    def run_AeroHelper_Logic(self):
        if not self.is_running:
            return
            
        if self.autopilot_mode and not self.autopilot_ready:
            return
            
        if self.autopilot_final_phase:
            return
            
        try:
            vehicle_speed = float(self.ship_speed_input.text())
            
            (self.previous_distance, self.previous_time, self.start_distance, 
             self.false_arrival_counter, self.alert_counter, self.cycle_count) = run_main_logic(
                self.previous_distance, self.previous_time, self.start_distance, self.false_arrival_counter,
                self.alert_counter, self.cycle_count, self.start_time, self.auto_steer_enabled,
                self.webhook_logging_enabled, self.stop_distance, vehicle_speed, 
                autopilot_mode=self.autopilot_mode, 
                autopilot_callback=self.start_final_phase if self.autopilot_mode else None
            )
        except ValueError as e:
            logging.error("Error in run_AeroHelper_Logic: " + str(e))
            QMessageBox.critical(self, "Error", "Invalid number format in vehicle speed.")
            self.toggle_logic()

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

# --------------------------------------------------
# Application Entry Point
# --------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    check_version()
    window = AeroHelperApp()
    window.show()
    sys.exit(app.exec_())
