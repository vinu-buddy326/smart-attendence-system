# Smart CCTV Attendance System: Working Model Guide

Follow these steps to transform the codebase into a fully functional production-level attendance system.

---

## 📸 1. Dataset Preparation (Crucial)
The AI identifies students by matching their live feed against images in these folders.

### `datasets/faces/`
*   **Format**: `roll_number.jpg` (e.g., `ROLL001.jpg`)
*   **Action**: Place a clear, front-facing portrait of the student here.
*   **AI Logic**: When the CCTV sees a face, it encodes it and compares it to these files.

### `datasets/bodies/`
*   **Format**: `roll_number.jpg`
*   **Action**: Place a full-body standing image here.
*   **AI Logic**: Used as a fallback if the face is obscured or too far from the camera.

---

## 🛠️ 2. Environment Setup

1.  **PostgreSQL**: Ensure PostgreSQL is running.
2.  **Database**: Create a database named `attendance_db`.
3.  **Config**: Open `.env` and enter your database password and Twilio credentials.

---

## 🚀 3. Step-by-Step Initialization

To fix the `ModuleNotFoundError` you saw earlier, you must run scripts as **modules** from the root folder.

### **Step A: Install Requirements**
```powershell
pip install -r requirements.txt
```

### **Step B: Initialize DB & Test Data**
Run this command to create tables and add an Admin account:
```powershell
$env:PYTHONPATH="."; python -m database.test_data
```
*Wait for: "Database Initialized" and "Test data added."*

### **Step C: Launch the Portal**
```powershell
python main.py
```

---

## 🧪 4. Testing the Production Flow

1.  **Login**: Open `http://127.0.0.1:5000` in your browser.
    *   **Email**: `admin@example.com`
    *   **Password**: `admin123`
2.  **Force-Start Detection**: The attendance detection is scheduled for specific times. To test it **immediately**, open a new terminal and run:
    ```powershell
    $env:PYTHONPATH="."; python -m attendance.scheduler
    ```
    *   **Result**: Your webcam will open. Face the camera. If you have your photo in `datasets/faces/ROLL001.jpg`, you will see your name appear and an SMS will be triggered!

---

## 💡 Troubleshooting
*   **ModuleNotFoundError**: Always use the `$env:PYTHONPATH=".";` prefix or run from the root using `-m`.
*   **Camera In Use**: Close other apps (Teams, Zoom) before running the detection module.
*   **YOLO Download**: The first run might take 30 seconds to download the vision model automatially.
