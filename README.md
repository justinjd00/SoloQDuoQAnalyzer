# SoloQDuoQAnalyzer
Tool which Analyse your SoloQ and DuoQ games
## Getting Started
### Prerequisites
- Python 3.7+ installed on your system.
- A valid Riot Games API key. You can get one from the Riot Developer Portal.

### Installation
1. Clone the repository:
 ```sh
git clone https://github.com/justinjd00/RiotMatchAnalyzer.git
cd RiotMatchAnalyzer
```
2. Install dependencies:
 ```sh
pip install -r requirements.txt
```

### Configuration
 ```sh
[API]
key = RGAPI-Your-API-Key-Here
region = europe

[Logging]
level = INFO

[Network]
timeout = 10
max_retries = 5

[Cache]
size = 1024
enable_cache = True

[Output]
colored_console = true

[Statistics]
detailed_champion_stats = false
 ```

#### Note:

Replace RGAPI-Your-API-Key-Here with your actual Riot API key.

You can adjust other settings (e.g., network timeout, max retries, cache size, and whether you want colored output in the console).

## Running the Project
 ```sh
python main.py
 ```

## Contributing

Contributions are welcome! Feel free to open an issue or submit a pull request if you have ideas for improvements or new features.

## License
This project is licensed under the MIT License.