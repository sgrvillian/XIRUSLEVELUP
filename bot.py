# -*- coding: utf-8 -*-
import os
import sys
import time
import zipfile
import tempfile
from pathlib import Path
from datetime import datetime

import requests

# ================= CONFIG =================
PROJECT_DIR = Path("/Account lvl")

# Set these environment variables in Termux before running.
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8944983211:AAFqePkbS-ecIs9P5pI7tJT_Y_h-T0g8J2Y").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7692008537").strip()

# ================= COLORS =================
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

def info(message):
    print(f"{YELLOW}🟡 INFO: {message}{RESET}", flush=True)

def success(message):
    print(f"{GREEN}🟢 SUCCESS: {message}{RESET}", flush=True)

def error(message):
    print(f"{RED}🔴 FAILED: {message}{RESET}", flush=True)

def safe_file(path):
    """Include normal source files; exclude secrets and account data."""
    name = path.name.lower()

    # Hidden files and directories are excluded.
    if name.startswith("."):
        return False

    blocked_names = {
        ".env", ".env.local", ".env.production",
         "credentials.json", "secrets.json",
        "cookies.txt", "authorized_keys",
    }

    if name in blocked_names:
        return False

    blocked_extensions = {
        ".pem", ".key", ".p12", ".pfx",
        ".sqlite", ".sqlite3", ".db", ".bak", ".tmp",
        ".zip",
    }

    if path.suffix.lower() in blocked_extensions:
        return False

    sensitive_words = (
        "passwd", "credential", "secret",
        "session", "private_key", "apikey", "api_key",
    )

    if any(word in name for word in sensitive_words):
        return False

    return path.is_file() and not path.is_symlink()

def create_backup():
    if not PROJECT_DIR.is_dir():
        raise FileNotFoundError(f"Project folder not found: {PROJECT_DIR}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = Path(tempfile.gettempdir()) / (
        f"level9_backup_{timestamp}.zip"
    )

    blocked_dirs = {
        "private"
    }

    count = 0
    total_bytes = 0

    info(f"Source folder: {PROJECT_DIR}")
    info("Scanning project files...")

    try:
        with zipfile.ZipFile(
            zip_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for root, dirs, files in os.walk(
                PROJECT_DIR, followlinks=False
            ):
                dirs[:] = [
                    d for d in dirs
                    if d.lower() not in blocked_dirs
                    and not d.startswith(".")
                ]

                for filename in files:
                    file_path = Path(root) / filename

                    try:
                        relative = file_path.relative_to(PROJECT_DIR)

                        if not safe_file(file_path):
                            info(f"Excluded: {relative}")
                            continue

                        archive.write(file_path, arcname=str(relative))
                        count += 1
                        total_bytes += file_path.stat().st_size
                        success(f"Added [{count}]: {relative}")

                    except (OSError, ValueError) as exc:
                        error(f"Skipped {file_path.name}: {exc}")

        if count == 0:
            raise RuntimeError(
                "No eligible files found. Check the project folder."
            )

        with zipfile.ZipFile(zip_path, "r") as archive:
            bad_file = archive.testzip()
            if bad_file:
                raise RuntimeError(f"ZIP verification failed: {bad_file}")

        size_mb = zip_path.stat().st_size / (1024 * 1024)
        success(f"ZIP verified: {count} files")
        info(f"Original file total: {total_bytes / (1024 * 1024):.2f} MB")
        info(f"Compressed ZIP size: {size_mb:.2f} MB")

        return zip_path

    except Exception:
        zip_path.unlink(missing_ok=True)
        raise

def send_to_telegram(zip_path):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError(
            "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID first."
        )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"

    info("Uploading ZIP to Telegram...")

    with open(zip_path, "rb") as file_handle:
        response = requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "caption": (
                    "Project backup\n"
                    f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                ),
            },
            files={
                "document": (
                    zip_path.name,
                    file_handle,
                    "application/zip",
                )
            },
            timeout=(20, 180),
        )

    response.raise_for_status()
    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram upload failed"))

    success("Telegram upload completed.")
    success(f"Message ID: {result['result']['message_id']}")

def main():
    zip_path = None

    print(f"{CYAN}==================================")
    print("       LEVEL9 PROJECT BACKUP")
    print("==================================" + RESET)

    started = time.time()

    try:
        zip_path = create_backup()
        send_to_telegram(zip_path)
        success(f"Finished in {time.time() - started:.2f} seconds")

    except KeyboardInterrupt:
        error("Cancelled by user.")

    except Exception as exc:
        error(str(exc))

    finally:
        if zip_path and zip_path.exists():
            zip_path.unlink(missing_ok=True)
            info("Temporary ZIP removed.")

if __name__ == "__main__":
    main()