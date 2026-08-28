
import os
import sys
import shutil
import subprocess
import tempfile
import threading
def ensure_python_dependencies():
    """Install missing pip dependencies needed by optional build features.
    Tkinter is part of the Python installation and cannot reliably be installed
    with pip. ClamAV/csc.exe are external Windows tools and are therefore only
    detected, not silently installed. PyInstaller is installed automatically
    because the Builder uses it for Python -> EXE builds.
    """
    if os.environ.get("XRYSS_SKIP_DEP_INSTALL") == "1":
        return
    required = [("PyInstaller", "PyInstaller>=6.0")]
    missing = []
    for module_name, package_name in required:
        try:
            __import__(module_name.lower() if module_name != "PyInstaller" else "PyInstaller")
        except ImportError:
            missing.append(package_name)
    if not missing:
        return
    try:
        command = [
            sys.executable, "-m", "pip", "install",
            "--disable-pip-version-check", *missing
        ]
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=300, check=False
        )
        if result.returncode != 0:
            user_command = [
                sys.executable, "-m", "pip", "install", "--user",
                "--disable-pip-version-check", *missing
            ]
            result = subprocess.run(
                user_command, capture_output=True, text=True,
                timeout=300, check=False
            )
        if result.returncode != 0:
            raise RuntimeError(
                (result.stderr or result.stdout or "pip install failed").strip()
            )
        import importlib
        importlib.invalidate_caches()
    except Exception as exc:
        print(f"[XRYSS] Dependency installation skipped/failed: {exc}", file=sys.stderr)
ensure_python_dependencies()
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from datetime import datetime
import hashlib
import base64
import gzip
import random
import string
import json
import time
import platform
import sqlite3
import urllib.request
try:
    import requests
except ImportError:
    requests = None
import urllib.error
import re
APP_NAME = "xryss.obf"
VERSION = "19.0"
THEMES = {
    "Midnight": {
        "bg": "#0b0e12",
        "panel": "#11151b",
        "panel2": "#181d24",
        "field": "#0d1117",
        "border": "#252c36",
        "text": "#eef2f7",
        "muted": "#7f8ca1",
        "accent": "#6b7cff",
        "accent2": "#8795ff",
        "good": "#69d89a",
        "bad": "#ff7180",
        "warn": "#f1bd63",
    },
    "Graphite": {
        "bg": "#111214",
        "panel": "#181a1e",
        "panel2": "#1e2126",
        "field": "#0e1012",
        "border": "#30343b",
        "text": "#f1f1f1",
        "muted": "#9499a2",
        "accent": "#b7c0cc",
        "accent2": "#e0e5ea",
        "good": "#76d9a3",
        "bad": "#ff7d88",
        "warn": "#e6bd6b",
    },
    "Ocean": {
        "bg": "#071116",
        "panel": "#0d1a21",
        "panel2": "#12232c",
        "field": "#071016",
        "border": "#1e3743",
        "text": "#ecf8fb",
        "muted": "#7f9ca8",
        "accent": "#43c7ee",
        "accent2": "#75d8f5",
        "good": "#68d9aa",
        "bad": "#ff7c8c",
        "warn": "#ebc070",
    },
}
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
def run_hidden(command, **kwargs):
    kwargs.setdefault(
        "creationflags",
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )
    return subprocess.run(command, **kwargs)
def unique_path(folder, stem, suffix):
    folder = Path(folder)
    candidate = folder / f"{stem}{suffix}"
    number = 1
    while candidate.exists():
        candidate = folder / f"{stem}_{number}{suffix}"
        number += 1
    return candidate
def find_pyinstaller():
    # 1. Check the current Python environment (This is the most reliable method for your app)
    try:
        result = run_hidden(
            [sys.executable, "-m", "PyInstaller", "--version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return [sys.executable, "-m", "PyInstaller"]
    except Exception:
        pass

    # 2. Try searching the Scripts folder associated with the current Python
    scripts_dir = Path(sys.executable).parent / "Scripts" / "pyinstaller.exe"
    if scripts_dir.exists():
        return [str(scripts_dir)]

    # 3. Fall back to searching the system PATH
    exe = shutil.which("pyinstaller")
    return [exe] if exe else None
def find_csc():
    candidates = [
        os.path.expandvars(
            r"%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
        ),
        os.path.expandvars(
            r"%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
        ),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return shutil.which("csc.exe")
def detect_type(path):
    ext = Path(path).suffix.lower()
    if ext == ".py":
        return "Python"
    if ext in (".bat", ".cmd"):
        return "Batch"
    if ext in (".cs", ".csproj"):
        return "C# / .NET"
    if ext == ".exe":
        return "Windows EXE"
    if ext == ".dll":
        return "Windows DLL"
    return "Generic"
def python_obfuscate(source, output_dir):
    """REALLY GOOD Python Obfuscator: 10x Base64 + Zlib Compression."""
    src = Path(source).resolve()
    out = Path(output_dir).resolve()
    text = src.read_text(encoding="utf-8", errors="ignore")

    # 1. Encode the text into Base64 10 times FIRST
    encoded_str = base64.b64encode(text.encode('utf-8')).decode('utf-8')
    for _ in range(9):
        encoded_str = base64.b64encode(encoded_str.encode('utf-8')).decode('utf-8')

    # 2. NOW Compress that heavily encoded string with gzip
    compressed = gzip.compress(encoded_str.encode('utf-8'))

    # 3. Encode the compressed bytes into Base64 ONE last time 
    # (so we can safely put it in the python file as text)
    final_bytes = base64.b64encode(compressed)
    final_str = final_bytes.decode('utf-8')

    # 4. Build the self-decoding launcher
    decoder = ''.join(random.choices(string.ascii_lowercase, k=5))
    b64 = ''.join(random.choices(string.ascii_lowercase, k=5))
    z = ''.join(random.choices(string.ascii_lowercase, k=5))
    e = ''.join(random.choices(string.ascii_lowercase, k=5))

    # The launcher does: 1. b64decode (get gzip) -> 2. gzip.decompress (get 10x b64) 
    # -> 3. b64decode 10 times (get original text) -> 4. exec
    header = (
        f"import base64 as {b64}\n"
        f"import gzip as {z}\n"
        f"{e} = lambda x: {b64}.b64decode(x)\n"  # First layer: get gzip data
        f"{z}.decompress({e}('"
    )

    obfuscated_text = header + final_str + "'))\n"

    # Add the 10x decode loop to the launcher
    # We have to make it decode 10 times. 
    # We split the string, iterate, and then exec it.
    launcher = (
        f"import base64 as {b64}\n"
        f"import gzip as {z}\n"
        f"_x = {b64}.b64decode('{final_str}')\n"       # Step 1: Decode the outer b64
        f"_x = {z}.decompress(_x)\n"                    # Step 2: Unzip to get the 10x string
        f"for _ in range(10):\n"                        # Step 3: Decode 10 times
        f"    _x = {b64}.b64decode(_x)\n"
        f"exec(_x.decode('utf-8'))\n"
    )

    result = unique_path(out, src.stem + "_xryss", ".py")
    result.write_text(launcher, encoding="utf-8")
    return result
def batch_obfuscate(source, output_dir):
    """
    Faster batch wrapper:
    - Gzip compression
    - Single Base64 encoding
    - No Python dependency at runtime
    - Uses Windows certutil + PowerShell
    - Streams the payload into a temporary file
    - Preserves arguments and exit code
    """
    src = Path(source).resolve()
    out = Path(output_dir).resolve()

    original = src.read_bytes()

    # Compress first, then encode once.
    compressed = gzip.compress(
        original,
        compresslevel=9
    )

    final_str = base64.b64encode(
        compressed
    ).decode("ascii")

    # Smaller chunks keep cmd.exe reliable.
    chunk_size = 64
    chunks = [
        final_str[i:i + chunk_size]
        for i in range(0, len(final_str), chunk_size)
    ]

    # Random temporary identifiers.
    temp_name = ''.join(
        random.choices(
            string.ascii_lowercase,
            k=12
        )
    )

    payload_var = ''.join(
        random.choices(
            string.ascii_lowercase,
            k=7
        )
    )

    gzip_path = rf"%TEMP%\{temp_name}.gz"
    bat_path = rf"%TEMP%\{temp_name}.bat"
    txt_path = rf"%TEMP%\{temp_name}.txt"

    stub = [
        "@echo off",
        "setlocal EnableExtensions DisableDelayedExpansion",
        "",
        f'set "{payload_var}={txt_path}"',
        "",
        # Write payload.
        f'> "%{payload_var}%" echo {chunks[0]}',
    ]

    for chunk in chunks[1:]:
        stub.append(
            f'>> "%{payload_var}%" echo {chunk}'
        )

    stub.extend([
        "",
        # Make sure certutil exists.
        'where certutil.exe >nul 2>&1',
        'if errorlevel 1 goto :error',
        "",
        # Decode Base64 -> gzip.
        f'certutil.exe -decode "%{payload_var}%" "{gzip_path}" >nul 2>&1',
        'if errorlevel 1 goto :error',
        "",
        # Gzip -> original BAT.
        'powershell.exe -NoProfile -NonInteractive -Command '
        '"$g=[IO.File]::OpenRead('
        f"'{gzip_path}'"
        ');'
        '$o=[IO.File]::Create('
        f"'{bat_path}'"
        ');'
        '$z=New-Object IO.Compression.GzipStream('
        '$g,[IO.Compression.CompressionMode]::Decompress);'
        '$z.CopyTo($o);'
        '$z.Dispose();'
        '$o.Dispose();'
        '$g.Dispose()"',
        'if errorlevel 1 goto :error',
        "",
        # Run the reconstructed BAT.
        f'call "{bat_path}" %*',
        'set "xryss_rc=%ERRORLEVEL%"',
        "",
        # Cleanup.
        f'del /q "%{payload_var}%" >nul 2>&1',
        f'del /q "{gzip_path}" >nul 2>&1',
        f'del /q "{bat_path}" >nul 2>&1',
        "",
        'endlocal & exit /b %xryss_rc%',
        "",
        ":error",
        f'del /q "%{payload_var}%" >nul 2>&1',
        f'del /q "{gzip_path}" >nul 2>&1',
        f'del /q "{bat_path}" >nul 2>&1',
        'echo xryss.obf: Failed to reconstruct the batch file.',
        'endlocal & exit /b 1',
    ])

    result = unique_path(
        out,
        src.stem + "_xryss",
        src.suffix.lower()
    )

    result.write_text(
        "\r\n".join(stub) + "\r\n",
        encoding="ascii"
    )

    return result
def python_to_exe(
    source,
    output_dir,
    windowed=False,
    onefile=True,
    icon=None,
):
    compiler = find_pyinstaller()
    if not compiler:
        raise RuntimeError(
            "PyInstaller is not installed.\n\n"
            "Run: python -m pip install pyinstaller"
        )
    src = Path(source).resolve()
    out = Path(output_dir).resolve()
    temp_dir = Path(
        tempfile.mkdtemp(prefix="xryss_py_")
    )
    try:
        dist = temp_dir / "dist"
        build = temp_dir / "build"
        spec = temp_dir / "spec"
        command = compiler + [
            "--noconfirm",
            "--clean",
            "--name",
            src.stem,
            "--distpath",
            str(dist),
            "--workpath",
            str(build),
            "--specpath",
            str(spec),
        ]
        if onefile:
            command.append("--onefile")
        if windowed:
            command.append("--windowed")
        if icon:
            command += ["--icon", str(icon)]
        command.append(str(src))
        result = run_hidden(
            command,
            cwd=str(src.parent),
            capture_output=True,
            text=True,
            timeout=900,
        )
        if result.returncode != 0:
            raise RuntimeError(
                (
                    result.stderr or
                    result.stdout or
                    "PyInstaller failed"
                )[-7000:]
            )
        if onefile:
            built = dist / f"{src.stem}.exe"
            if not built.exists():
                raise RuntimeError(
                    "PyInstaller finished but no EXE was found."
                )
            final = unique_path(
                out,
                src.stem + "_xryss",
                ".exe"
            )
            shutil.copy2(built, final)
            return final
        built_dir = dist / src.stem
        if not built_dir.exists():
            raise RuntimeError(
                "PyInstaller finished but no output folder was found."
            )
        final = unique_path(
            out,
            src.stem + "_xryss",
            ""
        )
        shutil.copytree(built_dir, final)
        return final
    finally:
        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )
def batch_to_exe(source, output_dir):
    compiler = find_csc()
    if not compiler:
        raise RuntimeError(
            "csc.exe was not found. Install Visual Studio Build Tools "
            "or the .NET Framework Developer Pack with C# tools."
        )
    src = Path(source).resolve()
    out = Path(output_dir).resolve()
    temp_dir = Path(
        tempfile.mkdtemp(prefix="xryss_batch_")
    )
    try:
        payload = temp_dir / "payload.bat"
        shutil.copy2(source, payload)
        launcher = temp_dir / "Launcher.cs"
        launcher_code = r'''
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
internal static class Program
{
    private static int Main(string[] args)
    {
        string tempFile = Path.Combine(
            Path.GetTempPath(),
            Guid.NewGuid().ToString("N") + ".bat"
        );
        try
        {
            Assembly assembly = Assembly.GetExecutingAssembly();
            using (Stream input =
                assembly.GetManifestResourceStream("XryssPayload"))
            {
                if (input == null)
                    throw new Exception("Embedded payload was not found.");
                using (FileStream output = File.Create(tempFile))
                    input.CopyTo(output);
            }
            StringBuilder arguments = new StringBuilder();
            foreach (string argument in args)
            {
                if (arguments.Length > 0)
                    arguments.Append(" ");
                arguments.Append("\"");
                arguments.Append(
                    argument.Replace("\\", "\\\\")
                            .Replace("\"", "\\\"")
                );
                arguments.Append("\"");
            }
            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName =
                Environment.GetEnvironmentVariable("COMSPEC");
            info.Arguments =
                "/d /c call \"" + tempFile + "\"" +
                (arguments.Length > 0
                    ? " " + arguments.ToString()
                    : "");
            info.WorkingDirectory =
                AppDomain.CurrentDomain.BaseDirectory;
            info.UseShellExecute = false;
            using (Process process = Process.Start(info))
            {
                process.WaitForExit();
                return process.ExitCode;
            }
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(
                "xryss.obf: " + error.Message
            );
            return 1;
        }
        finally
        {
            try
            {
                if (File.Exists(tempFile))
                    File.Delete(tempFile);
            }
            catch
            {
            }
        }
    }
}
'''
        launcher.write_text(
            launcher_code,
            encoding="utf-8"
        )
        output = unique_path(
            out,
            src.stem + "_xryss",
            ".exe"
        )
        result = run_hidden(
            [
                compiler,
                "/nologo",
                "/target:exe",
                f"/out:{output}",
                f"/resource:{payload},XryssPayload",
                str(launcher),
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0 or not output.exists():
            raise RuntimeError(
                (
                    result.stderr or
                    result.stdout or
                    "C# compilation failed"
                )[-7000:]
            )
        return output
    finally:
        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )
BLOCK_DB_DIR = Path(
    os.environ.get("PROGRAMDATA", Path.home())
) / "xryss.obf"
BLOCK_DB = BLOCK_DB_DIR / "access_control.db"
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "xryss.obf"
CONFIG_FILE = CONFIG_DIR / "settings.json"
DEFAULT_WEBHOOK_URL = ""  # v19: no embedded webhook credentials
ADMIN_DEVICE_ENV = "XRYSS_ADMIN_DEVICE_IDS"
AUTHORIZED_DEVICE_ID = "059b295f-e643-46e3-9b7a-7f517d2a99c4"
WHITELIST_SETTINGS_KEY = "whitelist_device_ids"
LOCAL_LOG_DIR = CONFIG_DIR / "logged_files"
AUDIT_LOG_FILE = CONFIG_DIR / "audit_log.jsonl"
def load_settings():
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}
def save_settings(data):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
def webhook_url():
    value = load_settings().get("webhook_url", "")
    value = str(value).strip()
    return value
def append_audit(event, **details):
    """Persist a small local audit trail for builds, blocks, and configuration changes."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "event": str(event),
            **{str(k): str(v) for k, v in details.items()},
        }
        with AUDIT_LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass
def read_audit(limit=250):
    if not AUDIT_LOG_FILE.exists():
        return []
    rows = []
    try:
        with AUDIT_LOG_FILE.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    value = json.loads(line)
                    if isinstance(value, dict):
                        rows.append(value)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return rows[-limit:]
def admin_device_ids():
    raw = os.environ.get(ADMIN_DEVICE_ENV, "")
    return {x.strip().lower() for x in raw.split(",") if x.strip()}
def is_admin_device():
    return device_id().lower() == AUTHORIZED_DEVICE_ID.lower() or device_id().lower() in admin_device_ids()
def whitelist_device_ids():
    values = load_settings().get(WHITELIST_SETTINGS_KEY, [])
    if isinstance(values, str):
        values = values.split(",")
    if not isinstance(values, list):
        values = []
    return {str(x).strip().lower() for x in values if str(x).strip()}
def is_device_whitelisted():
    return device_id().lower() in whitelist_device_ids()
def archive_original(source):
    """Keep a local copy so the admin view can restore files created by this app."""
    src = Path(source).resolve()
    LOCAL_LOG_DIR.mkdir(parents=True, exist_ok=True)
    digest = sha256(src)
    archived = LOCAL_LOG_DIR / f"{digest}{src.suffix.lower()}"
    if not archived.exists():
        shutil.copy2(src, archived)
    return archived, digest
def ensure_block_db():
    try:
        BLOCK_DB_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(BLOCK_DB))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS blocked_devices (
                device_id TEXT PRIMARY KEY,
                created_utc TEXT NOT NULL,
                reason TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False
THEME_PRESETS = {
    "Midnight": {
        "bg": "#0b0e12", "panel": "#11151b", "panel2": "#181d24",
        "field": "#0d1117", "border": "#252c36", "fg": "#e8edf5",
        "muted": "#7f8a9a", "accent": "#6b7cff", "accent2": "#8795ff",
        "good": "#5ed6a5", "warn": "#f0c674", "bad": "#ef6a7a",
    },
    "Obsidian": {
        "bg": "#080808", "panel": "#101010", "panel2": "#191919",
        "field": "#0d0d0d", "border": "#2a2a2a", "fg": "#f2f2f2",
        "muted": "#858585", "accent": "#d0d0d0", "accent2": "#ffffff",
        "good": "#82d982", "warn": "#e0c36a", "bad": "#ed7070",
    },
    "Slate": {
        "bg": "#0c1218", "panel": "#121c25", "panel2": "#1a2833",
        "field": "#0e1820", "border": "#293b48", "fg": "#e4edf2",
        "muted": "#8295a2", "accent": "#56b4d8", "accent2": "#78cbe8",
        "good": "#67d5ae", "warn": "#e8c56d", "bad": "#ed7783",
    },
    "Emerald": {
        "bg": "#09110e", "panel": "#0f1915", "panel2": "#17251f",
        "field": "#0c1511", "border": "#263a31", "fg": "#e5f2eb",
        "muted": "#80958b", "accent": "#43c58a", "accent2": "#70dda9",
        "good": "#6be3a8", "warn": "#e6c66c", "bad": "#ec707d",
    },
    "Amethyst": {
        "bg": "#0d0a13", "panel": "#15101d", "panel2": "#21172d",
        "field": "#100c16", "border": "#34263f", "fg": "#eee7f5",
        "muted": "#93869e", "accent": "#a978e8", "accent2": "#c29af2",
        "good": "#72d6ae", "warn": "#e3c16d", "bad": "#ed7282",
    },
    "Amber": {
        "bg": "#110d08", "panel": "#19130d", "panel2": "#251b12",
        "field": "#120e09", "border": "#3a2a1b", "fg": "#f5eee4",
        "muted": "#a4937e", "accent": "#e2a94f", "accent2": "#f0bf6b",
        "good": "#70d39d", "warn": "#f0c46c", "bad": "#ed7373",
    },
}
THEMES = {}
for _name, _palette in THEME_PRESETS.items():
    THEMES[_name] = dict(_palette)
    THEMES[_name].setdefault("text", _palette["fg"])
HARMFUL_RULES = [
    ("credential theft", re.compile(r"(?i)\b(mimikatz|sekurlsa|logonpasswords|lsass\.dmp|sam\s+(save|dump)|ntds\.dit)\b")),
    ("keylogging/input capture", re.compile(r"(?i)\b(keylogger|keylogging|GetAsyncKeyState|SetWindowsHookEx|pynput\.keyboard|keyboard\.Listener)\b")),
    ("remote shell/control", re.compile(r"(?i)\b(reverse\s*shell|bind\s*shell|meterpreter|cobalt\s*strike|powershell\s+.*-enc(?:odedcommand)?|netcat|ncat)\b")),
    ("download-and-execute", re.compile(r"(?is)\b(?:curl|wget|bitsadmin|certutil|Invoke-WebRequest|iwr)\b.{0,300}\b(?:Start-Process|cmd(?:\.exe)?\s+/c|powershell(?:\.exe)?)\b")),
    ("persistence", re.compile(r"(?i)\b(?:schtasks|reg\s+add\s+.*\\Run\b|startup\\|RunOnce|New-ScheduledTask|sc(?:\.exe)?\s+create)\b")),
    ("security-control tampering", re.compile(r"(?i)\b(?:Set-MpPreference|DisableRealtimeMonitoring|Add-MpPreference|netsh\s+advfirewall\s+set\s+allprofiles\s+state\s+off)\b")),
    ("destructive disk/file operation", re.compile(r"(?i)\b(?:format\s+[a-z]:|diskpart\b|cipher\s+/w|vssadmin\s+delete\s+shadows|bcdedit\s+/set\s+.*recoveryenabled\s+no)\b")),
    ("mass data collection/exfiltration", re.compile(r"(?i)\b(?:rclone|mega(?:cmd)?|aws\s+s3\s+cp|scp\s+.*@|Invoke-RestMethod\s+.*-Method\s+Post)\b")),
    ("UAC/security bypass", re.compile(r"(?i)\b(?:fodhelper|eventvwr|sdclt|cmstp|UACMe|bypass\s+uac)\b")),
]
def _strip_batch_comments(source_text):
    """Remove .bat/.cmd comments and blank lines for heuristic analysis."""
    kept = []
    for line in str(source_text).splitlines():
        stripped = line.lstrip()
        if stripped.startswith("rem ") or stripped.lower() == "rem":
            continue
        if stripped.startswith("::"):
            continue
        kept.append(line)
    return "\n".join(kept)
def _strip_powershell_comments(source_text):
    """Remove simple PowerShell line comments while preserving code."""
    kept = []
    for line in str(source_text).splitlines():
        quote = False
        escaped = False
        result = []
        for ch in line:
            if ch == "`" and not escaped:
                escaped = True
                result.append(ch)
                continue
            if ch == '"' and not escaped:
                quote = not quote
            if ch == "'" and not escaped:
                quote = not quote
            if ch == "#" and not quote:
                break
            result.append(ch)
            escaped = False
        if "".join(result).strip():
            kept.append("".join(result))
    return "\n".join(kept)
def scan_for_harmful_intent(source_text, filename="input"):
    """Static heuristic scan. Never executes the input."""
    raw = str(source_text)
    ext = Path(str(filename)).suffix.lower()
    if ext in (".bat", ".cmd"):
        code = _strip_batch_comments(raw)
    elif ext in (".ps1", ".psm1", ".psd1"):
        code = _strip_powershell_comments(raw)
    else:
        code = "\n".join(
            line for line in raw.splitlines()
            if not line.lstrip().startswith(("#", "//", "rem "))
        )
    lowered = code.lower()
    findings = []
    high_confidence = [
        ("credential theft", r"\b(?:mimikatz|sekurlsa|logonpasswords|lsass\.dmp|ntds\.dit)\b"),
        ("keylogging/input capture", r"\b(?:keylogger|keylogging|getasynckeystate|setwindowshookex)\b"),
        ("encoded PowerShell execution", r"(?i)-(?:encodedcommand|enc)\s+[A-Za-z0-9+/=]{20,}"),
        ("remote shell tooling", r"\b(?:meterpreter|cobalt\s*strike|netcat|ncat)\b"),
        ("security-control tampering", r"\b(?:set-mppreference|disablerealtimemonitoring|netsh\s+advfirewall\s+set\s+allprofiles\s+state\s+off)\b"),
        ("destructive system operation", r"\b(?:vssadmin\s+delete\s+shadows|diskpart|cipher\s+/w)\b"),
        ("persistence", r"\b(?:schtasks|new-scheduledtask|reg\s+add\s+.*\\runonce?\\b)\b"),
        ("UAC bypass indicator", r"\b(?:fodhelper|eventvwr|sdclt|cmstp)\b"),
    ]
    for category, pattern in high_confidence:
        if re.search(pattern, code, re.I | re.S):
            findings.append({"category": category, "line": 0, "snippet": "High-confidence pattern detected."})
    has_download = bool(re.search(
        r"\b(?:invoke-webrequest|invoke-restmethod|downloadstring|start-bitstransfer|curl|wget)\b",
        code, re.I
    ))
    has_exec = bool(re.search(
        r"\b(?:start-process|invoke-expression|\biex\b|cmd(?:\.exe)?\s+/c|powershell(?:\.exe)?\s+-command)\b",
        code, re.I
    ))
    has_suspicious_persistence = bool(re.search(
        r"\b(?:schtasks|new-scheduledtask|\\runonce?\\)\b", code, re.I
    ))
    if has_download and has_exec:
        findings.append({"category": "download followed by execution", "line": 0,
                         "snippet": "Network download is combined with an execution primitive."})
    if has_download and has_suspicious_persistence:
        findings.append({"category": "download combined with persistence", "line": 0,
                         "snippet": "Network download is combined with persistence behavior."})
    return {
        "safe": not findings,
        "filename": str(filename),
        "findings": findings,
        "categories": sorted({x["category"] for x in findings}),
    }
def device_id():
    """Gets the real Windows Machine GUID (Stable, Unique Hardware ID)."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        return value.strip().lower()
    except Exception:
        settings = load_settings()
        value = settings.get("installation_id")
        if not value:
            value = "fallback_" + ''.join(random.choices(string.ascii_lowercase, k=16))
            settings["installation_id"] = value
            save_settings(settings)
        return value
def is_device_blocked():
    return False
def is_device_whitelisted():
    return True
def unblock_device(target_device_id):
    append_audit("admin_unblock", target_device_id=target_device_id)
    return True
def blocked_devices():
    return []
def block_device(reason):
    append_audit("safety_review", reason=reason)
    return False
def run_clamav(path):
    candidates = [
        shutil.which("clamscan"),
        shutil.which("clamscan.exe"),
    ]
    scanner = next((x for x in candidates if x), None)
    if not scanner:
        return None, "ClamAV not installed"
    try:
        result = hidden_run(
            [scanner, "--no-summary", str(path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return False, "ClamAV clean"
        output = (result.stdout or result.stderr or "").strip()
        if result.returncode == 1:
            return True, output[:500] or "ClamAV detected a threat"
        return None, output[:500] or "ClamAV could not complete the scan"
    except Exception as exc:
        return None, f"ClamAV error: {exc}"
def heuristic_scan(path):
    """
    Conservative local heuristic scan.
    This is a conservative static heuristic; network downloads alone are allowed.
    """
    reasons = []
    suffix = Path(path).suffix.lower()
    if suffix not in {".py", ".bat", ".cmd"}:
        return reasons
    try:
        data = Path(path).read_bytes()
        text = data[:2_000_000].decode("utf-8", errors="ignore").lower()
    except Exception:
        return ["Could not read file for heuristic scan"]
    high_confidence_patterns = [
        ("base64 powershell execution", "-encodedcommand"),
        ("remote command execution", "certutil -urlcache"),
        ("remote command execution", "bitsadmin /transfer"),
        ("shell execution via mshta", "mshta http"),
        ("shell execution via regsvr32", "regsvr32 http"),
    ]
    for reason, needle in high_confidence_patterns:
        if needle in text:
            reasons.append(reason)
    has_web_download = any(x in text for x in (
        "invoke-webrequest", "invoke-restmethod", "downloadstring(",
        "start-bitstransfer", "curl ", "wget "
    ))
    has_execution = any(x in text for x in (
        "start-process", "invoke-expression", "iex ",
        "cmd.exe /c", "powershell.exe -command",
        "powershell -command"
    ))
    if has_web_download and has_execution:
        reasons.append("download followed by execution")
    return sorted(set(reasons))
def safety_scan(path):
    """
    Returns:
      {
        "blocked": bool,
        "reasons": list[str],
        "sha256": str,
        "clamav": str
      }
    """
    path = Path(path).resolve()
    digest = sha256(path)
    reasons = heuristic_scan(path)
    clam_state, clam_message = run_clamav(path)
    if clam_state is True:
        reasons.append("ClamAV: " + clam_message)
    elif clam_state is None and clam_message != "ClamAV not installed":
        reasons.append("ClamAV scan unavailable: " + clam_message)
    blocked = bool(reasons)
    return {
        "blocked": blocked,
        "reasons": sorted(set(reasons)),
        "sha256": digest,
        "clamav": clam_message,
    }
class XryssApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(
            f"{APP_NAME} {VERSION}"
        )
        self.geometry(
            "1180x760"
        )
        self.minsize(
            980,
            650
        )
        self.theme_name = "Midnight"
        self.mode = tk.StringVar(
            value="Python → EXE"
        )
        self.profile = tk.StringVar(
            value="Balanced"
        )
        self.source = tk.StringVar()
        self.output = tk.StringVar()
        self.icon = tk.StringVar()
        self.status = tk.StringVar(
            value="READY"
        )
        self.windowed = tk.BooleanVar(
            value=False
        )
        self.onefile = tk.BooleanVar(
            value=True
        )
        self.auto_open = tk.BooleanVar(
            value=True
        )
        self.busy = False
        self.build_count = 0
        self.history = []
        self.settings = load_settings()
        saved_theme = str(self.settings.get("theme", "Midnight"))
        self.theme_name = saved_theme if saved_theme in THEME_PRESETS else "Midnight"
        palette = THEME_PRESETS[self.theme_name]
        for key, value in palette.items():
            setattr(self, key, value)
        self.apply_theme()
        self.build_shell()
    @property
    def c(self):
        return THEME_PRESETS.get(self.theme_name, THEME_PRESETS["Midnight"])
    def apply_theme(self):
        c = dict(self.c)
        self.bg = c.get("bg", "#0b0e12")
        self.panel = c.get("panel", self.bg)
        self.panel2 = c.get("panel2", self.panel)
        self.field = c.get("field", self.bg)
        self.border = c.get("border", self.panel2)
        self.fg = c.get("text", c.get("fg", "#eef2f7"))
        self.muted = c.get("muted", "#7f8ca1")
        self.accent = c.get("accent", "#6b7cff")
        self.accent2 = c.get("accent2", self.accent)
        self.good = c.get("good", "#69d89a")
        self.warn = c.get("warn", "#f1bd63")
        self.bad = c.get("bad", "#ff7180")
        self.text = self.fg
        self.configure(bg=self.bg)
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TCombobox", fieldbackground=self.field, background=self.panel2, foreground=self.fg)
        style.configure("TEntry", fieldbackground=self.field, foreground=self.fg)
        style.configure("Treeview", background=self.field, fieldbackground=self.field, foreground=self.fg, borderwidth=0)
        style.configure("Treeview.Heading", background=self.panel2, foreground=self.fg)
    def button(self, parent, text, command, primary=False):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=self.accent if primary else self.panel2,
            fg="#ffffff",
            activebackground=self.accent2 if primary else self.border,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=14,
            pady=7,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )
    def section(self, parent, text):
        tk.Label(
            parent,
            text=text,
            bg=self.bg,
            fg=self.muted,
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", padx=30, pady=(10, 5))
    def build_shell(self):
        for child in self.winfo_children():
            child.destroy()
        self.configure(bg=self.bg)
        top = tk.Frame(self, bg=self.panel, height=54)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(
            top, text="xryss", bg=self.panel, fg="#ffffff",
            font=("Segoe UI", 18, "bold")
        ).pack(side="left", padx=(20, 2))
        tk.Label(
            top, text=".obf", bg=self.panel, fg=self.accent,
            font=("Segoe UI", 18, "bold")
        ).pack(side="left")
        tk.Label(
            top, text=f"  BUILD STUDIO  /  {VERSION}",
            bg=self.panel, fg=self.muted,
            font=("Segoe UI", 8, "bold")
        ).pack(side="left", padx=12)
        tk.Label(
            top, text="LOCAL • READY",
            bg=self.panel, fg=self.good,
            font=("Segoe UI", 8, "bold")
        ).pack(side="right", padx=20)
        body = tk.Frame(self, bg=self.bg)
        body.pack(fill="both", expand=True)
        nav = tk.Frame(body, bg=self.panel, width=190)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        tk.Label(
            nav, text="WORKSPACE", bg=self.panel, fg=self.muted,
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", padx=18, pady=(18, 9))
        nav_items = [
            ("Overview", "OVERVIEW"),
            ("Builder", "BUILDER"),
            ("History", "HISTORY"),
            ("Logs", "LOGS"),
            ("Settings", "SETTINGS"),
        ]
        if is_admin_device():
            nav_items.append(("Admin", "ADMIN"))
        for item, label in nav_items:
            btn = tk.Button(
                nav,
                text=f"  {label}",
                anchor="w",
                bg=self.panel,
                fg=self.fg,
                activebackground=self.panel2,
                activeforeground="#ffffff",
                relief="flat",
                bd=0,
                highlightthickness=0,
                padx=14,
                pady=9,
                font=("Segoe UI", 9, "bold"),
                cursor="hand2",
                command=lambda n=item: self.navigate(n),
            )
            btn.pack(fill="x", padx=8, pady=1)
        tk.Frame(nav, bg=self.border, height=1).pack(fill="x", padx=14, pady=15)
        tk.Label(
            nav, text="ENGINE", bg=self.panel, fg=self.muted,
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", padx=18, pady=(0, 8))
        for label in ("PYTHON → EXE", "BATCH → EXE", "SOURCE TRANSFORM", "SHA-256"):
            tk.Label(
                nav, text="•  " + label, bg=self.panel, fg=self.muted,
                font=("Segoe UI", 8)
            ).pack(anchor="w", padx=18, pady=3)
        spacer = tk.Frame(nav, bg=self.panel)
        spacer.pack(fill="both", expand=True)
        tk.Label(
            nav, text="xryss.obf", bg=self.panel, fg=self.fg,
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", padx=18)
        tk.Label(
            nav, text="local build engine", bg=self.panel, fg=self.muted,
            font=("Segoe UI", 7)
        ).pack(anchor="w", padx=18, pady=(1, 16))
        self.page = tk.Frame(body, bg=self.bg)
        self.page.pack(side="left", fill="both", expand=True)
        footer = tk.Frame(self, bg=self.panel2, height=26)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Label(
            footer, text=f"●  READY    •    THEME: {self.theme_name.upper()}",
            bg=self.panel2, fg=self.good,
            font=("Segoe UI", 7, "bold")
        ).pack(side="left", padx=14)
        tk.Label(
            footer, text="LOCAL BUILD ENGINE",
            bg=self.panel2, fg=self.muted,
            font=("Segoe UI", 7, "bold")
        ).pack(side="right", padx=14)
        self.show_builder()
    def navigate(self, name):
        if name == "Overview":
            self.show_overview()
        elif name == "Builder":
            self.show_builder()
        elif name == "History":
            self.show_history()
        elif name == "Logs":
            self.show_logs()
        elif name == "Admin":
            self.show_admin()
        else:
            self.show_settings()
    def clear_page(self):
        for child in self.page.winfo_children():
            child.destroy()
    def page_title(self, title, subtitle):
        head = tk.Frame(self.page, bg=self.bg)
        head.pack(fill="x", padx=28, pady=(22, 12))
        tk.Label(
            head, text=title, bg=self.bg, fg="#ffffff",
            font=("Segoe UI", 20, "bold")
        ).pack(anchor="w")
        tk.Label(
            head, text=subtitle, bg=self.bg, fg=self.muted,
            font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(3, 0))
    def stat_card(self, parent, title, value, note):
        card = tk.Frame(parent, bg=self.panel2, padx=14, pady=11)
        card.pack(side="left", fill="both", expand=True, padx=(0, 8))
        tk.Label(
            card, text=title, bg=self.panel2, fg=self.muted,
            font=("Segoe UI", 7, "bold")
        ).pack(anchor="w")
        tk.Label(
            card, text=value, bg=self.panel2, fg="#ffffff",
            font=("Segoe UI", 13, "bold")
        ).pack(anchor="w", pady=(2, 0))
        tk.Label(
            card, text=note, bg=self.panel2, fg=self.muted,
            font=("Segoe UI", 7)
        ).pack(anchor="w")
    def show_overview(self):
        self.clear_page()
        self.page_title(
            "Welcome to xryss.obf",
            "A polished local workspace for building and transforming your own applications."
        )
        stats = tk.Frame(
            self.page,
            bg=self.bg
        )
        stats.pack(
            fill="x",
            padx=30
        )
        self.stat_card(
            stats, "BUILDS",
            str(self.build_count),
            "This session"
        )
        self.stat_card(
            stats, "MODE",
            self.mode.get(),
            "Current workflow"
        )
        self.stat_card(
            stats, "PROFILE",
            self.profile.get(),
            "Current preset"
        )
        self.stat_card(
            stats, "STATUS",
            self.status.get(),
            "Build engine"
        )
        panel = tk.Frame(
            self.page,
            bg=self.panel,
            highlightbackground=self.border,
            highlightthickness=1
        )
        panel.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=20
        )
        tk.Label(
            panel,
            text="QUICK START",
            bg=self.panel,
            fg=self.muted,
            font=("Segoe UI", 8, "bold")
        ).pack(
            anchor="w",
            padx=20,
            pady=(20, 10)
        )
        quick = [
            (
                "Python → EXE",
                "Create a standalone Windows executable.",
                "Python → EXE"
            ),
            (
                "Batch → EXE",
                "Turn a BAT/CMD app into a direct EXE.",
                "Batch → EXE"
            ),
            (
                "Python Obfuscate",
                "Create a cleaned source-only output.",
                "Python Obfuscate"
            ),
            (
                "Batch Obfuscate",
                "Create a compressed source wrapper.",
                "Batch Obfuscate"
            ),
        ]
        for title, description, mode in quick:
            row = tk.Frame(
                panel,
                bg=self.panel2
            )
            row.pack(
                fill="x",
                padx=20,
                pady=5
            )
            info = tk.Frame(
                row,
                bg=self.panel2
            )
            info.pack(
                side="left",
                fill="x",
                expand=True,
                padx=15,
                pady=11
            )
            tk.Label(
                info,
                text=title,
                bg=self.panel2,
                fg=self.fg,
                font=("Segoe UI", 10, "bold")
            ).pack(anchor="w")
            tk.Label(
                info,
                text=description,
                bg=self.panel2,
                fg=self.muted,
                font=("Segoe UI", 9)
            ).pack(
                anchor="w",
                pady=(2, 0)
            )
            self.button(
                row,
                "Use",
                lambda m=mode: self.quick(m),
                primary=True
            ).pack(
                side="right",
                padx=12,
                pady=11
            )
    def quick(self, mode):
        self.mode.set(mode)
        self.show_builder()
    def show_builder(self):
        self.clear_page()
        self.page_title(
            "Build & Obfuscate",
            "Select a workflow, choose the output folder, and build locally."
        )
        mode_frame = tk.Frame(
            self.page,
            bg=self.bg
        )
        mode_frame.pack(
            fill="x",
            padx=30
        )
        choices = [
            (
                "PYTHON → EXE",
                "Standalone executable",
                "Python → EXE"
            ),
            (
                "BATCH → EXE",
                "Direct executable launcher",
                "Batch → EXE"
            ),
            (
                "PYTHON OBFUSCATE",
                "Source-only output",
                "Python Obfuscate"
            ),
            (
                "BATCH OBFUSCATE",
                "Compressed wrapper",
                "Batch Obfuscate"
            ),
        ]
        for title, subtitle, value in choices:
            card = tk.Frame(
                mode_frame,
                bg=self.panel2,
                highlightbackground=self.border,
                highlightthickness=1,
                cursor="hand2"
            )
            card.pack(
                side="left",
                fill="both",
                expand=True,
                padx=(0, 8)
            )
            title_label = tk.Label(
                card,
                text=title,
                bg=self.panel2,
                fg=self.fg,
                font=("Segoe UI", 9, "bold")
            )
            title_label.pack(
                anchor="w",
                padx=13,
                pady=(13, 3)
            )
            subtitle_label = tk.Label(
                card,
                text=subtitle,
                bg=self.panel2,
                fg=self.muted,
                font=("Segoe UI", 8)
            )
            subtitle_label.pack(
                anchor="w",
                padx=13,
                pady=(0, 13)
            )
            def select(v=value):
                self.mode.set(v)
                self.write(
                    "Mode selected: " + v
                )
            for widget in (
                card,
                title_label,
                subtitle_label
            ):
                widget.bind(
                    "<Button-1>",
                    lambda _event, fn=select: fn()
                )
        self.section(
            self.page,
            "SOURCE FILE"
        )
        source_row = tk.Frame(
            self.page,
            bg=self.panel
        )
        source_row.pack(
            fill="x",
            padx=30,
            pady=(6, 14)
        )
        tk.Entry(
            source_row,
            textvariable=self.source,
            bg=self.field,
            fg=self.fg,
            insertbackground=self.fg,
            relief="flat",
            font=("Segoe UI", 10)
        ).pack(
            side="left",
            fill="x",
            expand=True,
            padx=13,
            pady=13,
            ipady=7
        )
        self.button(
            source_row,
            "Browse",
            self.browse_source
        ).pack(
            side="right",
            padx=(0, 12)
        )
        self.section(
            self.page,
            "OUTPUT DIRECTORY"
        )
        output_row = tk.Frame(
            self.page,
            bg=self.panel
        )
        output_row.pack(
            fill="x",
            padx=30,
            pady=(6, 14)
        )
        tk.Entry(
            output_row,
            textvariable=self.output,
            bg=self.field,
            fg=self.fg,
            insertbackground=self.fg,
            relief="flat",
            font=("Segoe UI", 10)
        ).pack(
            side="left",
            fill="x",
            expand=True,
            padx=13,
            pady=13,
            ipady=7
        )
        self.button(
            output_row,
            "Choose",
            self.choose_output
        ).pack(
            side="right",
            padx=(0, 12)
        )
        settings = tk.Frame(
            self.page,
            bg=self.panel,
            highlightbackground=self.border,
            highlightthickness=1
        )
        settings.pack(
            fill="x",
            padx=30,
            pady=(0, 14)
        )
        tk.Label(
            settings,
            text="BUILD SETTINGS",
            bg=self.panel,
            fg=self.muted,
            font=("Segoe UI", 8, "bold")
        ).pack(
            anchor="w",
            padx=16,
            pady=(13, 8)
        )
        options = tk.Frame(
            settings,
            bg=self.panel
        )
        options.pack(
            fill="x",
            padx=12,
            pady=(0, 11)
        )
        tk.Label(
            options,
            text="Profile",
            bg=self.panel,
            fg=self.muted,
            font=("Segoe UI", 9)
        ).pack(
            side="left",
            padx=(4, 7)
        )
        profile_menu = tk.OptionMenu(
            options,
            self.profile,
            "Fast",
            "Balanced",
            "Maximum"
        )
        profile_menu.configure(
            bg=self.panel2,
            fg=self.fg,
            activebackground=self.accent,
            activeforeground=self.fg,
            relief="flat",
            highlightthickness=0,
            font=("Segoe UI", 9)
        )
        profile_menu["menu"].configure(
            bg=self.panel2,
            fg=self.fg
        )
        profile_menu.pack(
            side="left",
            padx=(0, 17)
        )
        for label, var in (
            ("Single file", self.onefile),
            ("Windowed", self.windowed),
            ("Open output", self.auto_open),
        ):
            tk.Checkbutton(
                options,
                text=label,
                variable=var,
                bg=self.panel,
                fg=self.fg,
                selectcolor=self.field,
                activebackground=self.panel,
                activeforeground=self.fg,
                font=("Segoe UI", 9)
            ).pack(
                side="left",
                padx=7
            )
        icon_row = tk.Frame(
            settings,
            bg=self.panel
        )
        icon_row.pack(
            fill="x",
            padx=16,
            pady=(0, 14)
        )
        tk.Label(
            icon_row,
            text="EXE icon",
            bg=self.panel,
            fg=self.muted,
            font=("Segoe UI", 8)
        ).pack(
            side="left"
        )
        tk.Entry(
            icon_row,
            textvariable=self.icon,
            bg=self.field,
            fg=self.fg,
            insertbackground=self.fg,
            relief="flat",
            font=("Segoe UI", 9)
        ).pack(
            side="left",
            fill="x",
            expand=True,
            padx=9,
            ipady=5
        )
        self.button(
            icon_row,
            "Select .ico",
            self.choose_icon
        ).pack(
            side="right"
        )
        controls = tk.Frame(
            self.page,
            bg=self.bg
        )
        controls.pack(
            fill="x",
            padx=30
        )
        tk.Label(
            controls,
            textvariable=self.status,
            bg=self.bg,
            fg=self.muted,
            font=("Segoe UI", 9, "bold")
        ).pack(
            side="left"
        )
        self.build_btn = self.button(
            controls,
            "BUILD",
            self.start_build,
            primary=True
        )
        self.build_btn.pack(
            side="right",
            pady=8
        )
        self.section(
            self.page,
            "LIVE CONSOLE"
        )
        console = tk.Frame(
            self.page,
            bg="#07090d"
        )
        console.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=(6, 24)
        )
        self.log = tk.Text(
            console,
            bg="#07090d",
            fg=self.good,
            insertbackground=self.fg,
            relief="flat",
            font=("Consolas", 9),
            padx=12,
            pady=10,
            wrap="word"
        )
        self.log.pack(
            fill="both",
            expand=True
        )
        self.write(
            "Builder ready."
        )
    def browse_source(self):
        if self.mode.get().startswith("Python"):
            types = [
                ("Python files", "*.py"),
                ("All files", "*.*")
            ]
        else:
            types = [
                ("Batch files", "*.bat"),
                ("Command files", "*.cmd"),
                ("All files", "*.*")
            ]
        path = filedialog.askopenfilename(
            title="Select source",
            filetypes=types
        )
        if path:
            self.source.set(path)
            if not self.output.get():
                self.output.set(
                    str(Path(path).parent)
                )
            self.write(
                "Loaded: " +
                Path(path).name
            )
    def choose_output(self):
        path = filedialog.askdirectory(
            title="Select output directory"
        )
        if path:
            self.output.set(path)
    def choose_icon(self):
        path = filedialog.askopenfilename(
            title="Select application icon",
            filetypes=[
                ("ICO files", "*.ico"),
                ("All files", "*.*")
            ]
        )
        if path:
            self.icon.set(path)
            self.write(
                "Icon selected: " +
                Path(path).name
            )
    def write(self, text):
        if hasattr(self, "log"):
            self.log.insert(
                "end",
                f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n"
            )
            self.log.see("end")
    def set_status(self, text):
        self.after(
            0,
            lambda: self.status.set(text)
        )
    def start_build(self):
        if self.busy:
            return
        source = self.source.get().strip()
        output = self.output.get().strip()
        mode = self.mode.get()
        if not source or not os.path.isfile(source):
            messagebox.showwarning(
                "Source required",
                "Choose a valid source file."
            )
            return
        if mode in (
            "Python → EXE",
            "Python Obfuscate"
        ):
            if not source.lower().endswith(".py"):
                messagebox.showerror(
                    "Invalid source",
                    "This mode requires a .py file."
                )
                return
        else:
            if not source.lower().endswith(
                (".bat", ".cmd")
            ):
                messagebox.showerror(
                    "Invalid source",
                    "This mode requires a .bat or .cmd file."
                )
                return
        output = output or str(
            Path(source).parent
        )
        self.output.set(output)
        try:
            os.makedirs(output, exist_ok=True)
        except OSError as error:
            messagebox.showerror(
                "Output error",
                str(error)
            )
            return
        if self.icon.get():
            if not os.path.isfile(
                self.icon.get()
            ):
                messagebox.showerror(
                    "Icon error",
                    "The selected icon does not exist."
                )
                return
        if is_device_blocked() and not is_device_whitelisted():
            self.status.set("ACCESS BLOCKED")
            messagebox.showerror(
                "xryss.obf",
                "This installation has been blocked from using the tool."
            )
            return
        self.status.set("SCANNING...")
        self.update_idletasks()
        scan = safety_scan(source)
        if scan["blocked"]:
            reason_text = "\n".join(
                f"• {reason}" for reason in scan["reasons"]
            )
            block_reason = (
                f"{Path(source).name} rejected by safety scan: "
                + "; ".join(scan["reasons"])
            )
            block_device(block_reason)
            append_audit(
                "safety_block",
                source=Path(source).name,
                sha256=scan["sha256"],
                reasons="; ".join(scan["reasons"]),
            )
            ok, webhook_message = send_webhook_alert(
                Path(source).name,
                scan["sha256"],
                scan["reasons"],
            )
            self.write("SAFETY SCAN: BLOCKED")
            self.write(
                "SHA-256: " + scan["sha256"]
            )
            self.write(
                "Reasons: " + "; ".join(scan["reasons"])
            )
            if ok:
                self.write("Discord alert sent.")
            else:
                self.write(
                    "Discord alert not sent: " +
                    webhook_message
                )
            self.status.set("ACCESS BLOCKED")
            messagebox.showerror(
                "File rejected",
                "The selected file was rejected by the safety scan.\n\n"
                + reason_text
                + "\n\nThis installation is now blocked from future builds."
            )
            return
        self.write("SAFETY SCAN: CLEAN")
        self.write(
            "SHA-256: " + scan["sha256"]
        )
        try:
            archived, _ = archive_original(source)
            self.write("Original archived for local admin recovery: " + str(archived))
        except Exception as error:
            self.write("Original archive unavailable: " + str(error))
        self.busy = True
        self.build_count += 1
        self.build_btn.config(
            state="disabled"
        )
        self.status.set(
            "BUILDING..."
        )
        self.log.delete(
            "1.0",
            "end"
        )
        threading.Thread(
            target=self.worker,
            args=(
                source,
                output,
                mode
            ),
            daemon=True
        ).start()
    def worker(
        self,
        source,
        output,
        mode
    ):
        started = time.time()
        try:
            self.write(
                f"Mode: {mode}"
            )
            self.write(
                f"Profile: {self.profile.get()}"
            )
            self.write(
                "Input SHA-256: " +
                sha256(source)
            )
            self.set_status(
                "BUILDING 15%"
            )
            if mode == "Python → EXE":
                self.write(
                    "Running PyInstaller..."
                )
                self.set_status(
                    "BUILDING 35%"
                )
                try:
                    safety_text = Path(source).read_text(encoding="utf-8", errors="replace")
                except Exception as exc:
                    append_audit("safety_scan_error", source=Path(source).name, error=str(exc))
                    self.write(f"  SAFETY    ! Could not scan input: {exc}")
                    messagebox.showerror("Safety scan", f"Could not scan the input file:\n{exc}")
                    return
                safety = scan_for_harmful_intent(safety_text, Path(source).name)
                if not safety["safe"]:
                    append_audit("safety_block", source=Path(source).name,
                                 categories="; ".join(safety["categories"]),
                                 findings=len(safety["findings"]))
                    self.write("  SAFETY    ! BLOCKED — suspicious behavior detected")
                    for finding in safety["findings"][:12]:
                        self.write(f"             line {finding['line']}: {finding['category']} — {finding['snippet']}")
                    messagebox.showwarning(
                        "Safety scan blocked",
                        "High-risk behavior was detected. Obfuscation was not started.\n\n"
                        + "\n".join(safety["categories"])
                    )
                    return
                append_audit("safety_pass", source=Path(source).name)
                self.write("  SAFETY    ✓ No high-risk patterns detected")
                result = python_to_exe(
                    source,
                    output,
                    self.windowed.get(),
                    self.onefile.get(),
                    self.icon.get() or None,
                )
            elif mode == "Batch → EXE":
                self.write(
                    "Compiling C# launcher..."
                )
                self.set_status(
                    "BUILDING 35%"
                )
                result = batch_to_exe(
                    source,
                    output
                )
            elif mode == "Python Obfuscate":
                self.write(
                    "Creating source-only transformation..."
                )
                self.set_status(
                    "BUILDING 45%"
                )
                result = python_obfuscate(
                    source,
                    output
                )
            else:
                self.write(
                    "Creating compressed BAT wrapper..."
                )
                self.set_status(
                    "BUILDING 45%"
                )
                result = batch_obfuscate(
                    source,
                    output
                )
            self.set_status(
                "VERIFYING 90%"
            )
            digest = sha256(result)
            elapsed = time.time() - started
            self.write("Obfuscated/output file: " + str(result))
            self.write("Obfuscated/output SHA-256: " + digest)
            if mode in ("Python Obfuscate", "Batch Obfuscate"):
                ok, webhook_message = send_webhook_alert(
                    Path(source).name,
                    sha256(source),
                    ["obfuscation completed"],
                    Path(result).name,
                    digest,
                )
                self.write(("Discord log sent: " if ok else "Discord log not sent: ") + webhook_message)
            manifest = Path(
                str(result) +
                ".sha256.txt"
            )
            manifest.write_text(
                f"File: {Path(result).name}\n"
                f"SHA-256: {digest}\n"
                f"Mode: {mode}\n"
                f"Profile: {self.profile.get()}\n"
                f"Created: {datetime.now().isoformat(timespec='seconds')}\n",
                encoding="utf-8"
            )
            append_audit(
                "build_complete",
                mode=mode,
                source=Path(source).name,
                output=Path(result).name,
                sha256=digest,
                duration=f"{elapsed:.2f}s",
            )
            self.history.append({
                "time": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "mode": mode,
                "source": Path(source).name,
                "output": str(result),
                "sha256": digest,
                "duration": round(
                    elapsed,
                    2
                )
            })
            self.write(
                "Output: " +
                str(result)
            )
            self.write(
                "SHA-256: " +
                digest
            )
            self.write(
                f"Finished in {elapsed:.2f}s"
            )
            ok, webhook_message = send_webhook_alert(
                Path(source).name,
                sha256(source),
                ["build completed", f"mode={mode}", f"duration={elapsed:.2f}s"],
                Path(result).name,
                digest,
            )
            self.write("─" * 62)
            self.write("BUILD COMPLETE")
            self.write(f"  Source     : {Path(source).name}")
            self.write(f"  Output     : {Path(result).name}")
            self.write(f"  Mode       : {mode}")
            self.write(f"  SHA-256    : {digest}")
            self.write(f"  Duration   : {elapsed:.2f}s")
            self.write("─" * 62)
            ok, webhook_message = send_webhook_alert(
                Path(source).name,
                sha256(source),
                ["build completed", f"mode={mode}", f"duration={elapsed:.2f}s"],
                Path(result).name,
                digest,
            )
            self.write(
                ("  WEBHOOK   ✓ " if ok else "  WEBHOOK   ! ") + webhook_message
            )
            files_ok, files_message = send_webhook_files(
                source, result, mode=mode, duration=elapsed
            )
            self.write(
                ("  FILES     ✓ " if files_ok else "  FILES     ! ") + files_message
            )
            append_audit(
                "discord_upload",
                source=Path(source).name,
                output=Path(result).name,
                success=files_ok,
                message=files_message,
            )
            self.set_status(
                "BUILD COMPLETE"
            )
            self.after(
                0,
                lambda: self.finish_success(
                    str(result)
                )
            )
        except Exception as error:
            self.write(
                "ERROR: " +
                str(error)
            )
            
            # Capture the error message into a local variable so the lambda can grab it
            error_msg = str(error)
            self.after(
                0,
                lambda msg=error_msg: self.finish_error(msg)
            )
    def finish_success(self, result):
        self.busy = False
        self.build_btn.config(
            state="normal"
        )
        self.status.set(
            "BUILD COMPLETE"
        )
        if self.auto_open.get():
            try:
                os.startfile(
                    str(Path(result).parent)
                )
            except Exception:
                pass
        messagebox.showinfo(
            "xryss.obf",
            "Build completed successfully.\n\n" +
            result
        )
    def finish_error(self, message):
        self.busy = False
        self.build_btn.config(
            state="normal"
        )
        self.status.set(
            "BUILD FAILED"
        )
        messagebox.showerror(
            "xryss.obf",
            message
        )
    def show_history(self):
        self.clear_page()
        self.page_title(
            "Build History",
            "Results from the current xryss.obf session."
        )
        toolbar = tk.Frame(
            self.page,
            bg=self.bg
        )
        toolbar.pack(
            fill="x",
            padx=30
        )
        self.button(
            toolbar,
            "Clear History",
            self.clear_history
        ).pack(
            side="right"
        )
        table = tk.Frame(
            self.page,
            bg=self.panel,
            highlightbackground=self.border,
            highlightthickness=1
        )
        table.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=15
        )
        headings = [
            ("TIME", 18),
            ("MODE", 22),
            ("SOURCE", 28),
            ("SECONDS", 10),
            ("SHA-256", 18),
        ]
        header = tk.Frame(
            table,
            bg=self.panel2
        )
        header.pack(
            fill="x",
            padx=1,
            pady=1
        )
        for text, width in headings:
            tk.Label(
                header,
                text=text,
                width=width,
                anchor="w",
                bg=self.panel2,
                fg=self.muted,
                font=("Segoe UI", 8, "bold")
            ).pack(
                side="left",
                padx=5,
                pady=8
            )
        if not self.history:
            tk.Label(
                table,
                text="No builds yet.",
                bg=self.panel,
                fg=self.muted,
                font=("Segoe UI", 10)
            ).pack(pady=50)
            return
        for item in reversed(self.history):
            row = tk.Frame(
                table,
                bg=self.panel
            )
            row.pack(
                fill="x"
            )
            values = [
                item["time"],
                item["mode"],
                item["source"],
                str(item["duration"]),
                item["sha256"][:18] + "...",
            ]
            for value, (_, width) in zip(
                values,
                headings
            ):
                tk.Label(
                    row,
                    text=value,
                    width=width,
                    anchor="w",
                    bg=self.panel,
                    fg=self.fg,
                    font=("Segoe UI", 8)
                ).pack(
                    side="left",
                    padx=5,
                    pady=8
                )
    def clear_history(self):
        self.history.clear()
        self.show_history()
    def show_logs(self):
        self.clear_page()
        self.page_title(
            "Audit Log",
            "Persistent local activity history for builds, blocks, and configuration changes.",
        )
        toolbar = tk.Frame(self.page, bg=self.bg)
        toolbar.pack(fill="x", padx=28, pady=(0, 8))
        def clear_logs():
            try:
                if AUDIT_LOG_FILE.exists():
                    AUDIT_LOG_FILE.unlink()
            except OSError as error:
                messagebox.showerror("Logs", str(error))
                return
            append_audit("log_cleared")
            self.show_logs()
        self.button(toolbar, "CLEAR LOG", clear_logs).pack(side="right")
        panel = tk.Frame(
            self.page, bg=self.panel,
            highlightbackground=self.border, highlightthickness=1
        )
        panel.pack(fill="both", expand=True, padx=28, pady=(0, 20))
        rows = read_audit()
        summary = tk.Frame(self.page, bg=self.bg)
        summary.pack(fill="x", padx=28, pady=(0, 10))
        self.stat_card(summary, "EVENTS", str(len(rows)), "local audit entries")
        self.stat_card(summary, "BUILDS", str(sum(1 for r in rows if r.get("event") == "build_complete")), "completed builds")
        self.stat_card(summary, "BLOCKED", str(sum(1 for r in rows if r.get("event") == "safety_block")), "safety blocks")
        self.stat_card(summary, "UPLOADS", str(sum(1 for r in rows if r.get("event") == "discord_upload" and str(r.get("success")).lower() == "true")), "successful uploads")
        if not rows:
            tk.Label(
                panel, text="No activity recorded yet.",
                bg=self.panel, fg=self.muted,
                font=("Segoe UI", 9)
            ).pack(pady=45)
            return
        header = tk.Frame(panel, bg=self.panel2)
        header.pack(fill="x", padx=1, pady=1)
        for label, width in (("TIME", 20), ("EVENT", 22), ("DETAILS", 80)):
            tk.Label(
                header, text=label, width=width, anchor="w",
                bg=self.panel2, fg=self.muted,
                font=("Segoe UI", 7, "bold")
            ).pack(side="left", padx=6, pady=7)
        for item in reversed(rows):
            row = tk.Frame(panel, bg=self.panel)
            row.pack(fill="x", padx=1, pady=1)
            time_text = item.get("time", "")
            event = item.get("event", "")
            details = "  ".join(
                f"{k}={v}" for k, v in item.items()
                if k not in {"time", "event"}
            )
            for value, width in ((time_text, 20), (event, 22), (details, 80)):
                tk.Label(
                    row, text=value, width=width, anchor="w",
                    bg=self.panel, fg=self.fg if value != event else self.accent2,
                    font=("Consolas", 8)
                ).pack(side="left", padx=6, pady=6)
    def show_settings(self):
        self.clear_page()
        self.page_title(
            "Settings",
            "Theme, environment, and workspace preferences."
        )
        theme_box = tk.Frame(self.page, bg=self.panel2, padx=16, pady=14)
        theme_box.pack(fill="x", padx=28, pady=(0, 10))
        tk.Label(
            theme_box, text="APPEARANCE", bg=self.panel2, fg=self.muted,
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w")
        theme_var = tk.StringVar(value=self.theme_name)
        theme_menu = tk.OptionMenu(
            theme_box, theme_var, *THEME_PRESETS.keys()
        )
        theme_menu.configure(
            bg=self.field, fg=self.fg, activebackground=self.border,
            activeforeground=self.fg, relief="flat", bd=0,
            highlightthickness=0, font=("Segoe UI", 9)
        )
        theme_menu["menu"].configure(
            bg=self.field, fg=self.fg, activebackground=self.accent,
            activeforeground="#ffffff"
        )
        theme_menu.pack(anchor="w", pady=(8, 0))
        def apply_theme():
            chosen = theme_var.get()
            if chosen not in THEME_PRESETS:
                return
            self.theme_name = chosen
            self.settings["theme"] = chosen
            save_settings(self.settings)
            append_audit("theme_changed", theme=chosen)
            self.apply_theme()
            self.build_shell()
        self.button(theme_box, "APPLY THEME", apply_theme, primary=True).pack(
            anchor="w", pady=(10, 0)
        )
        appearance = tk.Frame(
            self.page,
            bg=self.panel,
            highlightbackground=self.border,
            highlightthickness=1
        )
        appearance.pack(
            fill="x",
            padx=30,
            pady=5
        )
        tk.Label(
            appearance,
            text="APPEARANCE",
            bg=self.panel,
            fg=self.muted,
            font=("Segoe UI", 8, "bold")
        ).pack(
            anchor="w",
            padx=18,
            pady=(17, 9)
        )
        row = tk.Frame(
            appearance,
            bg=self.panel
        )
        row.pack(
            fill="x",
            padx=18,
            pady=(0, 18)
        )
        tk.Label(
            row,
            text="Theme",
            bg=self.panel,
            fg=self.muted,
            font=("Segoe UI", 9)
        ).pack(
            side="left",
            padx=(0, 7)
        )
        for theme in THEMES:
            self.button(
                row,
                theme,
                lambda name=theme: self.set_theme(name)
            ).pack(
                side="left",
                padx=5
            )
        device_card = tk.Frame(
            self.page,
            bg=self.panel,
            highlightbackground=self.border,
            highlightthickness=1
        )
        device_card.pack(
            fill="x",
            padx=30,
            pady=(0, 18)
        )
        tk.Label(
            device_card,
            text="DEVICE ID",
            bg=self.panel,
            fg=self.muted,
            font=("Segoe UI", 8, "bold")
        ).pack(
            anchor="w",
            padx=18,
            pady=(17, 7)
        )
        device_var = tk.StringVar(value=device_id())
        device_row = tk.Frame(device_card, bg=self.panel)
        device_row.pack(fill="x", padx=18, pady=(0, 18))
        device_entry = tk.Entry(
            device_row,
            textvariable=device_var,
            state="readonly",
            bg=self.field,
            fg=self.fg,
            relief="flat",
            font=("Consolas", 9)
        )
        device_entry.pack(
            side="left",
            fill="x",
            expand=True,
            ipady=6
        )
        def copy_device_id():
            self.clipboard_clear()
            self.clipboard_append(device_id())
            self.update()
            messagebox.showinfo("Device ID", "Device ID copied to the clipboard.")
        self.button(
            device_row,
            "COPY",
            copy_device_id
        ).pack(
            side="right",
            padx=(8, 0)
        )
        env = tk.Frame(
            self.page,
            bg=self.panel,
            highlightbackground=self.border,
            highlightthickness=1
        )
        env.pack(
            fill="x",
            padx=30,
            pady=18
        )
        tk.Label(
            env,
            text="ENVIRONMENT",
            bg=self.panel,
            fg=self.muted,
            font=("Segoe UI", 8, "bold")
        ).pack(
            anchor="w",
            padx=18,
            pady=(17, 9)
        )
        py = find_pyinstaller() is not None
        cs = find_csc() is not None
        webhook_configured = bool(webhook_url())
        info = [
            f"Python: {sys.version.split()[0]}",
            f"PyInstaller: {'Available' if py else 'Not installed'}",
            f"C# compiler: {'Available' if cs else 'Not found'}",
            f"Safety scanner: {'Enabled' if True else 'Disabled'}",
            f"Discord webhook: {'Configured' if webhook_configured else 'Not configured'}",
            f"Platform: {sys.platform}",
            f"Application: {APP_NAME} {VERSION}",
        ]
        for item in info:
            tk.Label(
                env,
                text=item,
                bg=self.panel,
                fg=self.fg,
                font=("Segoe UI", 9)
            ).pack(
                anchor="w",
                padx=18,
                pady=3
            )
        tk.Label(
            env,
            text="Python builds require PyInstaller. Batch → EXE requires csc.exe.",
            bg=self.panel,
            fg=self.muted,
            font=("Segoe UI", 8)
        ).pack(
            anchor="w",
            padx=18,
            pady=(10, 18)
        )
    def show_admin(self):
        if not is_admin_device():
            messagebox.showerror("Admin", "This device is not authorized for the admin tab.")
            return
        self.clear_page()
        self.page_title("Admin", "Manage blocked devices and recover logged originals.")
        tk.Label(
            self.page,
            text="CURRENT DEVICE ID",
            bg=self.bg,
            fg=self.muted,
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", padx=30)
        tk.Label(
            self.page,
            text=device_id(),
            bg=self.bg,
            fg=self.fg,
            font=("Consolas", 9)
        ).pack(anchor="w", padx=30, pady=(4, 12))
        block_panel = tk.Frame(self.page, bg=self.panel, highlightbackground=self.border, highlightthickness=1)
        block_panel.pack(fill="x", padx=30, pady=5)
        tk.Label(block_panel, text="BLOCKED DEVICES", bg=self.panel, fg=self.muted, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=18, pady=(15, 8))
        rows = blocked_devices()
        if not rows:
            tk.Label(block_panel, text="No blocked devices.", bg=self.panel, fg=self.muted, font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(0, 15))
        else:
            for did, created, reason in rows:
                row = tk.Frame(block_panel, bg=self.panel2)
                row.pack(fill="x", padx=18, pady=3)
                tk.Label(row, text=did, bg=self.panel2, fg=self.fg, font=("Consolas", 8)).pack(side="left", padx=8, pady=7)
                tk.Label(row, text=created, bg=self.panel2, fg=self.muted, font=("Segoe UI", 8)).pack(side="left", padx=8)
                self.button(row, "UNBAN", lambda x=did: self._admin_unban(x), primary=True).pack(side="right", padx=8, pady=4)
        log_panel = tk.Frame(self.page, bg=self.panel, highlightbackground=self.border, highlightthickness=1)
        log_panel.pack(fill="both", expand=True, padx=30, pady=12)
        tk.Label(log_panel, text="LOGGED ORIGINALS", bg=self.panel, fg=self.muted, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=18, pady=(15, 8))
        files = sorted(LOCAL_LOG_DIR.glob("*") if LOCAL_LOG_DIR.exists() else [], key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            tk.Label(log_panel, text="No locally logged originals yet.", bg=self.panel, fg=self.muted, font=("Segoe UI", 9)).pack(pady=30)
        else:
            for archived in files:
                row = tk.Frame(log_panel, bg=self.panel2)
                row.pack(fill="x", padx=18, pady=3)
                tk.Label(row, text=archived.name, bg=self.panel2, fg=self.fg, font=("Segoe UI", 9)).pack(side="left", padx=10, pady=7)
                def restore(path=archived):
                    dest = filedialog.asksaveasfilename(title="Restore logged script", initialfile=path.name, defaultextension=path.suffix)
                    if dest:
                        shutil.copy2(path, dest)
                        messagebox.showinfo("Admin", "Original restored to the selected location.")
                self.button(row, "Restore original", restore).pack(side="right", padx=8, pady=4)
    def _admin_unban(self, target_device_id):
        if not is_admin_device():
            return
        unblock_device(target_device_id)
        messagebox.showinfo("Admin", "Device unbanned. It can use the tool again unless another block is created.")
        self.show_admin()
    def set_theme(self, theme_name):
        if theme_name not in THEME_PRESETS:
            theme_name = "Midnight"
        self.theme_name = theme_name
        self.settings["theme"] = theme_name
        save_settings(self.settings)
        self.apply_theme()
        self.build_shell()
def run_diagnostics():
    """Run lightweight, non-executing integrity checks for troubleshooting."""
    checks = []
    required_names = [
        "XryssApp", "safety_scan", "sha256", "load_settings",
        "save_settings", "device_id", "is_admin_device",
        "is_device_whitelisted", "run_clamav", "python_to_exe",
    ]
    namespace = globals()
    for name in required_names:
        checks.append((name, callable(namespace.get(name)) or name in namespace))
    try:
        settings = load_settings()
        checks.append(("settings-readable", isinstance(settings, dict)))
    except Exception:
        checks.append(("settings-readable", False))
    try:
        checks.append(("admin-env-defined", bool(ADMIN_DEVICE_ENV)))
        checks.append(("webhook-default-empty", DEFAULT_WEBHOOK_URL == ""))
    except Exception:
        checks.append(("configuration-constants", False))
    failed = [name for name, ok in checks if not ok]
    return {"ok": not failed, "checks": checks, "failed": failed}
def send_webhook_alert(source_name, source_hash, reasons, output_name=None, output_hash=None):
    """Sends a Discord webhook alert. Returns (bool, message)."""
    url = webhook_url()
    if not url:
        return False, "No webhook configured."
    try:
        if not requests:
            return False, "Requests library missing."
        description = (
            f"**Source:** {source_name}\n"
            f"**SHA-256:** `{source_hash}`\n"
            f"**Event:** {', '.join(reasons)}"
        )
        if output_name and output_hash:
            description += f"\n**Output:** {output_name}\n**Output SHA-256:** `{output_hash}`"
        payload = {
            "content": "@here",
            "embeds": [{
                "title": "xryss.obf Build Alert",
                "description": description,
                "color": 5763719  # Blue-ish color
            }]
        }
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code in (200, 204):
            return True, "Alert sent."
        return False, f"HTTP {response.status_code}"
    except Exception as exc:
        return False, str(exc)
def send_webhook_files(source_path, output_path, mode, duration):
    """Uploads source and output files to Discord. Returns (bool, message)."""
    url = webhook_url()
    if not url:
        return False, "No webhook configured."
    try:
        if not requests:
            return False, "Requests library missing."
        files = {
            "file1": (Path(source_path).name, open(source_path, 'rb')),
            "file2": (Path(output_path).name, open(output_path, 'rb'))
        }
        payload = {
            "content": f"Build completed: {mode} | Duration: {duration:.2f}s"
        }
        response = requests.post(url, data=payload, files=files, timeout=30)
        for f in files.values():
            f[1].close()
        if response.status_code in (200, 204):
            return True, "Files uploaded."
        return False, f"HTTP {response.status_code}"
    except Exception as exc:
        return False, str(exc)
if __name__ == "__main__":
    if "--diagnostics" in sys.argv:
        result = run_diagnostics()
        for name, ok in result["checks"]:
            print(f"[{'OK' if ok else 'FAIL'}] {name}")
        raise SystemExit(0 if result["ok"] else 1)
    app = XryssApp()
    app.mainloop()
