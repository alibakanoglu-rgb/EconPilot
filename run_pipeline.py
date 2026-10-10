from pathlib import Path
import subprocess
import sys


PROJECT_DIR = Path(__file__).resolve().parent
SCRIPTS = [
    "fetch_evds.py",
    "fetch_tufe_2025base.py",
    "fetch_usdtry.py",
    "analyze_macro.py",
]
for script_name in SCRIPTS:
    script_path = PROJECT_DIR / script_name
    print(f"\n--- {script_name} çalıştırılıyor ---")
    subprocess.run(
        [sys.executable, str(script_path)],
        cwd=PROJECT_DIR,
        check=True,
    )

print("\nEconPilot veri hattı tamamlandı.")
