import logging
import os
from enum import Enum
from dataclasses import dataclass
import sys
from typing import Any, Dict, List, Literal, Optional

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

                cache_path = os.path.expanduser("~/.config/music-mcp/.cache")
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)

                auth_manager = SpotifyOAuth(
                    scope=[
                        "user-library-read",
                        "user-top-read",
                        "user-read-currently-playing",
                        "user-read-playback-state",
                        "user-read-recently-played",
                        "user-read-playback-position",
                        "user-read-private",
                        "user-modify-playback-state",
                        "playlist-read-private",
                        "playlist-read-collaborative",
                        "playlist-modify-private",
                        "playlist-modify-public",
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


@mcp.resource(uri="spotify://devices")
def devices() -> Dict[str, Any]:
    """Get the devices available on Spotify

    Returns:
        Dict[str, Any]: The devices available on Spotify
    """
    return SpotifyClient.get_client().devices()


@mcp.resource(uri="spotify://user/playlists")
def user_playlists() -> Dict[str, Any]:
    """Get the user's playlists

    Returns:
        Dict[str, Any]: The user's playlists
    """
    return SpotifyClient.get_client().current_user_playlists()


@mcp.resource(uri="spotify://user/saved-tracks")
def user_saved_tracks() -> Dict[str, Any]:
    """Get the user's saved tracks

    Returns:
        Dict[str, Any]: The user's saved tracks
    """
    return SpotifyClient.get_client().current_user_saved_tracks()


@mcp.resource(uri="spotify://user/saved-albums")
def user_saved_albums() -> Dict[str, Any]:
    """Get the user's saved albums

    Returns:
        Dict[str, Any]: The user's saved albums
    """
    return SpotifyClient.get_client()


@mcp.tool()
def current_playback() -> Dict[str, Any]:
    """Get the current playback state

    Returns:
        Dict[str, Any]: The current playback state
    """
    return SpotifyClient.get_client().current_playback()


@mcp.tool()
def recent_played_tracks(
    limit: int = 20, before: int = None, after: int = None
) -> Dict[str, Any]:
    """Get the user's recently played tracks

    Args:
        limit: The number of tracks to return
        before: A Unix timestamp in milliseconds
        after: A Unix timestamp in milliseconds

    Returns:
        Dict[str, Any]: The user's recently played tracks
    """
    return SpotifyClient.get_client().current_user_recently_played(
        limit=limit, before=before, after=after
    )


class PlaybackAction(str, Enum):
    """Enum for different playback actions"""

    PLAY = "play"
    PAUSE = "pause"
    RESUME = "resume"
    NEXT = "next"
    PREVIOUS = "previous"
    SEEK = "seek"
    TRANSFER = "transfer"
    SET_VOLUME = "set_volume"
    SET_MODE = "set_mode"


class PlaybackTrackParams(BaseModel):
    """Parameters for playing specific tracks"""

    context_uri: Optional[str] = Field(
        default=None,
        description="URI to start playback of an album, artist, or playlist",
    )
    track_uris: Optional[List[str]] = Field(
        default=None, description="List of track URIs to play"
    )
    offset: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Offset as {'position': <int>} or {'uri': '<track uri>'}",
    )
    position_ms: Optional[int] = Field(
        default=None, description="Position in milliseconds to start from"
    )


class PlaybackModeParams(BaseModel):
    """Parameters for playback mode settings"""

    shuffle: Optional[bool] = Field(
        default=None, description="Enable/disable shuffle mode"
    )
    repeat: Optional[Literal["off", "track", "context"]] = Field(
        default=None,
        description="Repeat mode: off, track (repeat song), or context (repeat playlist/album)",
    )


class PlaybackControlParams(BaseModel):
    """Unified parameters for controlling playback"""

    action: PlaybackAction = Field(description="The playback action to perform")
    device_id: Optional[str] = Field(
        default=None, description="Target device ID for the action"
    )
    track_params: Optional[PlaybackTrackParams] = Field(
        default=None, description="Parameters for playing tracks"
    )
    mode_params: Optional[PlaybackModeParams] = Field(
        default=None, description="Parameters for setting playback mode"
    )
    position_ms: Optional[int] = Field(
        default=None, description="Position in milliseconds for seek action"
    )
    volume_percent: Optional[int] = Field(
        default=None, ge=0, le=100, description="Volume level (0-100) for volume action"
    )
    force_play: Optional[bool] = Field(
        default=None, description="Whether to force playback after transfer"
    )


@mcp.tool()
def control_playback(params: PlaybackControlParams) -> Dict[str, Any]:
    """Control the playback of Spotify

    Args:
        params: Playback control parameters

    Returns:
        Dict[str, Any]: Status and current playback state
    """
    client = SpotifyClient.get_client()

    try:
        if params.action == PlaybackAction.PLAY and params.track_params:
            result = client.start_playback(
                device_id=params.device_id,
                context_uri=params.track_params.context_uri,
                uris=params.track_params.track_uris,
                offset=params.track_params.offset,
                position_ms=params.track_params.position_ms,
            )

        elif params.action == PlaybackAction.PAUSE:
            result = client.pause_playback(device_id=params.device_id)

        elif params.action == PlaybackAction.RESUME:
            result = client.start_playback(device_id=params.device_id)

        elif params.action == PlaybackAction.NEXT:
            result = client.next_track(device_id=params.device_id)

        elif params.action == PlaybackAction.PREVIOUS:
            result = client.previous_track(device_id=params.device_id)

        elif params.action == PlaybackAction.SEEK and params.position_ms is not None:
            result = client.seek_track(
                position_ms=params.position_ms, device_id=params.device_id
            )

        elif params.action == PlaybackAction.TRANSFER and params.device_id:
            result = client.transfer_playback(
                device_id=params.device_id,
                force_play=params.force_play if params.force_play is not None else True,
            )

        elif (
            params.action == PlaybackAction.SET_VOLUME
            and params.volume_percent is not None
        ):
            result = client.volume(
                volume_percent=params.volume_percent, device_id=params.device_id
            )

        elif params.action == PlaybackAction.SET_MODE and params.mode_params:
            if params.mode_params.shuffle is not None:
                client.shuffle(params.mode_params.shuffle, device_id=params.device_id)
            if params.mode_params.repeat is not None:
                client.repeat(params.mode_params.repeat, device_id=params.device_id)
            result = {"status": "success"}

        else:
            return {
                "status": "error",
                "message": "Invalid action or missing required parameters",
            }

        return {"status": "success", "action": params.action, "result": result}

    except Exception as e:
        return {"status": "error", "action": params.action, "message": str(e)}


class SearchParams(BaseModel):
    """Parameters for search operations"""

    query: str = Field(description="Search query string")
    types: List[Literal["track", "album", "artist", "playlist"]] = Field(
        description="Types of items to search for"
    )
    limit: Optional[int] = Field(
        default=20, ge=1, le=50, description="Number of results per type"
    )
    offset: Optional[int] = Field(
        default=0, ge=0, description="Offset for paginated results"
    )
    market: Optional[str] = Field(
        description="ISO 3166-1 alpha-2 country code to limit results"
    )


@mcp.tool()
def search(params: SearchParams) -> Dict[str, Any]:
    """Search Spotify for tracks, albums, artists, or playlists

    Args:
        params: Search parameters including query and types

    Returns:
        Dict[str, Any]: Search results for each requested type
    """
    try:
        results = SpotifyClient.get_client().search(
            q=params.query,
            type=",".join(params.types),
            limit=params.limit,
            offset=params.offset,
            market=params.market,
        )
        return {"status": "success", "results": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}


class PlaylistOperation(str, Enum):
    """Enum for different playlist operations"""

    CREATE = "create"
    ADD_TRACKS = "add_tracks"
    REMOVE_TRACKS = "remove_tracks"
    UPDATE_DETAILS = "update_details"
    GET_TRACKS = "get_tracks"


class PlaylistDetails(BaseModel):
    """Parameters for playlist creation and modification"""

    name: Optional[str] = Field(default=None, description="Name of the playlist")
    description: Optional[str] = Field(
        default=None, description="Description of the playlist"
    )
    public: Optional[bool] = Field(
        default=None, description="Whether the playlist is public"
    )
    collaborative: Optional[bool] = Field(
        default=None, description="Whether the playlist is collaborative"
    )


class PlaylistParams(BaseModel):
    """Unified parameters for playlist operations"""

    operation: PlaylistOperation = Field(
        description="The playlist operation to perform"
    )
    playlist_id: Optional[str] = Field(
        default=None, description="Spotify ID of the playlist (not needed for create)"
    )
    details: Optional[PlaylistDetails] = Field(
        default=None, description="Details for create/update operations"
    )
    tracks: Optional[List[str]] = Field(
        default=None, description="List of Spotify track URIs, URLs or IDs"
    )
    position: Optional[int] = Field(
        default=None, description="Position to insert tracks (for add operation)"
    )
    limit: Optional[int] = Field(
        default=100, description="Number of tracks to return for get_tracks"
    )
    offset: Optional[int] = Field(
        default=0, description="Offset for get_tracks operation"
    )


@mcp.tool()
def manage_playlist(params: PlaylistParams) -> Dict[str, Any]:
    """Manage Spotify playlists with various operations

    Args:
        params: Playlist operation parameters including operation type and relevant details

    Returns:
        Dict[str, Any]: Operation result
    """
    client = SpotifyClient.get_client()

    try:
        if params.operation == PlaylistOperation.CREATE:
            if not params.details or not params.details.name:
                raise ValueError("Playlist name is required for creation")

            user_id = client.me()["id"]
            result = client.user_playlist_create(
                user=user_id,
                name=params.details.name,
                public=params.details.public
                if params.details.public is not None
                else True,
                collaborative=params.details.collaborative
                if params.details.collaborative is not None
                else False,
                description=params.details.description,
            )

        elif params.operation == PlaylistOperation.ADD_TRACKS:
            if not params.playlist_id or not params.tracks:
                raise ValueError(
                    "Playlist ID and tracks are required for adding tracks"
                )

            result = client.playlist_add_items(
                playlist_id=params.playlist_id,
                items=params.tracks,
                position=params.position,
            )

        elif params.operation == PlaylistOperation.REMOVE_TRACKS:
            if not params.playlist_id or not params.tracks:
                raise ValueError(
                    "Playlist ID and tracks are required for removing tracks"
                )

            result = client.playlist_remove_all_occurrences_of_items(
                playlist_id=params.playlist_id, items=params.tracks
            )

        elif params.operation == PlaylistOperation.UPDATE_DETAILS:
            if not params.playlist_id or not params.details:
                raise ValueError("Playlist ID and new details are required for update")

            result = client.playlist_change_details(
                playlist_id=params.playlist_id,
                name=params.details.name,
                public=params.details.public,
                collaborative=params.details.collaborative,
                description=params.details.description,
            )

        elif params.operation == PlaylistOperation.GET_TRACKS:
            if not params.playlist_id:
                raise ValueError("Playlist ID is required for getting tracks")

            result = client.playlist_items(
                playlist_id=params.playlist_id, limit=params.limit, offset=params.offset
            )

        return {"status": "success", "operation": params.operation, "result": result}

    except Exception as e:
        return {"status": "error", "operation": params.operation, "message": str(e)}


if __name__ == "__main__":
    try:
        logging.info("Starting music-mcp server...")
        mcp.run()
    except Exception as e:
        logging.error(f"Failed to start music-mcp server: {str(e)}")
        sys.exit(1)
