from pathlib import Path

PROJECT_FOLDER: Path = Path(__file__).parent.parent.parent
LOGS_FOLDER: Path = Path(f"{PROJECT_FOLDER}/logs")
SETTINGS_FOLDER: Path = Path(f"{PROJECT_FOLDER}/settings")
DATA_FOLDER: Path = Path(f"{PROJECT_FOLDER}/data")
SOURCE_FOLDER: Path = Path(f"{PROJECT_FOLDER}/src")
TEMP_FOLDER: Path = Path(f"{PROJECT_FOLDER}/temp")
