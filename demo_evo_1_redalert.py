#!/usr/bin/env python3
"""
demo_evo_1_redalert.py — RED_ALERT // DEFCON-1 BREACH (5-Stage Evolution)
100% standalone dummy/mock simulation (NO real file reads, NO HTTP requests, UI_WIDTH = 80).
Structure: v2 intro + basic menu + basic option 3 (entry anim + 2x2 matrix) + v2 3.0s loading + v3 telemetry & AAR.
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

# v2 RED_ALERT // DEFCON-1 palette
C_CYAN = Fore.LIGHTCYAN_EX + Style.BRIGHT
C_MAG = Fore.LIGHTMAGENTA_EX + Style.BRIGHT
C_GREEN = Fore.LIGHTGREEN_EX + Style.BRIGHT
C_YEL = Fore.LIGHTYELLOW_EX + Style.BRIGHT
C_RED = Fore.LIGHTRED_EX + Style.BRIGHT
C_CRIMSON = Fore.RED + Style.BRIGHT
C_DIM = Fore.LIGHTBLACK_EX
C_WHITE = Fore.WHITE + Style.BRIGHT
C_RST = Style.RESET_ALL

# basic palette
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"
DIM = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"

# v3 Red-Amber Telemetry & AAR palette
C_TEXT = Fore.WHITE
C_GRAY = Fore.LIGHTBLACK_EX
C_AMBER = Style.BRIGHT + Fore.YELLOW
C_ALERT = Style.BRIGHT + Fore.LIGHTRED_EX
C_RESET = Style.RESET_ALL

BRAILLE_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
GLITCH_CHARS = "!@#$%^&*░▒▓█<>/\\[]{}01DEFCON"


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

def v2_box_top(border_color: str = C_RED, tag: str = "") -> str:
    if tag:
        label = f"═[{tag}]"
        rem = max(0, INNER_WIDTH - len(label))
        return f"{border_color}╔{label}{'═' * rem}╗{C_RST}"
    return f"{border_color}╔{'═' * INNER_WIDTH}╗{C_RST}"


def v2_box_sep(border_color: str = C_RED, tag: str = "") -> str:
    if tag:
        label = f"═[{tag}]"
        rem = max(0, INNER_WIDTH - len(label))
        return f"{border_color}╠{label}{'═' * rem}╣{C_RST}"
    return f"{border_color}╠{'═' * INNER_WIDTH}╣{C_RST}"


def v2_box_bottom(border_color: str = C_RED) -> str:
    return f"{border_color}╚{'═' * INNER_WIDTH}╝{C_RST}"


def v2_box_row(
    content: str,
    border_color: str = C_RED,
    align: str = "left",
    pad_x: int = 1,
) -> str:
    inner_w = INNER_WIDTH - (pad_x * 2)
    padded = pad_line(content, inner_w, align=align)
    spaces = " " * pad_x
    return f"{border_color}║{C_RST}{spaces}{padded}{spaces}{border_color}║{C_RST}"


def hud_tag_row(left_tag: str, right_tag: str, color: str = C_RED) -> str:
    left = f"┌─[{left_tag}]─┐"
    right = f"┌─[{right_tag}]─┐"
    gap = max(1, UI_WIDTH - len(left) - len(right))
    return f"{color}{left}{'─' * gap}{right}{C_RST}"


def v2_progress_bar(ratio: float, width: int = 30, fill_color: str = C_RED) -> str:
    clamped = max(0.0, min(1.0, ratio))
    filled = int(round(clamped * width))
    empty = width - filled
    return f"{fill_color}{'█' * filled}{C_DIM}{'░' * empty}{C_RST}"


def basic_box_top(width: int = UI_WIDTH, color: str = RED) -> str:
    return f"{color}╔{'═' * (width - 2)}╗{RESET}"


def basic_box_sep(width: int = UI_WIDTH, color: str = RED) -> str:
    return f"{color}╠{'═' * (width - 2)}╣{RESET}"


def basic_box_bottom(width: int = UI_WIDTH, color: str = RED) -> str:
    return f"{color}╚{'═' * (width - 2)}╝{RESET}"


def basic_box_line(text: str = "", width: int = UI_WIDTH, color: str = RED, align: str = "left") -> str:
    inner_width = width - 4
    vis_len = visible_len(text)
    if vis_len > inner_width:
        plain = strip_ansi(text)
        content = plain[: inner_width - 3] + "..."
    else:
        content = center_text(text, inner_width) if align == "center" else pad_right(text, inner_width)
    return f"{color}║{RESET} {content} {color}║{RESET}"


def basic_progress_bar(current: int, total: int, bar_width: int = 30, fill_color: str = YELLOW) -> str:
    pct = (current / total * 100.0) if total > 0 else 0.0
    filled = int(round(bar_width * current / total)) if total > 0 else 0
    filled = max(0, min(bar_width, filled))
    bar = f"{fill_color}{'█' * filled}{DIM}{'░' * (bar_width - filled)}{RESET}"
    return f"[{bar}] {BOLD}{pct:5.1f}%{RESET}"


def v3_box_top(border_color: str = C_ALERT) -> str:
    return f"{border_color}╔{'═' * (UI_WIDTH - 2)}╗{C_RESET}"


def v3_box_sep(border_color: str = C_ALERT) -> str:
    return f"{border_color}╠{'═' * (UI_WIDTH - 2)}╣{C_RESET}"


def v3_box_bottom(border_color: str = C_ALERT) -> str:
    return f"{border_color}╚{'═' * (UI_WIDTH - 2)}╝{C_RESET}"


def v3_box_row(content: str = "", border_color: str = C_ALERT, align: str = "left") -> str:
    inner = pad_line(content, UI_WIDTH - 4, align=align)
    return f"{border_color}║{C_RESET} {inner} {border_color}║{C_RESET}"


# ===========================================================================
# STAGE 1: Intro (v2) — RED_ALERT // DEFCON-1 BREACH Boot Sequence
# ===========================================================================

def run_boot_sequence(auto: bool = False) -> None:
    """Simulate DEFCON-1 breach initialization, perimeter override, and cipher unlock."""
    clear_screen()
    print(hud_tag_row("RED_ALERT v4.1", "DEFCON-1::BREACH", C_RED))
    print(v2_box_top(C_RED, "HUD::DEFCON_1_BREACH"))
    print(
        v2_box_row(
            f"{C_RED}RED_ALERT KERNEL{C_RST} {C_DIM}//{C_RST} {C_YEL}DEFCON-1 BREACH PROTOCOL ACTIVE{C_RST}",
            C_RED,
            align="center",
        )
    )
    print(v2_box_bottom(C_RED))

    steps = [
        ("SIREN_BUS", "Engaging DEFCON-1 tactical override bus", C_RED),
        ("ICE_BREACH", "Fracturing sentinel perimeter firewalls", C_YEL),
        ("SEAL_KEY", "Injecting crimson root-cipher [0xD1::ADE]", C_CRIMSON),
        ("GHOST_LINK", "Tunneling dark-relay uplink :: NO TRACE", C_GREEN),
    ]
    for code, msg, col in steps:
        for i in range(4):
            spinner = BRAILLE_FRAMES[i % len(BRAILLE_FRAMES)]
            sys.stdout.write(f"\r  {col}[{spinner}] {code:<12}{C_RST} │ {msg}...")
            sys.stdout.flush()
            time.sleep(0.05 if auto else 0.08)
        sys.stdout.write(f"\r  {C_YEL}[✓] {code:<12}{C_RST} │ {msg} {C_RED}[ARMED]{C_RST}\n")
        sys.stdout.flush()
        beep(660, 35, silent=auto)

    target = "DEFCON-1 BREACH READY :: ADE7ASLI"
    print()
    for step in range(12):
        reveal = int((step + 1) / 12 * len(target))
        scrambled = "".join(
            target[idx] if idx < reveal else random.choice(GLITCH_CHARS)
            for idx in range(len(target))
        )
        color = C_RED if step == 11 else (C_YEL if step % 2 == 0 else C_CRIMSON)
        sys.stdout.write(f"\r  {C_RED}>> BREACH:{C_RST} {color}{scrambled}{C_RST}")
        sys.stdout.flush()
        time.sleep(0.04 if auto else 0.06)
    print("\n")
    beep(980, 75, silent=auto)
    time.sleep(0.20 if auto else 0.40)


# ===========================================================================
# STAGE 2: Tampilan Awal (basic) — RED_ALERT // DEFCON-1 Command Menu
# ===========================================================================

def print_welcome_banner() -> None:
    """Display WELCOME + ADE7ASLI ASCII Art inside an 80-col basic RED_ALERT frame."""
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
    print(basic_box_top(UI_WIDTH, RED))
    for line in welcome_art:
        print(basic_box_line(f"{BOLD}{RED}{line}{RESET}", UI_WIDTH, RED, align="center"))
    for line in ade_art:
        print(basic_box_line(f"{BOLD}{YELLOW}{line}{RESET}", UI_WIDTH, RED, align="center"))
    print(
        basic_box_line(
            f"{BOLD}{RED}<< RED_ALERT // DEFCON-1 BREACH COMMAND CENTER >>{RESET}",
            UI_WIDTH,
            RED,
            align="center",
        )
    )


def render_basic_dashboard(state: dict[str, int | str]) -> None:
    """Render the 80-col RED_ALERT basic dashboard with dummy stats."""
    next_idx = int(state["next_index"])
    total_emails = int(state["total_emails"])
    total_votes = int(state["total_votes_sent"])
    remaining = max(0, total_emails - next_idx)
    target_email = str(state["next_email"])

    print()
    print_welcome_banner()
    print(basic_box_sep(UI_WIDTH, RED))
    prog_bar = basic_progress_bar(next_idx, total_emails, bar_width=30, fill_color=YELLOW)
    print(basic_box_line(f" {DIM}QUEUE PROGRESS :{RESET} {prog_bar}  ({YELLOW}{next_idx}/{total_emails}{RESET})", UI_WIDTH, RED))
    print(basic_box_line(f" {DIM}TOTAL SENT     :{RESET} {BOLD}{GREEN}{total_votes} votes{RESET}   {DIM}│  REMAINING :{RESET} {BOLD}{YELLOW}{remaining} emails{RESET}", UI_WIDTH, RED))
    if next_idx < total_emails:
        print(basic_box_line(f" {DIM}NEXT TARGET    :{RESET} {WHITE}Baris {next_idx + 2}{RESET} -> {RED}{target_email}{RESET}", UI_WIDTH, RED))
    else:
        print(basic_box_line(f" {DIM}NEXT TARGET    :{RESET} {BOLD}{YELLOW}ALL EMAILS EXHAUSTED (HABIS){RESET}", UI_WIDTH, RED))

    print(basic_box_sep(UI_WIDTH, RED))
    print(basic_box_line(f" {BOLD}{WHITE}SELECT EXECUTION VECTOR:{RESET}", UI_WIDTH, RED))
    print(basic_box_line(f"  {BOLD}{GREEN}[1]{RESET} {WHITE}10x   SURVEY BURST{RESET}  {DIM}│{RESET} {CYAN}10 threads{RESET}  {DIM}│{RESET}  1 base email  (10 votes)", UI_WIDTH, RED))
    print(basic_box_line(f"  {BOLD}{YELLOW}[2]{RESET} {WHITE}100x  SURVEY STORM{RESET}  {DIM}│{RESET} {YELLOW}10 threads{RESET}  {DIM}│{RESET} 10 base emails (100 votes)", UI_WIDTH, RED))
    print(basic_box_line(f"  {BOLD}{RED}[3]{RESET} {YELLOW}1000x OVERDRIVE{RESET}     {DIM}│{RESET} {RED}25 threads{RESET}  {DIM}│{RESET} 100 base emails {RED}[DEFCON-1 SEAL]{RESET}", UI_WIDTH, RED))
    print(basic_box_line(f"  {DIM}[0] EXIT TERMINAL{RESET}", UI_WIDTH, RED))
    print(basic_box_bottom(UI_WIDTH, RED))


# ===========================================================================
# STAGE 3: Option 3 Entry Animation (~1.0-1.2s) + 2x2 Matrix (basic)
# ===========================================================================

def play_option3_entry_animation(auto_mode: bool = False) -> None:
    """
    ~1.1s Option 3 entry warning animation before the 2x2 matrix appears:
    - Red warning flash banner: [!!] CLASS-5 OVERDRIVE DETECTED [!!]
    - CRACKING LAUNCH SEAL... animation with optional winsound.Beep
    """
    banner_text = "[!!] CLASS-5 OVERDRIVE DETECTED [!!]"
    print()
    # 4 rapid flash frames * 0.12s = 0.48s
    for idx in range(4):
        if idx % 2 == 0:
            line = f"{BOLD}{RED}{banner_text}{RESET}"
            beep(880, 40, silent=auto_mode)
        else:
            line = f"{BOLD}{YELLOW}{banner_text}{RESET}"
            beep(620, 40, silent=auto_mode)
        sys.stdout.write(f"\r{center_text(line, UI_WIDTH)}")
        sys.stdout.flush()
        time.sleep(0.12)
    print()

    # CRACKING LAUNCH SEAL... animation: 12 steps * 0.055s = 0.66s (total ~1.14s)
    seal_steps = 12
    seal_width = 24
    for step in range(1, seal_steps + 1):
        spin = BRAILLE_FRAMES[step % len(BRAILLE_FRAMES)]
        filled = int(round(seal_width * step / seal_steps))
        bar = f"{RED}{'█' * filled}{DIM}{'░' * (seal_width - filled)}{RESET}"
        pct = int(step * 100 / seal_steps)
        status = f"{BOLD}{YELLOW}SEAL BREACHED{RESET}" if step == seal_steps else f"{RED}CRACKING...{RESET}"
        sys.stdout.write(
            f"\r  {BOLD}{RED}[{spin}] CRACKING LAUNCH SEAL...{RESET} [{bar}] {BOLD}{YELLOW}{pct:3d}%{RESET} {status}"
        )
        sys.stdout.flush()
        time.sleep(0.055)
    print()
    beep(1046, 70, silent=auto_mode)


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
        return f"{YELLOW}{name:<4}{RESET} {DIM}({desc:<13}){RESET} : {state}"

    def verify_loading(mod_name: str) -> None:
        """1.5s loading animation with decryption scramble."""
        tech_msg = {
            "CORE": "Verifying DEFCON-1 kernel & thread pool...",
            "NET": "Handshake TLS & dark-relay socket sync...",
            "AUTH": "Decrypting Ade7asli crimson root key...",
            "EXEC": "Arming 1000x overdrive launch vector...",
        }.get(mod_name, f"Validating {mod_name}...")
        print(f" {YELLOW}[*]{RESET} {tech_msg}")
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
            color = GREEN if step == 10 else RED
            sys.stdout.write(f"\r {color}[{bar}] {pct:3d}% // DECRYPT: {scrambled}{RESET}")
            sys.stdout.flush()
            time.sleep(0.15)  # 10 * 0.15s = 1.5s
        print()

    auto_step = 0
    while not all(modules.values()):
        print()
        print(basic_box_top(UI_WIDTH, RED))
        print(
            basic_box_line(
                f"{BOLD}{RED}[!] DEFCON-1 1000X MATRIX :: ROOT AUTHORIZATION REQUIRED{RESET}",
                UI_WIDTH,
                RED,
                align="center",
            )
        )
        print(basic_box_sep(UI_WIDTH, RED))
        row1 = f" {fmt_status('CORE', 'Thread Pool', modules['CORE'])}   │   {fmt_status('NET', 'TLS Socket', modules['NET'])}"
        row2 = f" {fmt_status('AUTH', 'Root Key', modules['AUTH'])}   │   {fmt_status('EXEC', '1000x Bus', modules['EXEC'])}"
        print(basic_box_line(row1, UI_WIDTH, RED))
        print(basic_box_line(row2, UI_WIDTH, RED))
        print(basic_box_bottom(UI_WIDTH, RED))

        prompt = f" {BOLD}{RED}root@Ade7asli:~#{RESET} "
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
                print(f" {YELLOW}[*] MODULE {mod_name} -> ALREADY READY{RESET}")
        else:
            print(f" {RED}[-] ACCESS DENIED // INVALID ROOT COMMAND{RESET}")
            beep(240, 100, silent=auto_mode)

    print()
    print(basic_box_top(UI_WIDTH, YELLOW))
    print(
        basic_box_line(
            f"{BOLD}{GREEN}[+] ALL SYSTEMS ARMED & READY // LAUNCHING DEFCON-1 PAYLOAD{RESET}",
            UI_WIDTH,
            YELLOW,
            align="center",
        )
    )
    print(basic_box_sep(UI_WIDTH, YELLOW))
    print(basic_box_line(f" {fmt_status('CORE', 'Thread Pool', True)}   │   {fmt_status('NET', 'TLS Socket', True)}", UI_WIDTH, YELLOW))
    print(basic_box_line(f" {fmt_status('AUTH', 'Root Key', True)}   │   {fmt_status('EXEC', '1000x Bus', True)}", UI_WIDTH, YELLOW))
    print(basic_box_bottom(UI_WIDTH, YELLOW))
    beep(1100, 80, silent=auto_mode)
    return True


# ===========================================================================
# STAGE 4: Loading Opsi 3 (v2 extended to 3.0s) — Proxy Trace + Dual-Stage Bar
# ===========================================================================

def run_preflight_and_loading(mode_label: str, auto: bool = False) -> None:
    """
    Display Proxy Hop Trace (127.0.0.1 -> SG-RELAY -> EU-NODE -> TARGET)
    + Dual-Stage 3.0s Arming Bar (30 steps * 0.10s = 3.0s):
      - 0-50%  : TUNNEL ENCRYPTION
      - 50-100%: PAYLOAD OVERCLOCK
    with Braille spinner.
    """
    print()
    print(hud_tag_row("PRE-FLIGHT", f"MODE::{mode_label}", C_RED))
    print(v2_box_top(C_RED, "ROUTING & PROXY HOP TRACE"))

    hops = [
        ("LOCAL", "127.0.0.1:9050", "Red-Alert Deck Origin", "0.4ms"),
        ("SG-RELAY", "103.21.244.8", "Singapore Dark-Fiber", "14.2ms"),
        ("EU-NODE", "185.220.101.4", "Zurich Onion Exit", "38.7ms"),
        ("TARGET", "198.51.100.77", "Survey Vault Gateway", "51.9ms"),
    ]
    trace = (
        f"{C_YEL}127.0.0.1{C_RST} {C_DIM}->{C_RST} "
        f"{C_CYAN}SG-RELAY{C_RST} {C_DIM}->{C_RST} "
        f"{C_MAG}EU-NODE{C_RST} {C_DIM}->{C_RST} "
        f"{C_RED}TARGET{C_RST}"
    )
    print(v2_box_row(trace, C_RED, align="center"))
    print(v2_box_sep(C_RED, "HOP LATENCY"))
    for name, ip, desc, rtt in hops:
        row = f"  {C_YEL}{name:<9}{C_RST} {C_DIM}│{C_RST} {C_WHITE}{ip:<15}{C_RST} {C_DIM}│{C_RST} {desc:<23} {C_DIM}│{C_RST} {C_GREEN}{rtt:>6}{C_RST}"
        print(v2_box_row(row, C_RED))
    print(v2_box_bottom(C_RED))
    print()

    # Dual-Stage 3.0s Arming Bar: 30 steps * 0.10s = 3.0s
    steps = 30
    interval = 0.10
    for step in range(1, steps + 1):
        ratio = step / steps
        pct = int(round(ratio * 100))
        spin = BRAILLE_FRAMES[step % len(BRAILLE_FRAMES)]
        if pct <= 50:
            stage_label = "TUNNEL ENCRYPTION"
            stage_col = C_YEL
            fill_col = C_YEL
        else:
            stage_label = "PAYLOAD OVERCLOCK"
            stage_col = C_RED if step < steps else C_GREEN
            fill_col = C_RED if step < steps else C_GREEN

        bar = v2_progress_bar(ratio, width=30, fill_color=fill_col)
        line = f"  {stage_col}[{spin}] {stage_label:<18}{C_RST} [{bar}] {C_YEL}{pct:>3}%{C_RST}"
        sys.stdout.write(f"\r{pad_right(line, UI_WIDTH)}")
        sys.stdout.flush()
        time.sleep(interval)

    print(f"\n  {C_GREEN}[✓] DEFCON-1 TUNNEL LOCKED :: STREAMING BREACH PACKETS{C_RST}\n")
    beep(1120, 65, silent=auto)


# ===========================================================================
# STAGE 5: Proses Kirim Email (v3) — Red-Amber Radar Telemetry & AAR
# ===========================================================================

def run_live_telemetry(op_label: str, total_packets: int, target_scale: int) -> tuple[float, float]:
    """Stream fixed-column dummy radar telemetry lines with red-amber accents."""
    print(v3_box_top(C_ALERT))
    print(
        v3_box_row(
            f"{C_ALERT}[LIVE STREAM]{C_RESET} {C_WHITE}{op_label}{C_RESET}  {C_GRAY}//  DEFCON-1 TELEMETRY ({target_scale}x){C_RESET}",
            C_ALERT,
            align="center",
        )
    )
    print(v3_box_bottom(C_ALERT))

    start_ts = time.perf_counter()
    base_id = 91042
    for idx in range(1, total_packets + 1):
        ts = now_hms()
        node = f"breach.node{idx:02d}@example.test"
        pkt_id = base_id + (idx - 1) * 9
        status_tag = "[BREACHED]" if idx % 3 == 0 else "[CONFIRMED]"
        status_col = C_ALERT if idx % 3 == 0 else C_AMBER
        line = (
            f"  {C_GRAY}[{C_ALERT}{idx:03d}/{total_packets:03d}{C_GRAY}]{C_RESET} "
            f"{C_GRAY}[{C_TEXT}{ts}{C_GRAY}]{C_RESET} "
            f"{C_GRAY}[{C_WHITE}{node:<26}{C_GRAY}]{C_RESET} "
            f"{C_GRAY}[{C_AMBER}ID:{pkt_id:05d}{C_GRAY}]{C_RESET} "
            f"{status_col}{status_tag}{C_RESET}"
        )
        print(line)
        time.sleep(0.10)

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
    """Render the AFTER-ACTION REPORT (AAR) mission summary box with red-amber accents."""
    print(v3_box_top(C_ALERT))
    print(
        v3_box_row(
            f"{C_ALERT}AFTER-ACTION REPORT (AAR){C_RESET}  {C_GRAY}//  {C_AMBER}{op_label}{C_RESET}",
            C_ALERT,
            align="center",
        )
    )
    print(v3_box_sep(C_ALERT))
    print(v3_box_row(f"  {C_GRAY}THREAT LEVEL   :{C_RESET} {C_ALERT}DEFCON-1 // RED_ALERT BREACH{C_RESET}", C_ALERT))
    print(v3_box_row(f"  {C_GRAY}MISSION STATUS :{C_RESET} {C_AMBER}OBJECTIVE SECURED{C_RESET}", C_ALERT))
    print(v3_box_row(f"  {C_GRAY}OPERATOR       :{C_RESET} {C_WHITE}ADE7ASLI{C_RESET}  {C_GRAY}(CLEARANCE: LEVEL-5){C_RESET}", C_ALERT))
    print(v3_box_row(f"  {C_GRAY}PACKETS LOGGED :{C_RESET} {C_WHITE}{packets:03d}/{packets:03d}{C_RESET}  {C_GRAY}(SIMULATED SCALE: {target_scale}x){C_RESET}", C_ALERT))
    print(v3_box_row(f"  {C_GRAY}VELOCITY       :{C_RESET} {C_AMBER}{velocity:.2f} pkt/s{C_RESET}", C_ALERT))
    print(v3_box_row(f"  {C_GRAY}DURATION       :{C_RESET} {C_WHITE}{duration:.2f} s{C_RESET}", C_ALERT))
    print(v3_box_bottom(C_ALERT))
    print()
    beep(960, 120, silent=auto)


def execute_operation(choice: str, state: dict[str, int | str], auto_mode: bool = False) -> bool:
    """Dispatch selected operation. Returns False if operator exits."""
    if choice == "0":
        print(f"\n {RED}[*] DEFCON-1 terminal closed. Goodbye Ade7asli.{RESET}\n")
        beep(420, 100, silent=auto_mode)
        return False

    if choice == "1":
        run_preflight_and_loading("10x_BURST", auto=auto_mode)
        vel, dur = run_live_telemetry("OP-10 // MICRO-BURST", total_packets=6, target_scale=10)
        render_aar_summary("OP-10 // MICRO-BURST", 6, 10, vel, dur, auto=auto_mode)
        state["total_votes_sent"] = int(state["total_votes_sent"]) + 10
        state["next_index"] = min(int(state["total_emails"]), int(state["next_index"]) + 1)
        return True

    if choice == "2":
        run_preflight_and_loading("100x_STORM", auto=auto_mode)
        vel, dur = run_live_telemetry("OP-100 // MID-SWEEP", total_packets=8, target_scale=100)
        render_aar_summary("OP-100 // MID-SWEEP", 8, 100, vel, dur, auto=auto_mode)
        state["total_votes_sent"] = int(state["total_votes_sent"]) + 100
        state["next_index"] = min(int(state["total_emails"]), int(state["next_index"]) + 10)
        return True

    if choice == "3":
        play_option3_entry_animation(auto_mode=auto_mode)
        if not verify_1000x_matrix(auto_mode=auto_mode):
            return True
        run_preflight_and_loading("1000x_OVERDRIVE", auto=auto_mode)
        vel, dur = run_live_telemetry("OP-1000 // DEFCON-1 BREACH", total_packets=12, target_scale=1000)
        render_aar_summary("OP-1000 // DEFCON-1 BREACH", 12, 1000, vel, dur, auto=auto_mode)
        state["total_votes_sent"] = int(state["total_votes_sent"]) + 1000
        state["next_index"] = min(int(state["total_emails"]), int(state["next_index"]) + 100)
        return True

    print(f"\n {RED}[!] Pilihan tidak valid. Ketik 1, 2, 3, atau 0.{RESET}\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="demo_evo_1_redalert — RED_ALERT // DEFCON-1 BREACH (5-Stage Evolution)"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Run end-to-end non-interactively (Boot -> Menu -> Option 3 -> Entry Anim -> 2x2 Matrix -> 3.0s Loading -> Telemetry & AAR -> Exit)",
    )
    args = parser.parse_args()

    state: dict[str, int | str] = {
        "next_index": 180,
        "total_emails": 2000,
        "total_votes_sent": 1793,
        "next_email": "demo.target@example.test",
    }

    # Stage 1: Intro (v2)
    run_boot_sequence(auto=args.auto)

    if args.auto:
        # Stage 2: Tampilan Awal (basic)
        render_basic_dashboard(state)
        print(f" {BOLD}{RED}root@Ade7asli:~#{RESET} pilih [1/2/3/0]: {YELLOW}3{RESET} {DIM}[AUTO-SELECT]{RESET}")
        time.sleep(0.3)
        # Stage 3 -> Stage 4 -> Stage 5
        execute_operation("3", state, auto_mode=True)
        print(f"  {C_GRAY}[AUTO-EXIT]{C_RESET} {C_WHITE}RED_ALERT // DEFCON-1 simulation complete. Terminating session.{C_RESET}")
        return 0

    while True:
        render_basic_dashboard(state)
        try:
            choice = input(f" {BOLD}{RED}root@Ade7asli:~#{RESET} pilih [1/2/3/0]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n {RED}[*] DEFCON-1 terminal closed. Goodbye Ade7asli.{RESET}\n")
            return 0

        if not execute_operation(choice, state, auto_mode=False):
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
