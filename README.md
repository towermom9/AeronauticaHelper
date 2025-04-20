# <img src="https://github.com/user-attachments/assets/5dd9d0a5-c24b-4b94-9afa-a9692a72e46f" width="25" height="25" alt="AeroHelperLogo" /> AeronauticaHelper

---

## 🚀 Introduction

Welcome to **AeronauticaHelper** – your all-in-one AFK automation companion for [Aeronautica](https://www.roblox.com/games/6647962258/UPD-Aeronautica), the ship/aircraft simulator on Roblox.

> **Note:** The delay in the latest release was due to unexpected bugs and some real-life scheduling issues. Thanks for your patience!

This is not an exploit, nor malware. It's fully **open source**, and functions by:
- Taking a **screenshot**
- Processing it with [EasyOCR](https://pypi.org/project/easyocr/)
- Extracting values using **regex**
- Simulating **human-like mouse and keyboard actions**

---

## 🧾 Features

### ✅ AutoPilot

AutoPilot allows you to AFK full job cycles by:
- Refueling
- Accepting the highest-paying job
- Starting the boat
- Steering the ship
- Ending the route
- Repeating

It currently supports select routes between airports that allow straight-line navigation.
<details><summary>🌍 Supported Routes</summary>

- **Leovetsk ⇄ Auchenburgh**  
- **Leovetsk ⇄ Tierdam**  
- **Nordspyd ⇄ Tenera Palm**
- **Nordspyd ⇄ Norman**
- **Norman ⇄ Auchenburgh**

More to come. Suggest more via [@sskipr](https://discord.gg/3adphMca)!

</details>

### 🧭 AutoSteer
Lines up your ship (or airship!) to match a target **bearing**. Uses OCR to calculate angle difference and applies smart turns via keypresses.

> Especially useful when navigating through multiple waypoints or tight paths.

### 🔁 Auto Rejoin
Disconnected? No worries – AeroHelper detects disconnects and will:
- Rejoin the game
- Continue the previous job

### 📢 Webhook Alerts

Sends alerts through your webhook when:
- Disconnected
- Crashed
- Fuel depleted
- Collision or obstruction
- OCR issues
- ETC

Critical alerts get an `@everyone` ping. Optional debug alerts can be toggled in the app.

### 🔍 Feature Support Matrix

| Feature               | Boat 🚢 | Airship 🎈 | Aircraft ✈️ | Helicopter 🚁 |
|----------------------|--------|------------|-------------|---------------|
| AutoPilot            | ✅     | ❌         | ❌          | ❌            |
| AutoSteer            | ✅     | ✅         | ⚠️ (WIP)    | ❌            |
| Auto Rejoin          | ✅     | ✅         | ✅          | ✅            |
| Webhook Alerts       | ✅     | ✅         | ✅          | ✅            |
| Anti-AFK             | ✅     | ✅         | ✅          | ✅            |

---

## 🛠️ Installation Guide

### **Use the [compiled version](https://github.com/SSkipr/AeronauticaHelper/releases) for ease of use. Only supported for WindowsOS.**

### ✅ Supported OS (non compiled version):
- Windows
- MacOS (extra setup steps required)

### 1️⃣ Python Setup
Install **Python 3.7+**, ideally [Python 3.11](https://www.python.org/downloads/release/python-3110/). Avoid newer versions if issues arise.

#### MacOS Certificate Fix:
1. Go to `/Applications/Python 3.x/`
2. Run `Install Certificates.command`

### 2️⃣ Install Required Libraries

AeroHelper installs dependencies on first run. If it fails, run:

```bash
pip install pyautogui easyocr numpy requests pynput PyQt5
```

or

```bash
py -m pip install pyautogui easyocr numpy requests pynput PyQt5
```

### 3️⃣ Download and Setup
Grab the repo:  
[Download ZIP](https://github.com/SSkipr/AeronauticaHelper/archive/refs/heads/Standard.zip)

Your folder should look like:

```
/AeronauticaHelper
├── AeroHelperMain.py
├── data.txt
├── log_data.txt
├── LICENSE.md
└── README.md
```

### 4️⃣ Running the App
In terminal/cmd:

```bash
python AeroHelperMain.py
```

Or from your code editor (IDLE, VS Code, etc.)

---

## ⚙️ Configuration & Optimization Tips

- **Camera angle:** For better OCR, point your camera *underneath* the ship.
- **Graphics Quality:** Set **LOWEST** for better OCR clarity.
- **UI Scale:** 1.5–2x in Aeronautica settings.
- **Webhook:** Must be set up for alerts. Use a private Discord channel with notifications enabled.

---

## 🧠 Best Practices

- Use the default key binds and metrics: A, D, Z, Knots, and Nautical Miles.
- Adjust TURNING MULTIPLIER (~0.3–2.0) based on your ship’s agility.
- Use servers with higher multipliers, then rejoin a new server to start AFK.

---

## 🆕 Version 3 Highlights

- 🚤 Full AutoPilot
- 🎈 Airship AutoSteer support
- 🔁 AutoRejoin across all vehicle types
- 🎯 Precision Docking (AutoPilot)
- 🤫 Auto hide player list/chat
- 🧠 Smarter crash detection
- 🚫 Excludes "WINDY" and "KNOTS" from bearing calculations
- 🧮 Accepts negative distances (waypoints behind the ship)
- 📉 Sends error alerts if movement > 20 or < -20
- 🕵️ Anonymous Data Sharing

[Download Compiled v3](https://github.com/SSkipr/AeronauticaHelper/releases)

---

## 🙋 FAQ

**Can I use my PC while it runs?**  
> ❌ No – Roblox must be in focus.

**Why isn't it working?**  
> Try running as administrator. Still broken? DM me [@sskipr](https://discord.gg/3adphMca)

**Do I need a webhook?**  
> ✅ Yes, for error detection and alerts.

**Why is it so slow?**  
> To ensure stability. Will likely be customizable soon.

**Spammy errors?**  
> After 5 consecutive errors, the program exits safely.

---

## 📡 Anonymous Data Sharing (Optional)

If enabled, this will send:
- Your `data.txt`
- `log_data.txt`
- Webhook URL

Used only for **bug reports and troubleshooting.** You may be contacted (via your webhook) with fixes or follow-up questions. Logs are not stored long-term.

---

## 📎 Screenshots, Guide & References

💻 [AeroHelper Website](https://aeronautica-helper.vercel.app/)
📄 [AeroHelper AutoSteer Reference PDF](https://github.com/user-attachments/files/19727540/AeroHelper.Guide.pdf)
♾️ [AeroHelper AutoPilot PDF](https://github.com/user-attachments/files/19826524/AeroHelper.AutoPilot.pdf)

---

## ⭐ Support Us!

If you find this tool useful:
- Leave a ⭐ on the repo
- Follow the project
- Submit issues or ideas via [GitHub](https://github.com/SSkipr/AeronauticaHelper/issues) or [@sskipr](https://discord.gg/3adphMca)

Thanks for using AeroHelper!

---

## 📈 Roadmap

- Airship AutoPilot (~v3.ln(3√(2x + 5) + 7) - 1 = ln(3√11 + 7) - 1 😉)

- AI Plane Pathfinding (~v4)

---

# Version 3 has been cleared with Aeronautica Staff, specifically the Lead Developer, Rice

![v3Approved](https://github.com/user-attachments/assets/daa03f00-bca1-4754-92c8-c466379d97a6)
![v3ApprovedBottom](https://github.com/user-attachments/assets/0b77774c-5069-4697-9f9f-5939a46e22e7)
![v3ApprovedMidSS](https://github.com/user-attachments/assets/ad32da2a-8267-44c4-9d5d-b104d4a7e82e)



---

### Contribution

My appreciation for all of the contributors cannot be overstated. A special thanks to the Python libraries that made this project possible! Thank you all!


<img src="https://github.com/user-attachments/assets/1227944f-d48a-48c1-8176-15a6b6fb7856" width="25" height="25" alt="Person12" /> **Person 12**

<img src="https://github.com/user-attachments/assets/74d429c4-1262-40f8-9f0b-deefc4cfc620" width="25" height="25" alt="Person12" /> **She3pd0g**

PyAutoGUI

EasyOCR

Numpy

Requests

PyNput

PyQt5

MouseKey
