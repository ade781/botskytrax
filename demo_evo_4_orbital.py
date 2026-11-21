#!/usr/bin/env python3
"""
demo_evo_4_orbital.py — 5-Stage Orbital Uplink // Satcom SIGINT Simulation
100% standalone dummy/mock simulation (NO real file reads, NO HTTP requests, UI_WIDTH = 80).
"""

from __future__ import annotations

import argparse
import os
import random
import re
import sys
import time
from datetime import datetime

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    import colorama
    from colorama import Fore, Style

    colorama.init(autoreset=True)
except Exception:  # pragma: no cover
    class _FallbackFore:
        CYAN = "\x1b[36m"
        LIGHTCYAN_EX = "\x1b[96m"
        MAGENTA = "\x1b[35m"
        LIGHTMAGENTA_EX = "\x1b[95m"
        GREEN = "\x1b[32m"
        LIGHTGREEN_EX = "\x1b[92m"
        YELLOW = "\x1b[33m"
        LIGHTYELLOW_EX = "\x1b[93m"
        RED = "\x1b[31m"
        LIGHTRED_EX = "\x1b[91m"
        WHITE = "\x1b[37m"
        LIGHTBLACK_EX = "\x1b[90m"
        RESET = "\x1b[39m"

    class _FallbackStyle:
        BRIGHT = "\x1b[1m"
        DIM = "\x1b[2m"
        RESET_ALL = "\x1b[0m"

    Fore = _FallbackFore()  # type: ignore
    Style = _FallbackStyle()  # type: ignore

try:
    import winsound
except Exception:  # pragma: no cover
    winsound = None  # type: ignore


UI_WIDTH = 80
INNER_WIDTH = UI_WIDTH - 2
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# v2 Neon / Orbital HUD palette
C_CYAN = Fore.LIGHTCYAN_EX + Style.BRIGHT
C_MAG = Fore.LIGHTMAGENTA_EX + Style.BRIGHT
C_GREEN = Fore.LIGHTGREEN_EX + Style.BRIGHT
C_YEL = Fore.LIGHTYELLOW_EX + Style.BRIGHT
C_RED = Fore.LIGHTRED_EX + Style.BRIGHT
C_DIM = Fore.LIGHTBLACK_EX
C_WHITE = Fore.WHITE + Style.BRIGHT
C_RST = Style.RESET_ALL

# basic submit_survey.py palette
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"
DIM = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"

# v3 SIGINT Command palette
C_TEXT = Fore.WHITE
C_GRAY = Fore.LIGHTBLACK_EX
C_AMBER = Style.BRIGHT + Fore.YELLOW
C_RESET = Style.RESET_ALL

BRAILLE_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
GLITCH_CHARS = "!@#$%^&*░▒▓█<>/\\[]{}01ABCDEF"
SIGNAL_BARS = ["▂", "▄", "▆", "█"]


def beep(freq: int = 880, duration_ms: int = 45, silent: bool = False) -> None:
    """Play an optional Windows console beep safely."""
    if silent or winsound is None:
        return
    try:
        winsound.Beep(freq, duration_ms)
    except Exception:
        pass


def strip_ansi(text: str) -> str:
    """Return text with ANSI escape sequences removed."""
    return ANSI_RE.sub("", text)


def visible_len(text: str) -> int:
    """Return printable column width ignoring ANSI color escapes."""
    return len(strip_ansi(text))


def pad_right(text: str, width: int) -> str:
    """Pad ANSI-colored text on the right to exact visible width."""
    vis_len = visible_len(text)
    if vis_len >= width:
        return text
    return text + (" " * (width - vis_len))


def center_text(text: str, width: int) -> str:
    """Center ANSI-colored text within exact visible width."""
    vis_len = visible_len(text)
    if vis_len >= width:
        return text
    left_pad = (width - vis_len) // 2
    right_pad = width - vis_len - left_pad
    return (" " * left_pad) + text + (" " * right_pad)


def pad_line(text: str, width: int = INNER_WIDTH, align: str = "left") -> str:
    """Pad or clip a styled string to exact visible column width."""
    vlen = visible_len(text)
    if vlen > width:
        plain = strip_ansi(text)
        return plain[:width]
    pad = width - vlen
    if align == "center":
        left = pad // 2
        right = pad - left
        return (" " * left) + text + (" " * right)
    if align == "right":
        return (" " * pad) + text
    return text + (" " * pad)


def clear_screen() -> None:
    """Clear terminal viewport safely when running in a TTY."""
    if sys.stdout.isatty():
        os.system("cls" if os.name == "nt" else "clear")


def now_hms() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ---------------------------------------------------------------------------
# Box helpers (80-col)
# ---------------------------------------------------------------------------

def v2_box_top(border_color: str = C_CYAN, tag: str = "") -> str:
    if tag:
        label = f"═[{tag}]"
        rem = max(0, INNER_WIDTH - len(label))
        return f"{border_color}╔{label}{'═' * rem}╗{C_RST}"
    return f"{border_color}╔{'═' * INNER_WIDTH}╗{C_RST}"


def v2_box_sep(border_color: str = C_CYAN, tag: str = "") -> str:
    if tag:
        label = f"═[{tag}]"
        rem = max(0, INNER_WIDTH - len(label))
        return f"{border_color}╠{label}{'═' * rem}╣{C_RST}"
    return f"{border_color}╠{'═' * INNER_WIDTH}╣{C_RST}"


def v2_box_bottom(border_color: str = C_CYAN) -> str:
    return f"{border_color}╚{'═' * INNER_WIDTH}╝{C_RST}"


def v2_box_row(
    content: str,
    border_color: str = C_CYAN,
    align: str = "left",
    pad_x: int = 1,
) -> str:
    inner_w = INNER_WIDTH - (pad_x * 2)
    padded = pad_line(content, inner_w, align=align)
    spaces = " " * pad_x
    return f"{border_color}║{C_RST}{spaces}{padded}{spaces}{border_color}║{C_RST}"


def hud_tag_row(left_tag: str, right_tag: str, color: str = C_CYAN) -> str:
    left = f"┌─[{left_tag}]─┐"
    right = f"┌─[{right_tag}]─┐"
    gap = max(1, UI_WIDTH - len(left) - len(right))
    return f"{color}{left}{'─' * gap}{right}{C_RST}"


def v2_progress_bar(ratio: float, width: int = 32, fill_color: str = C_GREEN) -> str:
    clamped = max(0.0, min(1.0, ratio))
    filled = int(round(clamped * width))
    empty = width - filled
    return f"{fill_color}{'█' * filled}{C_DIM}{'░' * empty}{C_RST}"


def basic_box_top(width: int = UI_WIDTH, color: str = GREEN) -> str:
    return f"{color}╔{'═' * (width - 2)}╗{RESET}"


def basic_box_sep(width: int = UI_WIDTH, color: str = GREEN) -> str:
    return f"{color}╠{'═' * (width - 2)}╣{RESET}"


def basic_box_bottom(width: int = UI_WIDTH, color: str = GREEN) -> str:
    return f"{color}╚{'═' * (width - 2)}╝{RESET}"


def basic_box_line(text: str = "", width: int = UI_WIDTH, color: str = GREEN, align: str = "left") -> str:
    inner_width = width - 4
    vis_len = visible_len(text)
    if vis_len > inner_width:
        plain = strip_ansi(text)
        content = plain[: inner_width - 3] + "..."
    else:
        content = center_text(text, inner_width) if align == "center" else pad_right(text, inner_width)
    return f"{color}║{RESET} {content} {color}║{RESET}"


def basic_progress_bar(current: int, total: int, bar_width: int = 30, fill_color: str = CYAN) -> str:
    pct = (current / total * 100.0) if total > 0 else 0.0
    filled = int(round(bar_width * current / total)) if total > 0 else 0
    filled = max(0, min(bar_width, filled))
    bar = f"{fill_color}{'█' * filled}{DIM}{'░' * (bar_width - filled)}{RESET}"
    return f"[{bar}] {BOLD}{pct:5.1f}%{RESET}"


def v3_box_top(border_color: str = C_GRAY) -> str:
    return f"{border_color}╔{'═' * (UI_WIDTH - 2)}╗{C_RESET}"


def v3_box_sep(border_color: str = C_GRAY) -> str:
    return f"{border_color}╠{'═' * (UI_WIDTH - 2)}╣{C_RESET}"


def v3_box_bottom(border_color: str = C_GRAY) -> str:
    return f"{border_color}╚{'═' * (UI_WIDTH - 2)}╝{C_RESET}"


def v3_box_row(content: str = "", border_color: str = C_GRAY, align: str = "left") -> str:
    inner = pad_line(content, UI_WIDTH - 4, align=align)
    return f"{border_color}║{C_RESET} {inner} {border_color}║{C_RESET}"


def signal_meter(ratio: float) -> str:
    """Render a rising 4-bar signal strength meter (▂▄▆█) for a 0..1 ratio."""
    clamped = max(0.0, min(1.0, ratio))
    level = min(4, max(1, int(clamped * 4) + (1 if clamped > 0 else 0)))
    if clamped >= 0.99:
        level = 4
    active_col = C_GREEN if level >= 4 else (C_CYAN if level >= 2 else C_YEL)
    active = "".join(SIGNAL_BARS[:level])
    inactive = "".join(SIGNAL_BARS[level:])
    return f"{active_col}{active}{C_DIM}{inactive}{C_RST}"


# ===========================================================================
# STAGE 1: Intro (v2) — ORBITAL_UPLINK // SATCOM SIGINT Boot Sequence
# ===========================================================================

def run_boot_sequence(auto: bool = False) -> None:
    """Simulate orbital ground-station handshake, ephemeris sync, and cipher unlock."""
    clear_screen()
    print(hud_tag_row("ORBITAL_UPLINK v4.0", "BOOT::SATCOM_SIGINT", C_CYAN))
    print(v2_box_top(C_CYAN, "HUD::SATCOM_LINK"))
    print(v2_box_row(f"{C_MAG}ORBITAL_UPLINK{C_RST} :: {C_YEL}SATCOM SIGINT TRANSPONDER ARRAY v4.0{C_RST}", C_CYAN, align="center"))
    print(v2_box_bottom(C_CYAN))

    steps = [
        ("GND_ARRAY", "Calibrating Ku-band phased dish @ 14.2 GHz", C_CYAN),
        ("EPHEMERIS", "Predicting LEO-09 / GEO-04 orbital pass window", C_YEL),
        ("CRYPTO_SYNC", "Loading frequency-hopping TRANSEC key [0x09::ADE]", C_MAG),
        ("BEAM_LOCK", "Acquiring transponder carrier :: ZERO TRACE", C_GREEN),
    ]
    for code, msg, col in steps:
        for i in range(4):
            spinner = BRAILLE_FRAMES[i % len(BRAILLE_FRAMES)]
            sys.stdout.write(f"\r  {col}[{spinner}] {code:<12}{C_RST} │ {msg}...")
            sys.stdout.flush()
            time.sleep(0.05 if auto else 0.08)
        sys.stdout.write(f"\r  {C_GREEN}[✓] {code:<12}{C_RST} │ {msg} {C_GREEN}[OK]{C_RST}\n")
        sys.stdout.flush()
        beep(740, 30, silent=auto)

    target = "ORBITAL UPLINK ESTABLISHED :: ADE7ASLI"
    print()
    for step in range(12):
        reveal = int((step + 1) / 12 * len(target))
        scrambled = "".join(
            target[idx] if idx < reveal else random.choice(GLITCH_CHARS)
            for idx in range(len(target))
        )
        color = C_GREEN if step == 11 else (C_MAG if step % 2 == 0 else C_CYAN)
        sys.stdout.write(f"\r  {C_YEL}>> DECRYPT:{C_RST} {color}{scrambled}{C_RST}")
        sys.stdout.flush()
        time.sleep(0.04 if auto else 0.06)
    print("\n")
    beep(1046, 70, silent=auto)
    time.sleep(0.25 if auto else 0.4)


# ===========================================================================
# STAGE 2: Tampilan Awal (basic) — 80-col Orbital Command Center
# ===========================================================================

def print_welcome_banner() -> None:
    """Display WELCOME + ADE7ASLI ASCII Art inside an 80-col basic frame."""
    welcome_art = [
        " _    _ _____ _     _____ _____ __  __ _____ ",
        "| |  | |  ___| |   /  __ \\  _  |  \\/  |  ___|",
        "| |  | | |__ | |   | /  \\/ | | | .  . | |__  ",
        "| |/\\| |  __|| |   | |   | | | | |\\/| |  __| ",
        "\\  /\\  / |___| |___| \\__/\\ \\_/ / |  | | |___ ",
        " \\/  \\/\\____/\\_____/\\____/\\___/\\_|  |_/\\____/",
    ]
    ade_art = [
        "  ___  ______ _____ ______  ___   _____ _     _____ ",
        " / _ \\ |  _  \\  ___|___  / / _ \\ /  ___| |   |_   _|",
        "/ /_\\ \\| | | | |__    / / / /_\\ \\\\ `--.| |     | |  ",
        "|  _  || | | |  __|  / /  |  _  | `--. \\ |     | |  ",
        "| | | || |/ /| |___./ /   | | | |/\\__/ / |____ | |_ ",
        "\\_| |_/|___/ \\____/\\_/    \\_| |_/\\____/\\_____/\\___/ ",
    ]
    print(basic_box_top(UI_WIDTH, GREEN))
    for line in welcome_art:
        print(basic_box_line(f"{BOLD}{CYAN}{line}{RESET}", UI_WIDTH, GREEN, align="center"))
    for line in ade_art:
        print(basic_box_line(f"{BOLD}{GREEN}{line}{RESET}", UI_WIDTH, GREEN, align="center"))
    print(basic_box_line(f"{BOLD}{MAGENTA}<< ORBITAL_UPLINK // SATCOM SIGINT COMMAND CENTER >>{RESET}", UI_WIDTH, GREEN, align="center"))


def render_basic_dashboard(state: dict[str, int | str]) -> None:
    """Render the 80-col basic menu dashboard with dummy orbital telemetry stats."""
    next_idx = int(state["next_index"])
    total_emails = int(state["total_emails"])
    total_votes = int(state["total_votes_sent"])
    remaining = max(0, total_emails - next_idx)
    target_email = str(state["next_email"])

    print()
    print_welcome_banner()
    print(basic_box_sep(UI_WIDTH, GREEN))
    prog_bar = basic_progress_bar(next_idx, total_emails, bar_width=30, fill_color=CYAN)
    print(basic_box_line(f" {DIM}UPLINK QUEUE   :{RESET} {prog_bar}  ({CYAN}{next_idx}/{total_emails}{RESET})", UI_WIDTH, GREEN))
    print(basic_box_line(f" {DIM}PACKETS BEAMED :{RESET} {BOLD}{GREEN}{total_votes} pkts{RESET}    {DIM}│  REMAINING :{RESET} {BOLD}{YELLOW}{remaining} nodes{RESET}", UI_WIDTH, GREEN))
    if next_idx < total_emails:
        print(basic_box_line(f" {DIM}NEXT TRANSPOND :{RESET} {WHITE}Slot {next_idx + 2}{RESET} -> {CYAN}{target_email}{RESET}", UI_WIDTH, GREEN))
    else:
        print(basic_box_line(f" {DIM}NEXT TRANSPOND :{RESET} {BOLD}{YELLOW}ALL SLOTS EXHAUSTED (HABIS){RESET}", UI_WIDTH, GREEN))

    print(basic_box_sep(UI_WIDTH, GREEN))
    print(basic_box_line(f" {BOLD}{WHITE}SELECT ORBITAL EXECUTION VECTOR:{RESET}", UI_WIDTH, GREEN))
    print(basic_box_line(f"  {BOLD}{GREEN}[1]{RESET} {WHITE}10x   LEO BURST{RESET}     {DIM}│{RESET} {CYAN}10 beams{RESET}    {DIM}│{RESET}  1 ground slot  (10 pkts)", UI_WIDTH, GREEN))
    print(basic_box_line(f"  {BOLD}{GREEN}[2]{RESET} {WHITE}100x  SATCOM STORM{RESET}  {DIM}│{RESET} {CYAN}10 beams{RESET}    {DIM}│{RESET} 10 ground slots (100 pkts)", UI_WIDTH, GREEN))
    print(basic_box_line(f"  {BOLD}{RED}[3]{RESET} {YELLOW}1000x ORBITAL SALVO{RESET} {DIM}│{RESET} {RED}25 beams{RESET}    {DIM}│{RESET} 100 slots {RED}[MATRIX AUTH]{RESET}", UI_WIDTH, GREEN))
    print(basic_box_line(f"  {DIM}[0] EXIT TERMINAL{RESET}", UI_WIDTH, GREEN))
    print(basic_box_bottom(UI_WIDTH, GREEN))


# ===========================================================================
# STAGE 3: Opsi 3 Entry Animation + 2x2 Matrix (basic)
# ===========================================================================

def run_satellite_lock_on(auto: bool = False) -> None:
    """
    ~1.1s Satellite Lock-On Sequence right when Option 3 is selected,
    before the 2x2 matrix appears:
    ACQUIRING LEO-09 SAT-LINK -> random coordinates locking -> UPLINK LOCKED.
    """
    print()
    print(basic_box_top(UI_WIDTH, CYAN))
    print(basic_box_line(f"{BOLD}{YELLOW}ACQUIRING LEO-09 SAT-LINK // TELEMETRY TRACKING{RESET}", UI_WIDTH, CYAN, align="center"))
    print(basic_box_bottom(UI_WIDTH, CYAN))

    target_lat = 1.3521
    target_lon = 103.8198
    target_az = 214.6
    target_el = 67.4

    frames = 11
    for step in range(1, frames + 1):
        spin = BRAILLE_FRAMES[step % len(BRAILLE_FRAMES)]
        if step < frames:
            lat = target_lat + random.uniform(-4.5, 4.5) * (1.0 - step / frames)
            lon = target_lon + random.uniform(-6.0, 6.0) * (1.0 - step / frames)
            az = target_az + random.uniform(-18.0, 18.0) * (1.0 - step / frames)
            el = target_el + random.uniform(-12.0, 12.0) * (1.0 - step / frames)
            sig = signal_meter(step / frames * 0.85)
            sys.stdout.write(
                f"\r  {C_CYAN}[{spin}] ACQUIRING LEO-09 SAT-LINK{C_RST} │ "
                f"{C_YEL}LAT:{lat:+06.2f} LON:{lon:+07.2f} AZ:{az:05.1f}° EL:{el:04.1f}°{C_RST} {sig}"
            )
        else:
            sig = signal_meter(1.0)
            sys.stdout.write(
                f"\r  {C_GREEN}[✓] ACQUIRING LEO-09 SAT-LINK{C_RST} │ "
                f"{C_WHITE}LAT:{target_lat:+06.2f} LON:{target_lon:+07.2f} AZ:{target_az:05.1f}° EL:{target_el:04.1f}°{C_RST} {sig}"
            )
        sys.stdout.flush()
        time.sleep(0.10)  # 11 * 0.10s = 1.10s

    print(f"\n  {C_GREEN}[✓] UPLINK LOCKED :: LEO-09 TRANSPONDER READY (-61 dBm){C_RST}")
    beep(1020, 60, silent=auto)


def verify_1000x_matrix(auto_mode: bool = False) -> bool:
    """
    2x2 verification panel (CORE/NET/AUTH/EXEC: OFF -> READY) in 80 columns.
    Requires 4 root commands; hidden abort commands (root exit, root abort, batal).
    """
    modules = {
        "CORE": False,
        "NET": False,
        "AUTH": False,
        "EXEC": False,
    }
    ordered_cmds = [
        "root init core",
        "root sync net",
        "root auth ade7asli",
        "root exec 1000x",
    ]
    secret_commands = {
        "root init core": "CORE",
        "root sync net": "NET",
        "root auth ade7asli": "AUTH",
        "root exec 1000x": "EXEC",
    }
    hidden_abort_commands = {"root exit", "root abort", "batal"}

    def fmt_status(name: str, desc: str, is_ready: bool) -> str:
        state = f"{BOLD}{GREEN}[READY]{RESET}" if is_ready else f"{BOLD}{RED}[ OFF ]{RESET}"
        return f"{CYAN}{name:<4}{RESET} {DIM}({desc:<13}){RESET} : {state}"

    def verify_loading(mod_name: str) -> None:
        """1.5s loading animation with decryption scramble."""
        tech_msg = {
            "CORE": "Verifying orbital kernel & beam pool...",
            "NET": "Handshake Ku-band & satcom socket sync...",
            "AUTH": "Decrypting Ade7asli TRANSEC root key...",
            "EXEC": "Arming 1000x orbital salvo vector...",
        }.get(mod_name, f"Validating {mod_name}...")
        print(f" {CYAN}[*]{RESET} {tech_msg}")
        bar_width = 38
        target_word = "READY"
        cipher_chars = "X#9$K@2!Q%7&Z*4"
        for step in range(1, 11):
            pct = step * 10
            filled = int(bar_width * pct / 100)
            bar = "█" * filled + "░" * (bar_width - filled)
            unlocked = step // 2
            scrambled = "".join(
                target_word[i] if i < unlocked else random.choice(cipher_chars)
                for i in range(len(target_word))
            )
            color = GREEN if step == 10 else YELLOW
            sys.stdout.write(f"\r {color}[{bar}] {pct:3d}% // DECRYPT: {scrambled}{RESET}")
            sys.stdout.flush()
            time.sleep(0.15)  # 10 * 0.15s = 1.5s
        print()

    auto_step = 0
    while not all(modules.values()):
        print()
        print(basic_box_top(UI_WIDTH, YELLOW))
        print(basic_box_line(f"{BOLD}{RED}[!] 1000X ORBITAL SALVO MATRIX :: ROOT AUTHORIZATION REQUIRED{RESET}", UI_WIDTH, YELLOW, align="center"))
        print(basic_box_sep(UI_WIDTH, YELLOW))
        row1 = f" {fmt_status('CORE', 'Beam Kernel', modules['CORE'])}   │   {fmt_status('NET', 'Satcom Link', modules['NET'])}"
        row2 = f" {fmt_status('AUTH', 'TRANSEC Key', modules['AUTH'])}   │   {fmt_status('EXEC', '1000x Array', modules['EXEC'])}"
        print(basic_box_line(row1, UI_WIDTH, YELLOW))
        print(basic_box_line(row2, UI_WIDTH, YELLOW))
        print(basic_box_bottom(UI_WIDTH, YELLOW))

        prompt = f" {BOLD}{GREEN}root@Ade7asli:~#{RESET} "
        if auto_mode:
            cmd = ordered_cmds[auto_step]
            auto_step += 1
            time.sleep(0.2)
            print(f"{prompt}{YELLOW}{cmd}{RESET} {DIM}[AUTO-INJECT]{RESET}")
        else:
            try:
                cmd = input(prompt).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print(f"\n {RED}[!] ABORTED BY OPERATOR.{RESET}\n")
                return False

        if cmd in hidden_abort_commands:
            print(f" {RED}[!] ABORTED BY OPERATOR.{RESET}\n")
            beep(300, 120, silent=auto_mode)
            return False
        elif cmd in secret_commands:
            mod_name = secret_commands[cmd]
            if not modules[mod_name]:
                verify_loading(mod_name)
                modules[mod_name] = True
                print(f" {BOLD}{GREEN}[+] MODULE {mod_name} -> ONLINE / READY{RESET}")
                beep(880, 50, silent=auto_mode)
            else:
                print(f" {CYAN}[*] MODULE {mod_name} -> ALREADY READY{RESET}")
        else:
            print(f" {RED}[-] ACCESS DENIED // INVALID ROOT COMMAND{RESET}")
            beep(240, 100, silent=auto_mode)

    print()
    print(basic_box_top(UI_WIDTH, GREEN))
    print(basic_box_line(f"{BOLD}{GREEN}[+] ALL ORBITAL SYSTEMS ARMED // LAUNCHING 1000X SATCOM SALVO{RESET}", UI_WIDTH, GREEN, align="center"))
    print(basic_box_sep(UI_WIDTH, GREEN))
    print(basic_box_line(f" {fmt_status('CORE', 'Beam Kernel', True)}   │   {fmt_status('NET', 'Satcom Link', True)}", UI_WIDTH, GREEN))
    print(basic_box_line(f" {fmt_status('AUTH', 'TRANSEC Key', True)}   │   {fmt_status('EXEC', '1000x Array', True)}", UI_WIDTH, GREEN))
    print(basic_box_bottom(UI_WIDTH, GREEN))
    beep(1100, 80, silent=auto_mode)
    return True


# ===========================================================================
# STAGE 4: Loading Opsi 3 (v2 extended to 3.0s)
# ===========================================================================

def run_preflight_and_loading(mode_label: str, auto: bool = False) -> None:
    """
    Satcom/Proxy Hop Trace + 3.0s Orbital Calibration Bar (30 steps * 0.10s = 3.0s)
    with rising signal strength bars (▂▄▆█).
    """
    print()
    print(hud_tag_row("ORBITAL_PREFLIGHT", f"MODE::{mode_label}", C_CYAN))
    print(v2_box_top(C_CYAN, "SATCOM & PROXY HOP TRACE"))

    hops = [
        ("GND-01", "127.0.0.1:9050", "Ground SIGINT Console", "0.4ms"),
        ("LEO-09", "10.90.42.9", "Low-Orbit Ku-Relay", "18.6ms"),
        ("GEO-04", "172.16.204.4", "Geostationary Crosslink", "142.3ms"),
        ("TARGET", "198.51.100.77", "Orbital Vault Gateway", "164.8ms"),
    ]
    trace = (
        f"{C_GREEN}GND-01{C_RST} {C_DIM}->{C_RST} "
        f"{C_CYAN}LEO-09{C_RST} {C_DIM}->{C_RST} "
        f"{C_MAG}GEO-04{C_RST} {C_DIM}->{C_RST} "
        f"{C_RED}TARGET{C_RST}"
    )
    print(v2_box_row(trace, C_CYAN, align="center"))
    print(v2_box_sep(C_CYAN, "TRANSPONDER HOP LATENCY"))
    for name, ip, desc, rtt in hops:
        row = f"  {C_CYAN}{name:<9}{C_RST} {C_DIM}│{C_RST} {C_WHITE}{ip:<15}{C_RST} {C_DIM}│{C_RST} {desc:<23} {C_DIM}│{C_RST} {C_GREEN}{rtt:>7}{C_RST}"
        print(v2_box_row(row, C_CYAN))
    print(v2_box_bottom(C_CYAN))
    print()

    steps = 30
    interval = 0.10  # 30 * 0.10s = 3.0s
    for step in range(steps + 1):
        ratio = step / steps
        pct = int(ratio * 100)
        spin = BRAILLE_FRAMES[step % len(BRAILLE_FRAMES)]
        bar = v2_progress_bar(ratio, width=28, fill_color=C_CYAN if step < steps else C_GREEN)
        sig = signal_meter(ratio)
        snr = 11.2 + (14.8 * ratio)
        sys.stdout.write(
            f"\r  {C_CYAN}[{spin}] ORBITAL CALIBRATION{C_RST} [{bar}] {C_YEL}{pct:>3}%{C_RST} {sig} {C_DIM}{snr:4.1f}dB{C_RST}"
        )
        sys.stdout.flush()
        if step < steps:
            time.sleep(interval)
    print(f"\n  {C_GREEN}[✓] TRANSPONDER CARRIER LOCKED :: BEAMING SATCOM PACKETS{C_RST}\n")
    beep(1100, 60, silent=auto)


# ===========================================================================
# STAGE 5: Proses Kirim Email (v3) — Satcom Radar Telemetry & AAR
# ===========================================================================

SATCOM_CALLSIGNS = [
    "LEO-09.KESTREL.01",
    "GEO-04.ALBATROSS",
    "MEO-12.FALCON.03",
    "LEO-07.OSPREY.04",
    "GND-SG.SENTINEL",
    "LEO-11.HARRIER.06",
    "GEO-02.CONDOR.07",
    "MEO-08.MERLIN.08",
    "LEO-09.PEREGRINE",
    "GEO-04.VALKYRIE",
    "LEO-14.TALON.11",
    "GND-EU.HORIZON.12",
]


def run_live_telemetry(op_label: str, total_packets: int, target_scale: int) -> tuple[float, float]:
    """Stream fixed-column dummy radar telemetry lines with satcom node callsigns."""
    print(v3_box_top(C_GRAY))
    print(
        v3_box_row(
            f"{C_RED}[LIVE SATCOM]{C_RESET} {C_WHITE}{op_label}{C_RESET}  {C_GRAY}//  ORBITAL TELEMETRY ({target_scale}x){C_RESET}",
            C_GRAY,
            align="center",
        )
    )
    print(v3_box_bottom(C_GRAY))

    start_ts = time.perf_counter()
    base_id = 94108
    for idx in range(1, total_packets + 1):
        ts = now_hms()
        callsign = SATCOM_CALLSIGNS[(idx - 1) % len(SATCOM_CALLSIGNS)]
        pkt_id = base_id + (idx - 1) * 11
        status_tag = "[BEAM-ACK]"
        line = (
            f"  {C_GRAY}[{C_WHITE}{idx:03d}/{total_packets:03d}{C_GRAY}]{C_RESET} "
            f"{C_GRAY}[{C_TEXT}{ts}{C_GRAY}]{C_RESET} "
            f"{C_GRAY}[{C_WHITE}{callsign:<20}{C_GRAY}]{C_RESET} "
            f"{C_GRAY}[{C_AMBER}TX:{pkt_id:05d}{C_GRAY}]{C_RESET} "
            f"{C_AMBER}{status_tag}{C_RESET}"
        )
        print(line)
        time.sleep(0.11)

    duration = max(time.perf_counter() - start_ts, 0.01)
    velocity = total_packets / duration
    print()
    return velocity, duration


def render_aar_summary(
    op_label: str,
    packets: int,
    target_scale: int,
    velocity: float,
    duration: float,
    auto: bool = False,
) -> None:
    """Render the tactical AFTER-ACTION REPORT (AAR) mission summary box."""
    print(v3_box_top(C_AMBER))
    print(v3_box_row(f"{C_AMBER}AFTER-ACTION REPORT (AAR){C_RESET}  {C_GRAY}//  {C_WHITE}{op_label}{C_RESET}", C_AMBER, align="center"))
    print(v3_box_sep(C_AMBER))
    print(v3_box_row(f"  {C_GRAY}MISSION STATUS :{C_RESET} {C_AMBER}ORBITAL OBJECTIVE SECURED{C_RESET}", C_AMBER))
    print(v3_box_row(f"  {C_GRAY}OPERATOR       :{C_RESET} {C_WHITE}ADE7ASLI{C_RESET}  {C_GRAY}(CLEARANCE: SIGINT-5){C_RESET}", C_AMBER))
    print(v3_box_row(f"  {C_GRAY}CONSTELLATION  :{C_RESET} {C_WHITE}LEO-09 // GEO-04{C_RESET}  {C_GRAY}(CARRIER: -61 dBm){C_RESET}", C_AMBER))
    print(v3_box_row(f"  {C_GRAY}PACKETS BEAMED :{C_RESET} {C_WHITE}{packets:03d}/{packets:03d}{C_RESET}  {C_GRAY}(SIMULATED SCALE: {target_scale}x){C_RESET}", C_AMBER))
    print(v3_box_row(f"  {C_GRAY}UPLINK RATE    :{C_RESET} {C_AMBER}{velocity:.2f} pkt/s{C_RESET}", C_AMBER))
    print(v3_box_row(f"  {C_GRAY}DURATION       :{C_RESET} {C_WHITE}{duration:.2f} s{C_RESET}", C_AMBER))
    print(v3_box_bottom(C_AMBER))
    print()
    beep(960, 120, silent=auto)


def execute_operation(choice: str, state: dict[str, int | str], auto_mode: bool = False) -> bool:
    """Dispatch selected orbital operation. Returns False if operator exits."""
    if choice == "0":
        print(f"\n {CYAN}[*] Orbital uplink terminated. Goodbye Ade7asli.{RESET}\n")
        beep(420, 100, silent=auto_mode)
        return False

    if choice == "1":
        run_preflight_and_loading("10x_LEO_BURST", auto=auto_mode)
        vel, dur = run_live_telemetry("OP-10 // LEO MICRO-BURST", total_packets=6, target_scale=10)
        render_aar_summary("OP-10 // LEO MICRO-BURST", 6, 10, vel, dur, auto=auto_mode)
        state["total_votes_sent"] = int(state["total_votes_sent"]) + 10
        state["next_index"] = min(int(state["total_emails"]), int(state["next_index"]) + 1)
        return True

    if choice == "2":
        run_preflight_and_loading("100x_SATCOM_STORM", auto=auto_mode)
        vel, dur = run_live_telemetry("OP-100 // SATCOM SWEEP", total_packets=8, target_scale=100)
        render_aar_summary("OP-100 // SATCOM SWEEP", 8, 100, vel, dur, auto=auto_mode)
        state["total_votes_sent"] = int(state["total_votes_sent"]) + 100
        state["next_index"] = min(int(state["total_emails"]), int(state["next_index"]) + 10)
        return True

    if choice == "3":
        run_satellite_lock_on(auto=auto_mode)
        if not verify_1000x_matrix(auto_mode=auto_mode):
            return True
        run_preflight_and_loading("1000x_ORBITAL_SALVO", auto=auto_mode)
        vel, dur = run_live_telemetry("OP-1000 // LEO-09 SIGINT SALVO", total_packets=12, target_scale=1000)
        render_aar_summary("OP-1000 // LEO-09 SIGINT SALVO", 12, 1000, vel, dur, auto=auto_mode)
        state["total_votes_sent"] = int(state["total_votes_sent"]) + 1000
        state["next_index"] = min(int(state["total_emails"]), int(state["next_index"]) + 100)
        return True

    print(f"\n {RED}[!] Pilihan tidak valid. Ketik 1, 2, 3, atau 0.{RESET}\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="demo_evo_4_orbital — 5-Stage ORBITAL_UPLINK // SATCOM SIGINT Simulation"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Run Boot (v2) -> Menu (basic) -> Option 3 -> Lock-On -> 4-step auth (basic) -> 3.0s Loading (v2) -> Telemetry & AAR (v3) -> Exit",
    )
    args = parser.parse_args()

    state: dict[str, int | str] = {
        "next_index": 180,
        "total_emails": 2000,
        "total_votes_sent": 1793,
        "next_email": "satcom.node@orbital.test",
    }

    # Stage 1: Intro (v2)
    run_boot_sequence(auto=args.auto)

    if args.auto:
        # Stage 2: Tampilan Awal (basic)
        render_basic_dashboard(state)
        print(f" {BOLD}{GREEN}root@Ade7asli:~#{RESET} pilih [1/2/3/0]: {YELLOW}3{RESET} {DIM}[AUTO-SELECT]{RESET}")
        time.sleep(0.3)
        # Stage 3 (Lock-On + Matrix) -> Stage 4 (3.0s Loading) -> Stage 5 (Telemetry & AAR)
        execute_operation("3", state, auto_mode=True)
        print(f"  {C_GRAY}[AUTO-EXIT]{C_RESET} {C_WHITE}5-stage orbital simulation complete. Terminating session.{C_RESET}")
        return 0

    while True:
        render_basic_dashboard(state)
        try:
            choice = input(f" {BOLD}{GREEN}root@Ade7asli:~#{RESET} pilih [1/2/3/0]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n {CYAN}[*] Orbital uplink terminated. Goodbye Ade7asli.{RESET}\n")
            return 0

        if not execute_operation(choice, state, auto_mode=False):
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
