from pathlib import Path

PYTHON_FOLDER: Path = Path(__file__).parent.parent
LOGS_FOLDER: Path = Path(f"{PYTHON_FOLDER}/logs")
SETTINGS_FOLDER: Path = Path(f"{PYTHON_FOLDER}/settings")
DATA_FOLDER: Path = Path(f"{PYTHON_FOLDER}/data")
