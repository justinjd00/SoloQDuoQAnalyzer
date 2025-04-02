#!/usr/bin/env python3
import os
import sys
import re
import io
import logging
import configparser
from datetime import datetime
import pandas as pd
import colorama
from colorama import init, Fore, Style

from config import load_config, get_settings
from analyzer import RiotAnalyzer, analyze_champion_stats, analyze_lane_performance
from output import print_ascii_menu, print_match_table, remove_ansi_sequences

logger = logging.getLogger(__name__)

def analyze_queue_types(name, tag, api_key, games_to_analyze):
    print(Fore.CYAN + f"Analyzing up to {games_to_analyze} games for {name}#{tag}..." + Style.RESET_ALL)
    logger.info(f"Start analysis for {name}#{tag} with {games_to_analyze} games.")
    analyzer = RiotAnalyzer(api_key)
    account = analyzer.get_account_by_riot_id(name, tag)
    if not account:
        logger.error(f"Account not found for {name}#{tag}")
        print(Fore.RED + f"Could not find Riot account for {name}#{tag}." + Style.RESET_ALL)
        return None
    puuid = account["puuid"]
    game_name = account.get("gameName", name)
    display_name = f"{game_name}#{account.get('tagLine', tag)}"
    print(Fore.GREEN + f"Account found: {display_name} (PUUID: {puuid})" + Style.RESET_ALL)
    logger.info(f"Account found: {display_name} (PUUID: {puuid})")
    matches = analyzer.get_match_history(puuid, count=games_to_analyze)
    if not matches:
        logger.error("No matches found.")
        print(Fore.RED + "No matches found." + Style.RESET_ALL)
        return None
    print(Fore.GREEN + f"Found Matches: {len(matches)}" + Style.RESET_ALL)
    logger.info(f"Found Matches: {len(matches)}")
    print(Fore.YELLOW + "Processing match details (this may take a few minutes)..." + Style.RESET_ALL)
    results = analyzer.process_matches(matches, puuid)
    match_data_list = results["match_data_list"]
    match_classification = results.get("match_classification", {})

    champ_stats = analyze_champion_stats(match_data_list, puuid)
    lane_stats = analyze_lane_performance(match_data_list, puuid)

    print("\n" + Fore.CYAN + "===== ANALYSIS RESULTS =====" + Style.RESET_ALL)
    print(f"Player: {display_name}")
    print(f"Matches requested: {games_to_analyze}")
    print(f"Matches retrieved: {results['fetched_matches']}")
    print(f"Ranked Solo/Duo Matches (Queue 420): {results['total_ranked']}\n")

    print(Fore.CYAN + "Solo Queue:" + Style.RESET_ALL)
    print(f"  Games: {results['solo_queue']}")
    print(f"  Wins: {results['solo_wins']}/{results['solo_total']} ({results['solo_win_ratio']:.1f}% winrate)")

    print("\n" + Fore.CYAN + "Duo Queue:" + Style.RESET_ALL)
    print(f"  Games (where a duo partner was identified): {results['duo_queue']}")
    if results['duo_win_ratio'] is not None:
        print(f"  Wins: {results['duo_wins']}/{results['duo_total']} ({results['duo_win_ratio']:.1f}% winrate)")
    else:
        print("  Not enough Duo Queue games for winrate calculation (minimum 3 required)")

    print(Fore.CYAN + "\nGame Mode Distribution:" + Style.RESET_ALL)
    queue_names = {
        400: "Normal Draft",
        420: "Ranked Solo/Duo",
        430: "Normal Blind",
        440: "Ranked Flex",
        450: "ARAM",
        700: "Clash",
        830: "Co-op vs AI (Intro)",
        840: "Co-op vs AI (Beginner)",
        850: "Co-op vs AI (Intermediate)",
        900: "URF",
        1020: "One for All",
        1300: "Nexus Blitz",
        1400: "Ultimate Spellbook",
        1900: "URF",
    }
    for queue_id, count in results["game_modes"].items():
        qname = queue_names.get(queue_id, f"Queue ID {queue_id}")
        print(f"  {qname}: {count} games")

    print(Fore.CYAN + "\nChampion Stats:" + Style.RESET_ALL)
    for champ, stats in sorted(champ_stats.items(), key=lambda x: x[1]["games"], reverse=True):
        print(f"  {champ}: {stats['games']} games, winrate: {stats['win_rate']:.1f}%, KDA: {stats['kda']:.2f}")

    print(Fore.CYAN + "\nLane Performance:" + Style.RESET_ALL)
    for lane, stats in lane_stats.items():
        print(f"  {lane}: {stats['games']} games, winrate: {stats['win_rate']:.1f}%")

    print(Fore.YELLOW + "\nNote: If rate limits are reached, the retry mechanism will continue fetching data." + Style.RESET_ALL)

    # Print modern table with colors for console output; CSV export is handled without colors
    match_table_rows = print_match_table(match_data_list, puuid, match_classification, colored=COLORED_CONSOLE)
    return display_name, results, match_table_rows

def main():
    print_ascii_menu()
    # Ensure output directories exist
    os.makedirs("full", exist_ok=True)
    os.makedirs("table", exist_ok=True)
    config = load_config("apiKey.ini")
    settings = get_settings(config)
    global HEADERS
    HEADERS = {"X-Riot-Token": settings["api_key"]}
    # Setup other global variables from settings
    global NETWORK_TIMEOUT, MAX_RETRIES, CACHE_SIZE, COLORED_CONSOLE
    NETWORK_TIMEOUT = settings["network_timeout"]
    MAX_RETRIES = settings["max_retries"]
    CACHE_SIZE = settings["cache_size"]
    COLORED_CONSOLE = settings["colored_console"]
    if COLORED_CONSOLE:
        colorama.init(autoreset=True)
    else:
        colorama.deinit()

    try:
        summoner_name = input("Enter Riot Summoner Name: ").strip()
        tag = input("Enter Riot Tag: ").strip()
        games_input = input("Number of games to analyze: ").strip()
        try:
            games = int(games_input)
        except:
            games = 500
    except Exception as e:
        logger.exception("Error in user input")
        print(f"Error in user input: {e}")
        return

    now = datetime.now()
    timestr = now.strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r'\W+', '_', summoner_name)

    # Capture console output
    old_stdout = sys.stdout
    sys.stdout = mystdout = io.StringIO()

    ret = analyze_queue_types(summoner_name, tag, settings["api_key"], games)

    sys.stdout = old_stdout
    analysis_text = mystdout.getvalue()
    clean_text = remove_ansi_sequences(analysis_text)

    if ret is None:
        print("Analysis could not be completed.")
        logger.error("Analysis could not be completed.")
        input("\nPress Enter to exit...")
        return

    display_name, results, match_table_rows = ret

    txt_filename = os.path.join("full", f"{safe_name}_{timestr}.txt")
    try:
        with open(txt_filename, "w", encoding="utf-8") as f:
            f.write(clean_text)
        logger.info(f"Analysis output saved to text file: {txt_filename}")
        print(f"Analysis output saved to text file: {txt_filename}")
    except Exception as e:
        logger.exception("Error saving text file")

    if match_table_rows:
        try:
            df = pd.DataFrame(match_table_rows, columns=["GameID", "Date", "Result", "Type", "Teammates", "Playtime"])
            csv_filename = os.path.join("table", f"{safe_name}_{timestr}.csv")
            df.to_csv(csv_filename, index=False)
            logger.info(f"Match table saved as CSV: {csv_filename}")
            print(f"Match table saved as CSV: {csv_filename}")
        except Exception as e:
            logger.exception("Error saving CSV file")
    else:
        print("No match table found to save.")
        logger.warning("No match table found to save.")

    print("\n" + analysis_text)

if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            logger.exception("Unhandled exception in main")
            print(f"Unhandled exception: {e}")
        answer = input("\nWould you like to perform another analysis? (Y/n): ").strip().lower()
        if answer not in ["y", ""]:
            break
