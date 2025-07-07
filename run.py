# run.py
import logging, sys

# 1) Set up console logging so you actually see startup messages
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]

)

# 2) Import your FastAPI app object directly
from app.main import app as fastapi_app

import uvicorn

if __name__ == "__main__":
    # 3) Pass the app object, not a string
    uvicorn.run(
        fastapi_app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
        # reload=False  # no need for reload in the bundled exe
    )
