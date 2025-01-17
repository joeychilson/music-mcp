# music-mcp

A Model Context Protocol (MCP) server to let Claude help you manage your music.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- [Spotify Application](https://developer.spotify.com/dashboard)

## Configuration

Add the following to your `claude_desktop_config.json` file:

```
{
  "mcpServers": {
    "music-mcp": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "mcp",
        "--with",
        "spotipy",
        "/path/to/music-mcp/server.py"
      ],
      "env": {
        "SPOTIFY_CLIENT_ID": "your_spotify_client_id",
        "SPOTIFY_CLIENT_SECRET": "your_spotify_client_secret",
        "SPOTIFY_REDIRECT_URI": "your_spotify_redirect_uri"
      }
    }
  }
}
```