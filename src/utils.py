import os
import random
import zipfile
import requests
import platform

from status import *
from config import *

def close_running_selenium_instances() -> None:
    """
    Closes any running Selenium instances.

    Returns:
        None
    """
    try:
        info(" => Closing running Selenium instances...")

        # Kill all running Firefox instances
        if platform.system() == "Windows":
            os.system("taskkill /f /im firefox.exe")
        else:
            os.system("pkill firefox")

        success(" => Closed running Selenium instances.")

    except Exception as e:
        error(f"Error occurred while closing running Selenium instances: {str(e)}")

def build_url(youtube_video_id: str) -> str:
    """
    Builds the URL to the YouTube video.

    Args:
        youtube_video_id (str): The YouTube video ID.

    Returns:
        url (str): The URL to the YouTube video.
    """
    return f"https://www.youtube.com/watch?v={youtube_video_id}"

def rem_temp_files() -> None:
    """
    Removes temporary files in the `.mp` directory, except for MP4 files and JSON files.

    Returns:
        None
    """
    # Path to the `.mp` directory
    mp_dir = os.path.join(ROOT_DIR, ".mp")

    files = os.listdir(mp_dir)

    for file in files:
        # Keep JSON and MP4 files
        if not file.endswith(".json") and not file.endswith(".mp4"):
            os.remove(os.path.join(mp_dir, file))

def fetch_songs() -> None:
    """
    Downloads songs into songs/ directory to use with geneated videos.

    Returns:
        None
    """
    try:
        info(f" => Fetching songs...")

        files_dir = os.path.join(ROOT_DIR, "Songs")
        if not os.path.exists(files_dir):
            os.mkdir(files_dir)
            if get_verbose():
                info(f" => Created directory: {files_dir}")
        else:
            # Skip if songs are already downloaded
            return

        # Download songs
        response = requests.get(get_zip_url() or "https://filebin.net/bb9ewdtckolsf3sg/drive-download-20240209T180019Z-001.zip")

        # Save the zip file
        with open(os.path.join(files_dir, "songs.zip"), "wb") as file:
            file.write(response.content)

        # Unzip the file
        with zipfile.ZipFile(os.path.join(files_dir, "songs.zip"), "r") as file:
            file.extractall(files_dir)

        # Remove the zip file
        os.remove(os.path.join(files_dir, "songs.zip"))

        success(" => Downloaded Songs to ../Songs.")

    except Exception as e:
        error(f"Error occurred while fetching songs: {str(e)}")

def choose_random_song() -> str:
    """
    Chooses a random song from the songs/ directory.
    Only includes valid MP3 files and performs validation checks.

    Returns:
        str: The path to the chosen song, or None if no valid songs are found.
    """
    try:
        songs_dir = os.path.join(ROOT_DIR, "Songs")
        if not os.path.exists(songs_dir):
            error(f"Songs directory not found at: {songs_dir}")
            return None

        # Get all MP3 files from the directory
        songs = [f for f in os.listdir(songs_dir) 
                if f.lower().endswith('.mp3') 
                and os.path.isfile(os.path.join(songs_dir, f))
                and not f.startswith('.')]  # Exclude hidden files like .DS_Store
        
        if not songs:
            error("No valid MP3 files found in Songs directory")
            return None
            
        # Choose a random song
        song = random.choice(songs)
        song_path = os.path.join(songs_dir, song)
        
        # Validate the chosen file
        if not os.path.exists(song_path):
            error(f"Chosen song file does not exist: {song_path}")
            return None
            
        if os.path.getsize(song_path) == 0:
            error(f"Chosen song file is empty: {song_path}")
            return None
            
        success(f" => Chose song: {song}")
        return song_path
        
    except Exception as e:
        error(f"Error occurred while choosing random song: {str(e)}")
        return None
