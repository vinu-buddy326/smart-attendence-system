## Install as a Windows Service (NSSM)

### Prereqs
- Install NSSM (Non-Sucking Service Manager)
- Ensure Python + your venv + dependencies are installed

### Service command
We run Waitress as the service process.

- **Service name**: `SmartAttendance`
- **Application**: `C:\Path\To\Python.exe` (inside your venv, recommended)
  - Example: `D:\smart_attendence_system\.venv\Scripts\python.exe`
- **App parameters**:
  - `-m waitress --listen=0.0.0.0:5000 wsgi:application`
- **Startup directory**:
  - `D:\smart_attendence_system`

### Example (PowerShell)
Replace `C:\tools\nssm\nssm.exe` and python path.

```powershell
$nssm = "C:\\tools\\nssm\\nssm.exe"
$py   = "D:\\smart_attendence_system\\.venv\\Scripts\\python.exe"
$cwd  = "D:\\smart_attendence_system"

& $nssm install SmartAttendance $py "-m waitress --listen=0.0.0.0:5000 wsgi:application"
& $nssm set SmartAttendance AppDirectory $cwd
& $nssm set SmartAttendance Start SERVICE_AUTO_START

# Optional logs
& $nssm set SmartAttendance AppStdout "$cwd\\logs\\service-stdout.log"
& $nssm set SmartAttendance AppStderr "$cwd\\logs\\service-stderr.log"

& $nssm start SmartAttendance
```

### Verify
- Open `http://127.0.0.1:5000/health`
- Reboot PC → service should auto-start

