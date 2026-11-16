import zipfile
import shutil
from pathlib import Path

BASE_DIR = Path(r"C:\Users\Student\.gemini\antigravity\scratch\dropkit")
ZIP_DEST = BASE_DIR / "DropKit-Audit.zip"
ARTIFACT_DEST = Path(r"C:\Users\Student\.gemini\antigravity\brain\2b890657-4709-47a2-815a-12169035b9fe\DropKit-Audit.zip")

EXCLUDE_DIRS = {".git", "node_modules", "__pycache__"}
EXCLUDE_EXTS = {".pyc", ".pyo"}
EXCLUDE_FILES = {".env", "DropKit-Audit.zip", "dropkit.db"}

print(f"Creating archive at: {ZIP_DEST}")

with zipfile.ZipFile(ZIP_DEST, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in BASE_DIR.rglob("*"):
        if path.is_dir():
            continue
        
        # Check excluded directories
        parts = set(path.parts)
        if any(ex in parts for ex in EXCLUDE_DIRS):
            continue
            
        # Check excluded extensions
        if path.suffix.lower() in EXCLUDE_EXTS:
            continue
            
        # Check excluded filenames
        if path.name in EXCLUDE_FILES or path.name.startswith(".env"):
            if path.name != ".env.example":
                continue
                
        rel_path = path.relative_to(BASE_DIR)
        zf.write(path, arcname=str(rel_path))
        print(f"  + Added: {rel_path}")

print(f"Created {ZIP_DEST} ({ZIP_DEST.stat().st_size} bytes)")

# Copy to brain artifact directory
shutil.copy2(ZIP_DEST, ARTIFACT_DEST)
print(f"Copied to artifact directory: {ARTIFACT_DEST} ({ARTIFACT_DEST.stat().st_size} bytes)")
