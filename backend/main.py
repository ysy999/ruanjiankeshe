from dotenv import load_dotenv
import uvicorn

from app.main import create_app

load_dotenv()

app = create_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
