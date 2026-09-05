import json

class LogLoader:

    def load(self, file_path: str):
        logs = []

        with open(file_path, "r") as file:
            for line in file:
                line = line.strip()

                if not line:
                    continue

                log = json.loads(line)
                logs.append(log)

        return logs