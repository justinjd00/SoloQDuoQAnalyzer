import time
import requests
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# Globale Header (werden in main.py gesetzt)
HEADERS = {}

def safe_get(url, headers, params=None, max_retries=5, timeout=10):
    attempt = 0
    wait_time = 1
    while attempt < max_retries:
        try:
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    wait_time = int(retry_after)
                logger.warning(f"Rate limit hit at {url}. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                attempt += 1
                wait_time *= 2
            else:
                return response
        except Exception as e:
            logger.exception(f"Exception in safe_get for URL {url}: {e}")
            time.sleep(wait_time)
            attempt += 1
            wait_time *= 2
    return response

@lru_cache(maxsize=1024)
def cached_api_request(url, params_str="", headers=HEADERS):
    params = {}
    if params_str:
        try:
            for pair in params_str.split('&'):
                key, value = pair.split('=')
                params[key] = value
        except Exception as e:
            logger.exception("Error parsing params_str")
    response = safe_get(url, headers=headers, params=params)
    time.sleep(0.1)
    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"Error with request {url}: {response.status_code}")
        return None

def get_duo_partner_full_name(summoner_name, region="euw"):
    # duo_partner_cache wird im analyzer-Modul verwaltet
    from analyzer import duo_partner_cache
    if summoner_name in duo_partner_cache:
        return duo_partner_cache[summoner_name]
    try:
        url = f"https://euw1.api.riotgames.com/lol/summoner/v4/summoners/by-name/{summoner_name}"
        token = HEADERS.get("X-Riot-Token")
        response = safe_get(url, headers={"X-Riot-Token": token})
        if response.status_code == 200:
            data = response.json()
            puuid = data.get("puuid")
            if puuid:
                url2 = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}"
                response2 = safe_get(url2, headers={"X-Riot-Token": token})
                if response2.status_code == 200:
                    data2 = response2.json()
                    full_name = f"{data2.get('gameName', summoner_name)}#{data2.get('tagLine', 'UNKNOWN')}"
                    duo_partner_cache[summoner_name] = full_name
                    return full_name
    except Exception as e:
        logger.exception(f"Error in get_duo_partner_full_name for {summoner_name}")
    duo_partner_cache[summoner_name] = summoner_name
    return summoner_name

def get_summoner_full_name_by_puuid(puuid):
    # summoner_cache wird im analyzer-Modul verwaltet
    from analyzer import summoner_cache
    if puuid in summoner_cache:
        return summoner_cache[puuid]
    try:
        url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}"
        token = HEADERS.get("X-Riot-Token")
        response = safe_get(url, headers={"X-Riot-Token": token})
        if response.status_code == 200:
            data = response.json()
            full_name = f"{data.get('gameName', 'UNKNOWN')}#{data.get('tagLine', 'UNKNOWN')}"
            summoner_cache[puuid] = full_name
            return full_name
    except Exception as e:
        logger.exception(f"Error in get_summoner_full_name_by_puuid for {puuid}")
    return puuid
