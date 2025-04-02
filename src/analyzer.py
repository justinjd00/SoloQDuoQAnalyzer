import re
import time
import concurrent.futures
from collections import defaultdict
from datetime import datetime
import logging
from tqdm import tqdm
from riot_api import safe_get, get_duo_partner_full_name, get_summoner_full_name_by_puuid

logger = logging.getLogger(__name__)

# Globale Cache-Dictionaries
duo_partner_cache = {}
summoner_cache = {}

class RiotAnalyzer:
    def __init__(self, api_key, network_timeout=10, max_retries=5):
        self.api_key = api_key
        self.headers = {"X-Riot-Token": api_key}
        self.match_cache = {}
        self.network_timeout = network_timeout
        self.max_retries = max_retries

    def get_account_by_riot_id(self, name, tag, region="europe"):
        try:
            url = f"https://{region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}"
            response = safe_get(url, headers=self.headers, max_retries=self.max_retries, timeout=self.network_timeout)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error retrieving Riot ID data: {response.status_code}")
                logger.error(response.text)
                return None
        except Exception as e:
            logger.exception("Exception in get_account_by_riot_id")
            return None

    def get_match_history(self, puuid, count, region="europe"):
        matches = []
        num_requests = (count + 99) // 100
        start_indices = [i * 100 for i in range(num_requests)]
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_to_batch = {
                    executor.submit(self._get_match_batch, puuid, min(100, count - start), start, region): start 
                    for start in start_indices
                }
                for future in concurrent.futures.as_completed(future_to_batch):
                    batch = future.result()
                    if batch:
                        matches.extend(batch)
                    if len(matches) >= count:
                        matches = matches[:count]
                        break
            return matches
        except Exception as e:
            logger.exception("Exception in get_match_history")
            return matches

    def _get_match_batch(self, puuid, count, start, region):
        try:
            url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
            params = {"count": count, "start": start}
            response = safe_get(url, headers=self.headers, params=params, timeout=self.network_timeout)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error retrieving match batch: {response.status_code}")
                return []
        except Exception as e:
            logger.exception("Exception in _get_match_batch")
            return []

    def process_matches(self, matches, puuid):
        match_data_dict = {}
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                future_to_match = {executor.submit(self.get_match_details, match_id): match_id for match_id in matches}
                for future in tqdm(concurrent.futures.as_completed(future_to_match),
                                   total=len(future_to_match),
                                   desc="Processing Matches",
                                   unit="Match"):
                    match_id = future_to_match[future]
                    try:
                        match_data = future.result()
                        if match_data and "info" in match_data:
                            match_data_dict[match_id] = match_data
                    except Exception as e:
                        logger.exception(f"Error processing match {match_id}")
            logger.info(f"Successfully retrieved {len(match_data_dict)} match details.")
        except Exception as e:
            logger.exception("Exception in process_matches")
        
        game_modes = defaultdict(int)
        ranked_matches = []
        match_outcomes = {}
        teammates_per_match = {}

        try:
            for match_id, match_data in match_data_dict.items():
                queue_id = match_data["info"].get("queueId", 0)
                game_modes[queue_id] += 1
                if queue_id == 420:
                    participant_data = next((p for p in match_data["info"]["participants"] if p["puuid"] == puuid), None)
                    if participant_data:
                        win = participant_data.get("win", False)
                        match_outcomes[match_id] = win
                        ranked_matches.append(match_id)
                        teammates = [
                            p.get("summonerName") or get_summoner_full_name_by_puuid(p["puuid"])
                            for p in match_data["info"]["participants"]
                            if p["teamId"] == participant_data["teamId"] and p["puuid"] != puuid
                        ]
                        teammates_per_match[match_id] = teammates
        except Exception as e:
            logger.exception("Exception while processing matches")

        try:
            ranked_matches = sorted(ranked_matches, key=lambda mid: match_data_dict[mid]["info"].get("gameCreation", 0), reverse=True)
        except Exception as e:
            logger.exception("Exception sorting ranked_matches")

        overall_freq = defaultdict(int)
        for match_id in ranked_matches:
            for teammate in teammates_per_match.get(match_id, []):
                overall_freq[teammate] += 1

        match_classification = {}
        for match_id in ranked_matches:
            candidates = [t for t in teammates_per_match.get(match_id, []) if overall_freq[t] >= 2]
            if candidates:
                candidate = max(candidates, key=lambda t: overall_freq[t])
                match_classification[match_id] = f"DuoQ: {candidate}"
            else:
                match_classification[match_id] = "SoloQ"

        duo_matches = [m for m in ranked_matches if match_classification[m].startswith("DuoQ:")]
        solo_matches = [m for m in ranked_matches if match_classification[m] == "SoloQ"]

        duo_queue_count = len(duo_matches)
        solo_queue_count = len(solo_matches)
        solo_wins = sum(1 for m in solo_matches if match_outcomes.get(m, False))
        duo_wins = sum(1 for m in duo_matches if match_outcomes.get(m, False))
        duo_win_ratio = (duo_wins / duo_queue_count * 100) if duo_queue_count > 2 else None

        duo_partner_stats = defaultdict(lambda: {"total": 0, "wins": 0})
        for match_id in duo_matches:
            candidate = match_classification[match_id].split(": ")[1]
            duo_partner_stats[candidate]["total"] += 1
            if match_outcomes.get(match_id, False):
                duo_partner_stats[candidate]["wins"] += 1
        duo_partner_ratios = {partner: (stats["wins"] / stats["total"] * 100 if stats["total"] > 0 else 0)
                              for partner, stats in duo_partner_stats.items()}

        results = {
            "solo_queue": solo_queue_count,
            "solo_wins": solo_wins,
            "solo_total": solo_queue_count,
            "solo_win_ratio": (solo_wins / solo_queue_count * 100) if solo_queue_count > 0 else 0,
            "duo_queue": duo_queue_count,
            "duo_wins": duo_wins,
            "duo_total": duo_queue_count,
            "duo_win_ratio": duo_win_ratio,
            "duo_partner_stats": dict(duo_partner_stats),
            "duo_partner_ratios": duo_partner_ratios,
            "game_modes": game_modes,
            "total_ranked": len(ranked_matches),
            "fetched_matches": len(match_data_dict),
            "match_data_list": list(match_data_dict.values()),
            "match_classification": match_classification
        }
        return results

    def get_match_details(self, match_id, region="europe"):
        if match_id in self.match_cache:
            return self.match_cache[match_id]
        try:
            url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
            response = safe_get(url, headers=self.headers)
            if response.status_code == 200:
                match_data = response.json()
                self.match_cache[match_id] = match_data
                return match_data
            else:
                logger.error(f"Error retrieving match {match_id}: {response.status_code}")
                return None
        except Exception as e:
            logger.exception(f"Exception in get_match_details for match {match_id}")
            return None

def analyze_champion_stats(match_data_list, puuid):
    champion_stats = defaultdict(lambda: {"games": 0, "wins": 0, "kills": 0, "deaths": 0, "assists": 0})
    try:
        for match in match_data_list:
            if match["info"].get("queueId") != 420:
                continue
            participant = next((p for p in match["info"]["participants"] if p["puuid"] == puuid), None)
            if participant:
                champ = participant.get("championName", "Unknown")
                champion_stats[champ]["games"] += 1
                if participant.get("win", False):
                    champion_stats[champ]["wins"] += 1
                champion_stats[champ]["kills"] += participant.get("kills", 0)
                champion_stats[champ]["deaths"] += participant.get("deaths", 0)
                champion_stats[champ]["assists"] += participant.get("assists", 0)
        for champ, stats in champion_stats.items():
            stats["win_rate"] = (stats["wins"] / stats["games"] * 100) if stats["games"] > 0 else 0
            stats["kda"] = (stats["kills"] + stats["assists"]) / (stats["deaths"] if stats["deaths"] > 0 else 1)
    except Exception as e:
        logger.exception("Exception in analyze_champion_stats")
    return champion_stats

def analyze_lane_performance(match_data_list, puuid):
    lane_stats = {
        "TOP": {"games": 0, "wins": 0},
        "JUNGLE": {"games": 0, "wins": 0},
        "MID": {"games": 0, "wins": 0},
        "ADC": {"games": 0, "wins": 0},
        "SUPPORT": {"games": 0, "wins": 0}
    }
    mapping = {
        "TOP": "TOP",
        "JUNGLE": "JUNGLE",
        "MIDDLE": "MID",
        "MID": "MID",
        "BOTTOM": "ADC",
        "UTILITY": "SUPPORT"
    }
    try:
        for match in match_data_list:
            if match["info"].get("queueId") != 420:
                continue
            participant = next((p for p in match["info"]["participants"] if p["puuid"] == puuid), None)
            if participant:
                lane_raw = participant.get("individualPosition", "UNKNOWN").upper()
                lane = mapping.get(lane_raw, lane_raw)
                if lane in lane_stats:
                    lane_stats[lane]["games"] += 1
                    if participant.get("win", False):
                        lane_stats[lane]["wins"] += 1
        for lane, stats in lane_stats.items():
            stats["win_rate"] = (stats["wins"] / stats["games"] * 100) if stats["games"] > 0 else 0
    except Exception as e:
        logger.exception("Exception in analyze_lane_performance")
    return lane_stats
