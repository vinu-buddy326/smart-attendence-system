## Production (Windows + RTSP CCTV)

### 1) Install dependencies
```powershell
pip install -r requirements.txt
```

### 2) Configure `.env`
Required:
- `DB_TYPE=postgres`
- `DB_NAME`, `DB_USER`, `DB_PASS`, `DB_HOST`, `DB_PORT`
- `SECRET_KEY` (must be strong)

RTSP CCTV:
```env
CAMERA_SOURCE=rtsp
RTSP_URL=rtsp://username:password@camera_ip:554/stream
```

Optional Twilio SMS:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`

### 3) Run production server (Waitress)
From project root:
```powershell
waitress-serve --listen=0.0.0.0:5000 wsgi:application
```

Or use the helper script:
```powershell
powershell -ExecutionPolicy Bypass -File .\\scripts\\run_waitress.ps1
```

### 4) Health check
Open:
- `http://127.0.0.1:5000/health`

Expected JSON:
- `status: ok`
- `db: ok`
- `camera: running` (after you open `/dashboard` or `/video_feed`)

### 5) Run as a Windows service
Use NSSM instructions:
- `scripts/install_service_nssm.md`

### 6) Database backups (pg_dump)
Ensure PostgreSQL tools are installed and `pg_dump` is on PATH, then run:
```powershell
powershell -ExecutionPolicy Bypass -File .\\scripts\\backup_db.ps1
```

### 7) Soak test (2–4 hours)
- Start the app with Waitress (or the Windows service)
- Keep `/video_feed` open on one machine
- Walk 3–5 known students in front of the CCTV multiple times
- Verify in `/attendance`:
  - Attendance rows update within ~5 seconds
  - No duplicate spam for the same student within the cooldown window
- Simulate RTSP failure:
  - Temporarily unplug CCTV network / disable camera
  - Confirm app keeps running and recovers when RTSP comes back
- Check logs:
  - `logs/app.log` should contain errors but process should not crash

### 8) Performance tuning (if CPU is high)
- Reduce camera frame size (e.g., resize to 640x360 before detection)
- Reduce FPS processing loop (increase the sleep in `ai_engine/camera_stream.py`)
- Keep the dataset images clean (front-facing, good light)

