import json

class DeploymentLoader:

    def load(self, file_path: str):
        with open(file_path, "r") as file:
            deployments = json.load(file)

        return deployments    