import configparser
import os

def load_config(filename="apiKey.ini"):
    config = configparser.ConfigParser()
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Configuration file '{filename}' not found.")
    config.read(filename)
    return config

def get_settings(config):
    settings = {}
    settings["api_key"] = config.get("API", "key", fallback="YOUR_API_KEY")
    settings["region"] = config.get("API", "region", fallback="europe")
    settings["network_timeout"] = config.getint("Network", "timeout", fallback=10)
    settings["max_retries"] = config.getint("Network", "max_retries", fallback=5)
    settings["cache_size"] = config.getint("Cache", "size", fallback=1024)
    settings["colored_console"] = config.getboolean("Output", "colored_console", fallback=True)
    return settings
