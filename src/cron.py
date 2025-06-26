# RUN THIS N AMOUNT OF TIMES
import sys
import argparse
from typing import Optional

from status import *
from cache import get_accounts
from config import get_verbose
from classes.Tts import TTS
from classes.Twitter import Twitter
from classes.YouTube import YouTube
from classes.Video import Video
from state import VideoState

def get_latest_incomplete_session(state_manager: VideoState) -> Optional[dict]:
    """Get the most recently updated incomplete session.
    
    Args:
        state_manager: The VideoState instance
        
    Returns:
        The most recent incomplete session or None if no incomplete sessions exist
    """
    incomplete = state_manager.get_incomplete_sessions()
    if not incomplete:
        return None
        
    # Sort by last_updated time and get the most recent
    latest = max(
        incomplete.items(),
        key=lambda x: x[1].get("last_updated", x[1]["created_at"])
    )
    return latest[1]

def handle_video_generation(account_id: Optional[str], force_new: bool = False, clean: bool = False) -> None:
    """Handle video generation with support for resuming sessions.
    
    Args:
        account_id: Optional YouTube account ID
        force_new: Whether to force create a new session
        clean: Whether to clean up incomplete sessions
    """
    verbose = get_verbose()
    tts = TTS()
    state_manager = VideoState()
    
    # Clean up if requested
    if clean:
        if verbose:
            info("Cleaning up incomplete sessions...")
        state_manager.cleanup_incomplete_sessions()
    
    # If not forcing new, try to find an incomplete session
    session = None
    if not force_new:
        session = get_latest_incomplete_session(state_manager)
        if session:
            if verbose:
                info(f"Resuming video generation from session: {session['id']}")
                info(f"Session status: {session['status']}")
                info(f"Last updated: {session.get('last_updated', 'Never')}")
            
            video = Video(
                session["niche"],
                session["language"],
                session_id=session["id"]
            )
        elif verbose:
            info("No incomplete sessions found, starting new video generation")
    
    # If forcing new or no incomplete session found, create new
    if force_new or not session:
        if verbose and force_new:
            info("Forcing new video generation session")
        video = Video(
            "Science",  # TODO: Get from account or config
            "English"
        )
    
    # Generate the video
    video_path = video.generate_video(tts)
    if verbose and video_path:
        success(f"Generated video at: {video_path}")
    
    return video_path

def main():
    """Main function to post content to Twitter or upload videos to YouTube.

    This function determines its operation based on command-line arguments:
    - If the purpose is "twitter", it initializes a Twitter account and posts a message.
    - If the purpose is "youtube", it initializes a YouTube account, generates a video with TTS, and uploads it.
    - If the purpose is "video_generate", it only generates the video without uploading.

    Command-line arguments are parsed using argparse.
    """
    parser = argparse.ArgumentParser(description="Generate and upload content to social media platforms")
    parser.add_argument("purpose", choices=["twitter", "youtube", "video_generate"], 
                       help="The purpose of the script execution")
    parser.add_argument("account_id", nargs="?", default=None,
                       help="The account UUID (optional)")
    parser.add_argument("--new", action="store_true",
                       help="Force create a new video session")
    parser.add_argument("--clean", action="store_true",
                       help="Clean up incomplete sessions")
    
    args = parser.parse_args()
    verbose = get_verbose()

    if args.purpose == "twitter":
        accounts = get_accounts("twitter")
        if not accounts:
            error("No Twitter accounts found.")
            sys.exit(1)

        # If no account_id provided, use the first account
        if not args.account_id:
            account = accounts[0]
            if verbose:
                info(f"No account ID provided. Using first available account: {account['nickname']}")
        else:
            account = next((acc for acc in accounts if acc["id"] == args.account_id), None)
            if not account:
                error(f"No Twitter account found with ID: {args.account_id}")
                sys.exit(1)

        if verbose:
            info("Initializing Twitter...")
        twitter = Twitter(
            account["id"],
            account["nickname"],
            account["firefox_profile"],
            account["topic"]
        )
        twitter.post()
        if verbose:
            success("Done posting.")

    elif args.purpose == "youtube" or args.purpose == "video_generate":
        # Generate the video
        video_path = handle_video_generation(args.account_id, args.new, args.clean)
        
        if not video_path:
            error("Failed to generate video")
            sys.exit(1)

        # Upload if needed
        if args.purpose == "youtube":
            accounts = get_accounts("youtube")
            if not accounts:
                error("No YouTube accounts found.")
                sys.exit(1)

            # If no account_id provided, use the first account
            if not args.account_id:
                account = accounts[0]
                if verbose:
                    info(f"No account ID provided. Using first available account: {account['nickname']}")
            else:
                account = next((acc for acc in accounts if acc["id"] == args.account_id), None)
                if not account:
                    error(f"No YouTube account found with ID: {args.account_id}")
                    sys.exit(1)

            if verbose:
                info("Initializing YouTube...")
            youtube = YouTube(
                account["id"],
                account["nickname"],
                account["firefox_profile"],
                account["niche"],
                account["language"]
            )
            youtube.upload_video()
            if verbose:
                success("Uploaded Short.")
    else:
        error("Invalid Purpose, exiting...")
        sys.exit(1)

if __name__ == "__main__":
    main()
