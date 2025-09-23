import argparse
import uvicorn

try:
    # When frozen by PyInstaller, relative imports still work because package structure is preserved via datas
    from app.main import app  # noqa: F401
except Exception as e:
    # Fallback / helpful debug
    print(f"Failed to import FastAPI app: {e}")
    raise


def parse_args():
    parser = argparse.ArgumentParser(description="Erudi backend launcher")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    parser.add_argument("--log-level", default="info", help="uvicorn log level")
    return parser.parse_args()


def main():
    args = parse_args()
    # We import lazily here so that argparse --help works even if some heavy deps are missing
    from app.main import app  # re-import inside function (PyInstaller collection safety)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)


if __name__ == "__main__":
    main()
