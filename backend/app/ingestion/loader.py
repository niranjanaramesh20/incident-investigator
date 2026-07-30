from pathlib import Path
import json

class DataLoader:
    def __init__(self, data_dir: str = "sample_data"):
        self.data_dir = Path(data_dir)

      