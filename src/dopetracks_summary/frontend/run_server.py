import uvicorn

if __name__ == "__main__":
    uvicorn.run("spotify_auth_server:app", host="localhost", port=8888, reload=True)
