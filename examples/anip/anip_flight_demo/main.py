"""Server bootstrap."""
import uvicorn


def run():
    uvicorn.run("app:app", host="0.0.0.0", port=9100, reload=True)


if __name__ == "__main__":
    run()
