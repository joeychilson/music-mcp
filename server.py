import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@dataclass
class SpotifyClient:
    """Singleton class to manage Spotify client instance"""

    _instance: Optional[Spotify] = None

    @classmethod
    def get_client(cls) -> Spotify:
        """Get or create Spotify client instance"""
        if cls._instance is None:
            try:
                client_id = os.getenv("SPOTIFY_CLIENT_ID")
                client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
                redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")

                if not all([client_id, client_secret, redirect_uri]):
                    logging.error("Missing required Spotify credentials in environment")
                    raise ValueError("Missing required Spotify credentials")

                cache_path = os.path.expanduser("~/.config/spotify-mcp/.cache")
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)

                auth_manager = SpotifyOAuth(
                    scope=[
                        "user-library-read",
                        "user-read-currently-playing",
                        "user-read-playback-state",
                    ],
                    client_id=client_id,
                    client_secret=client_secret,
                    redirect_uri=redirect_uri,
                    cache_path=cache_path,
                )
                cls._instance = Spotify(auth_manager=auth_manager)
                logging.info("Successfully initialized Spotify client")
            except Exception as e:
                logging.error(f"Failed to initialize Spotify client: {str(e)}")
                raise
        return cls._instance


mcp = FastMCP("music-mcp", dependencies=["spotipy"])


@mcp.tool()
def get_current_track() -> Dict[str, Any]:
    """Get the current track playing on Spotify

    Returns:
        Dict[str, Any]: The current track playing on Spotify
    """
    return SpotifyClient.get_client().current_playback()


class LikedTracksParams(BaseModel):
    """The parameters for getting liked tracks"""

    limit: int = Field(
        default=20, ge=1, le=50, description="The number of tracks to return"
    )
    offset: int = Field(
        default=0, ge=0, description="The index of the first track to return"
    )


@mcp.tool()
def get_liked_tracks(params: LikedTracksParams) -> List[Dict[str, Any]]:
    """Get the user's liked tracks

    Args:
        limit (int): The number of tracks to return (default: 20, max: 50)
        offset (int): The index of the first track to return (default: 0)

    Returns:
        List[Dict[str, Any]]: The user's liked tracks
    """
    return SpotifyClient.get_client().current_user_saved_tracks(
        limit=params.limit, offset=params.offset
    )


if __name__ == "__main__":
    try:
        logging.info("Starting music-mcp server...")
        mcp.run()
    except Exception as e:
        logging.error(f"Failed to start music-mcp server: {str(e)}")
        sys.exit(1)
