from fastapi import FastAPI

app = FastAPI(
    title="Incident Investigation System",
    version="1.0.0")

@app.get("/")
async def root():
    return {
        "message": "Incident Investigation API"
    }
