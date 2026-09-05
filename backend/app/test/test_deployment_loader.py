from app.ingestion.deployment_loader import DeploymentLoader

loader = DeploymentLoader()

deployments = loader.load("data/deployments.json")

for deployment in deployments:
    print(deployment)