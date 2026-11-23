import uvicorn
from app.config import settings

if __name__ == "__main__":
    print(f"Starting Widget Platform server at http://{settings.HOST}:{settings.PORT}")
    print(f"Admin Dashboard available at: http://{settings.HOST}:{settings.PORT}/dashboard")
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)
