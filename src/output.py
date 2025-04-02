import re
import io
import time
import colorama
from colorama import Fore, Style

COLORED_CONSOLE = True  # Dieser Wert wird in main.py überschrieben

def format_playtime(seconds):
    minutes = seconds // 60
    sec = seconds % 60
    return f"{minutes}m {sec}s" if seconds else "N/A"

def print_match_table(match_data_list, puuid, match_classification, colored=True):
    ranked_matches = [m for m in match_data_list if m["info"].get("queueId") == 420 and "metadata" in m]
    ranked_matches = sorted(ranked_matches, key=lambda m: m["info"].get("gameCreation", 0), reverse=True)
    rows = []
    for match in ranked_matches:
        match_id = match["metadata"].get("matchId", "UNKNOWN")
        ts = match["info"].get("gameCreation", 0) / 1000.0
        date_str = time.strftime("%Y-%m-%d", time.localtime(ts))
        participant = next((p for p in match["info"]["participants"] if p["puuid"] == puuid), None)
        result = "Win" if participant and participant.get("win", False) else "Lose"
        typ = match_classification.get(match_id, "N/A")
        my_team = next((p["teamId"] for p in match["info"]["participants"] if p["puuid"] == puuid), None)
        teammates = [
            p.get("summonerName") or p.get("puuid")
            for p in match["info"]["participants"]
            if p["teamId"] == my_team and p["puuid"] != puuid
        ]
        teammates_str = ", ".join(teammates)
        duration = match["info"].get("gameDuration", 0)
        playtime = format_playtime(duration)
        rows.append([match_id, date_str, result, typ, teammates_str, playtime])
    
    if not rows:
        print("\nNo ranked matches found.")
        return rows

    # Define column names and widths
    columns = ["GameID", "Date", "Result", "Type", "Teammates", "Playtime"]
    col_widths = [30, 10, 8, 25, 40, 10]

    # Helper function to pad or trim strings
    def pad_or_trim(s, width):
        s = str(s)
        if len(s) > width:
            return s[:width - 1] + "…"
        return s.ljust(width)

    # Unicode box-drawing characters for table
    top_left, top_right = "┌", "┐"
    bottom_left, bottom_right = "└", "┘"
    horizontal, vertical, sep = "─", "│", "┼"
    line_top = top_left + sep.join([horizontal * w for w in col_widths]) + top_right
    line_sep = "├" + sep.join([horizontal * w for w in col_widths]) + "┤"
    line_bottom = bottom_left + sep.join([horizontal * w for w in col_widths]) + bottom_right

    print("\nMatch Overview:")
    print(line_top)
    header_row = vertical + vertical.join([pad_or_trim(col, w) for col, w in zip(columns, col_widths)]) + vertical
    print(header_row)
    print(line_sep)
    for row in rows:
        game_id, date_str, result, qtype, mates, playt = row
        if colored:
            if result == "Win":
                result_str = Fore.GREEN + pad_or_trim(result, col_widths[2]) + Style.RESET_ALL
            else:
                result_str = Fore.RED + pad_or_trim(result, col_widths[2]) + Style.RESET_ALL
        else:
            result_str = pad_or_trim(result, col_widths[2])
        line_data = (vertical +
                     pad_or_trim(game_id, col_widths[0]) + vertical +
                     pad_or_trim(date_str, col_widths[1]) + vertical +
                     result_str + vertical +
                     pad_or_trim(qtype, col_widths[3]) + vertical +
                     pad_or_trim(mates, col_widths[4]) + vertical +
                     pad_or_trim(playt, col_widths[5]) + vertical)
        print(line_data)
    print(line_bottom)
    return rows

def remove_ansi_sequences(text):
    ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)

def print_ascii_menu(colored=True):
    ascii_menu = r"""
 __       _         ____      ___               ____     _               _                    
/ _\ ___ | | ___   /___ \    /   \_   _  ___   /___ \   /_\  _ __   __ _| |_   _ _______ _ __ 
\ \ / _ \| |/ _ \ //  / /   / /\ / | | |/ _ \ //  / /  //_\\| '_ \ / _` | | | | |_  / _ \ '__|
_\ \ (_) | | (_) / \_/ /   / /_//| |_| | (_) / \_/ /  /  _  \ | | | (_| | | |_| |/ /  __/ |   
\__/\___/|_|\___/\___,_\  /___,'  \__,_|\___/\___,_\  \_/ \_/_| |_|\__,_|_|\__, /___\___|_|   
                                                                           |___/              
"""
    if colored:
        print(colorama.Fore.MAGENTA + ascii_menu + colorama.Style.RESET_ALL)
    else:
        print(ascii_menu)
