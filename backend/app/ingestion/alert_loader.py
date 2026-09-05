import json

class AlertLoader:

    def load(self, file_apth: str):
        with open(file_path, "r") as file:
            alerts = json.load(file)

        return alerts