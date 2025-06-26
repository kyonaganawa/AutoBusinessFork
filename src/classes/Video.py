import re
import g4f
import json
import shutil
import requests
import assemblyai as aai
import ssl
import time

from utils import *
from cache import *
from .Tts import TTS
from config import *
from status import *
from uuid import uuid4
from constants import *
from typing import List
from moviepy.editor import *
from termcolor import colored
from moviepy.video.fx.all import crop
from moviepy.config import change_settings
from moviepy.video.tools.subtitles import SubtitlesClip
from datetime import datetime
from llm_utils import generate_response
from state import VideoState
from prompts import get_image_prompts_prompt

# Set ImageMagick Path
change_settings({"IMAGEMAGICK_BINARY": get_imagemagick_path()})

class Video:
    """
    Class for Video Generation.

    Steps to create a Video:
    1. Generate a topic
    2. Generate a script
    3. Generate metadata (Title, Description, Tags)
    4. Generate AI Image Prompts
    4. Generate Images based on generated Prompts
    5. Convert Text-to-Speech
    6. Show images each for n seconds, n: Duration of TTS / Amount of images
    7. Combine Concatenated Images with the Text-to-Speech
    """
    def __init__(self, niche: str, language: str, useG4F: bool = True, session_id: str = None) -> None:
        """
        Constructor for Video Class.

        Args:
            niche (str): The niche of the content.
            language (str): The language of the content.
            useG4F (bool, optional): Whether to use G4F for image generation. Defaults to True.
            session_id (str, optional): Existing session ID to resume from. Defaults to None.

        Returns:
            None
        """
        self.useG4F: bool = useG4F
        self._niche: str = niche
        self._language: str = language
        self.images = []
        
        # Initialize state management
        self.state_manager = VideoState()
        self.session_id = session_id or self.state_manager.create_video_session(niche, language)
        
        # If resuming from existing session, load saved data
        if session_id:
            session = self.state_manager.get_session(session_id)
            if session and session["data"]:
                if "topic" in session["data"]:
                    self.subject = session["data"]["topic"]["subject"]
                if "script" in session["data"]:
                    self.script = session["data"]["script"]["content"]
                if "metadata" in session["data"]:
                    self.metadata = session["data"]["metadata"]
                if "image_prompts" in session["data"]:
                    self.image_prompts = session["data"]["image_prompts"]["prompts"]
                if "images" in session["data"]:
                    self.images = session["data"]["images"]["paths"]
                if "tts" in session["data"]:
                    self.tts_path = session["data"]["tts"]["path"]

    @property
    def niche(self) -> str:
        """
        Getter Method for the niche.

        Returns:
            niche (str): The niche
        """
        return self._niche
    
    @property
    def language(self) -> str:
        """
        Getter Method for the language to use.

        Returns:
            language (str): The language
        """
        return self._language

    def generate_topic(self) -> str:
        """
        Generates a topic based on the niche.

        Returns:
            topic (str): The generated topic.
        """
        # Check if we already have a topic from a previous session
        session = self.state_manager.get_session(self.session_id)
        if session and "topic" in session["data"]:
            self.subject = session["data"]["topic"]["subject"]
            return self.subject

        completion = generate_response(f"Please generate a specific video idea that takes about the following topic: {self.niche}. Make it exactly one sentence. Only return the topic, nothing else.")

        if not completion:
            error("Failed to generate Topic.")
            self.state_manager.mark_failed(self.session_id, "Failed to generate topic")
            return None

        self.subject = completion
        
        # Save the generated topic
        self.state_manager.save_step_result(self.session_id, "topic", {
            "subject": self.subject
        })

        return completion

    def generate_script(self) -> str:
        """
        Generate a script for a video, depending on the subject of the video, the number of paragraphs, and the AI model.

        Returns:
            script (str): The script of the video.
        """
        # Check if we already have a script from a previous session
        session = self.state_manager.get_session(self.session_id)
        if session and "script" in session["data"]:
            self.script = session["data"]["script"]["content"]
            return self.script

        sentence_length = get_script_sentence_length()
        prompt = f"""
        Generate a script for a video in {sentence_length} sentences, depending on the subject of the video.

        The script is to be returned as a string with the specified number of paragraphs.

        Here is an example of a string:
        "This is an example string."

        Do not under any circumstance reference this prompt in your response.

        Get straight to the point, don't start with unnecessary things like, "welcome to this video".

        Obviously, the script should be related to the subject of the video.
        
        YOU MUST NOT EXCEED THE {sentence_length} SENTENCES LIMIT. MAKE SURE THE {sentence_length} SENTENCES ARE SHORT.
        YOU MUST NOT INCLUDE ANY TYPE OF MARKDOWN OR FORMATTING IN THE SCRIPT, NEVER USE A TITLE.
        YOU MUST WRITE THE SCRIPT IN THE LANGUAGE SPECIFIED IN [LANGUAGE].
        ONLY RETURN THE RAW CONTENT OF THE SCRIPT. DO NOT INCLUDE "VOICEOVER", "NARRATOR" OR SIMILAR INDICATORS OF WHAT SHOULD BE SPOKEN AT THE BEGINNING OF EACH PARAGRAPH OR LINE. YOU MUST NOT MENTION THE PROMPT, OR ANYTHING ABOUT THE SCRIPT ITSELF. ALSO, NEVER TALK ABOUT THE AMOUNT OF PARAGRAPHS OR LINES. JUST WRITE THE SCRIPT
        
        Subject: {self.subject}
        Language: {self.language}
        """
        completion = generate_response(prompt)

        # Apply regex to remove *
        completion = re.sub(r"\*", "", completion)
        
        if not completion:
            error("The generated script is empty.")
            self.state_manager.mark_failed(self.session_id, "Failed to generate script")
            return None
        
        if len(completion) > 5000:
            if get_verbose():
                warning("Generated Script is too long. Retrying...")
            return self.generate_script()
        
        self.script = completion
        
        # Save the generated script
        self.state_manager.save_step_result(self.session_id, "script", {
            "content": self.script
        })
    
        return completion

    def generate_metadata(self) -> dict:
        """
        Generates Video metadata (Title, Description).

        Returns:
            metadata (dict): The generated metadata.
        """
        # Check if we already have metadata from a previous session
        session = self.state_manager.get_session(self.session_id)
        if session and "metadata" in session["data"]:
            self.metadata = session["data"]["metadata"]
            return self.metadata

        title = generate_response(f"Please generate a Video Title for the following subject, including hashtags: {self.subject}. Only return the title, nothing else. Limit the title under 100 characters.")

        if len(title) > 100:
            if get_verbose():
                warning("Generated Title is too long. Retrying...")
            return self.generate_metadata()

        description = generate_response(f"Please generate a Video Description for the following script: {self.script}. Only return the description, nothing else.")
        
        self.metadata = {
            "title": title,
            "description": description
        }
        
        # Save the generated metadata
        self.state_manager.save_step_result(self.session_id, "metadata", self.metadata)

        return self.metadata
    
    def generate_prompts(self) -> List[str]:
        """
        Generates AI Image Prompts based on the provided Video Script.

        Returns:
            image_prompts (List[str]): Generated List of image prompts.
        """
        # Check if we already have prompts from a previous session
        session = self.state_manager.get_session(self.session_id)
        if session and "image_prompts" in session["data"]:
            self.image_prompts = session["data"]["image_prompts"]["prompts"]
            return self.image_prompts

        # Calculate number of prompts based on script length
        base_n_prompts = len(self.script) / 3

        # If using G4F, limit to 25 prompts
        if self.useG4F:
            n_prompts = min(base_n_prompts, 10)
        else:
            n_prompts = base_n_prompts

        # Get the prompt from prompts.py
        prompt = get_image_prompts_prompt(
            n_prompts=int(n_prompts),
            subject=self.subject,
            script=self.script
        )

        completion = str(generate_response(prompt, model=parse_model(get_image_prompt_llm())))\
            .replace("```json", "") \
            .replace("```", "")

        image_prompts = []

        if "image_prompts" in completion:
            image_prompts = json.loads(completion)["image_prompts"]
        else:
            try:
                image_prompts = json.loads(completion)
                if get_verbose():
                    info(f" => Generated Image Prompts: {image_prompts}")
            except Exception:
                if get_verbose():
                    warning("GPT returned an unformatted response. Attempting to clean...")

                # Get everything between [ and ], and turn it into a list
                r = re.compile(r"\[.*\]")
                image_prompts = r.findall(completion)
                if len(image_prompts) == 0:
                    if get_verbose():
                        warning("Failed to generate Image Prompts. Retrying...")
                    return self.generate_prompts()

        # Limit prompts to max allowed amount
        if self.useG4F:
            image_prompts = image_prompts[:25]
        elif len(image_prompts) > n_prompts:
            image_prompts = image_prompts[:int(n_prompts)]

        self.image_prompts = image_prompts
        
        # Save the generated prompts
        self.state_manager.save_step_result(self.session_id, "image_prompts", {
            "prompts": self.image_prompts
        })

        success(f"Generated {len(image_prompts)} Image Prompts.")

        return image_prompts

    def generate_image_g4f(self, prompt: str, max_retries: int = 3) -> str:
        """
        Generates an AI Image using G4F with SDXL Turbo.

        Args:
            prompt (str): Reference for image generation
            max_retries (int, optional): Maximum number of retry attempts. Defaults to 3.

        Returns:
            path (str): The path to the generated image.
        """
        print(f"Generating Image using G4F: {prompt}")
        
        # Create an unverified SSL context for requests
        ssl._create_default_https_context = ssl._create_unverified_context
        
        for attempt in range(max_retries):
            try:
                from g4f.client import Client
                
                client = Client()
                response = client.images.generate(
                    model="sdxl-turbo",
                    prompt=prompt,
                    response_format="url",
                    timeout=60
                )
                
                if response and response.data and len(response.data) > 0:
                    # Download image from URL
                    image_url = response.data[0].url
                    
                    try:
                        image_response = requests.get(image_url, verify=False, timeout=30)
                        
                        if image_response.status_code == 200:
                            # Generate a unique filename
                            image_filename = f"{str(uuid4())}.png"
                            
                            # Save in temporary directory for video processing
                            temp_path = os.path.join(ROOT_DIR, ".mp", image_filename)
                            with open(temp_path, "wb") as image_file:
                                image_file.write(image_response.content)
                            
                            # Save in permanent images directory
                            permanent_path = os.path.join(ROOT_DIR, "images", image_filename)
                            with open(permanent_path, "wb") as image_file:
                                image_file.write(image_response.content)
                            
                            if get_verbose():
                                info(f" => Downloaded Image from {image_url}")
                                info(f" => Saved temporarily to: {temp_path}")
                                info(f" => Saved permanently to: {permanent_path}\n")
                            
                            self.images.append(temp_path)
                            
                            # Save the generated image path
                            session = self.state_manager.get_session(self.session_id)
                            current_paths = session["data"].get("images", {}).get("paths", []) if session else []
                            current_paths.append(temp_path)
                            self.state_manager.save_step_result(self.session_id, "images", {
                                "paths": current_paths
                            })
                            
                            return temp_path
                        else:
                            if get_verbose():
                                warning(f"Failed to download image from URL: {image_url} (Status: {image_response.status_code})")
                    except requests.exceptions.RequestException as e:
                        if get_verbose():
                            warning(f"Failed to download image: {str(e)}")
                else:
                    if get_verbose():
                        warning("Failed to generate image using G4F - no data in response")
                    
            except Exception as e:
                if get_verbose():
                    warning(f"Failed to generate image using G4F: {str(e)}")
            
            if attempt < max_retries - 1:
                if get_verbose():
                    warning(f"Image generation attempt {attempt + 1} failed, retrying in 5 seconds...")
                time.sleep(5)
                
        error("Failed to generate image after maximum retries")
        return None

    def generate_image_cloudflare(self, prompt: str, worker_url: str) -> str:
        """
        Generates an AI Image using Cloudflare worker.

        Args:
            prompt (str): Reference for image generation
            worker_url (str): The Cloudflare worker URL

        Returns:
            path (str): The path to the generated image.
        """
        print(f"Generating Image using Cloudflare: {prompt}")

        url = f"{worker_url}?prompt={prompt}&model=sdxl"
        
        response = requests.get(url)
        
        if response.headers.get('content-type') == 'image/png':
            # Generate a unique filename
            image_filename = f"{str(uuid4())}.png"
            
            # Save in temporary directory for video processing
            temp_path = os.path.join(ROOT_DIR, ".mp", image_filename)
            with open(temp_path, "wb") as image_file:
                image_file.write(response.content)
            
            # Save in permanent images directory
            permanent_path = os.path.join(ROOT_DIR, "images", image_filename)
            with open(permanent_path, "wb") as image_file:
                image_file.write(response.content)
            
            if get_verbose():
                info(f" => Generated Image from Cloudflare")
                info(f" => Saved temporarily to: {temp_path}")
                info(f" => Saved permanently to: {permanent_path}\n")
            
            self.images.append(temp_path)
            
            return temp_path
        else:
            if get_verbose():
                warning("Failed to generate image. The response was not a PNG image.")
            return None

    def generate_image(self, prompt: str) -> str:
        """
        Generates an AI Image based on the given prompt.

        Args:
            prompt (str): Reference for image generation

        Returns:
            path (str): The path to the generated image.
        """

        # Check if using G4F or Cloudflare
        if self.useG4F:
            return self.generate_image_g4f(prompt)
        else:
            worker_url = account_config.get("worker_url")
            if not worker_url:
                error("Cloudflare worker URL not configured for this account")
                return None
            return self.generate_image_cloudflare(prompt, worker_url)

    def generate_script_to_speech(self, tts_instance: TTS) -> str:
        """
        Converts the generated script into Speech using CoquiTTS and returns the path to the wav file.

        Args:
            tts_instance (tts): Instance of TTS Class.

        Returns:
            path_to_wav (str): Path to generated audio (WAV Format).
        """
        # Check if we already have TTS from a previous session
        session = self.state_manager.get_session(self.session_id)
        if session and "tts" in session["data"]:
            self.tts_path = session["data"]["tts"]["path"]
            return self.tts_path

        path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".wav")

        # Clean script, remove every character that is not a word character, a space, a period, a question mark, or an exclamation mark.
        self.script = re.sub(r'[^\w\s.?!]', '', self.script)

        tts_instance.synthesize(self.script, path)

        self.tts_path = path
        
        # Save the generated TTS path
        self.state_manager.save_step_result(self.session_id, "tts", {
            "path": self.tts_path
        })

        if get_verbose():
            info(f" => Wrote TTS to \"{path}\"")

        return path

    def generate_subtitles(self, audio_path: str) -> str:
        """
        Generates subtitles for the audio using AssemblyAI.

        Args:
            audio_path (str): The path to the audio file.

        Returns:
            path (str): The path to the generated SRT File.
        """
        # Turn the video into audio
        aai.settings.api_key = get_assemblyai_api_key()
        config = aai.TranscriptionConfig()
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(audio_path)
        subtitles = transcript.export_subtitles_srt()

        srt_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".srt")

        with open(srt_path, "w") as file:
            file.write(subtitles)

        return srt_path

    def combine(self) -> str:
        """
        Combines everything into the final video.

        Returns:
            path (str): The path to the generated MP4 File.
        """
        combined_image_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".mp4")
        threads = get_threads()
        tts_clip = AudioFileClip(self.tts_path)
        max_duration = tts_clip.duration
        
        # Filter out invalid image paths
        valid_images = []
        for image_path in self.images:
            if not os.path.exists(image_path):
                if get_verbose():
                    warning(f"Image not found, skipping: {image_path}")
                continue
            try:
                # Try to create the clip to validate the image
                test_clip = ImageClip(image_path)
                valid_images.append(image_path)
            except Exception as e:
                if get_verbose():
                    warning(f"Failed to create clip for image {image_path}: {str(e)}")
                continue
        
        if not valid_images:
            error("No valid images found to create video")
            self.state_manager.mark_failed(self.session_id, "No valid images found to create video")
            return None
            
        req_dur = max_duration / len(valid_images)

        # Make a generator that returns a TextClip when called with consecutive
        generator = lambda txt: TextClip(
            txt,
            font=os.path.join(get_fonts_dir(), get_font()),
            fontsize=100,
            color="#FFFF00",
            stroke_color="black",
            stroke_width=5,
            size=(1080, 1920),
            method="caption",
        )

        print(colored("[+] Combining images...", "blue"))

        clips = []
        tot_dur = 0
        # Add downloaded clips over and over until the duration of the audio (max_duration) has been reached
        while tot_dur < max_duration:
            for image_path in valid_images:
                try:
                    clip = ImageClip(image_path)
                    clip.duration = req_dur
                    clip = clip.set_fps(30)

                    # Not all images are same size,
                    # so we need to resize them
                    if round((clip.w/clip.h), 4) < 0.5625:
                        if get_verbose():
                            info(f" => Resizing Image: {image_path} to 1080x1920")
                        clip = crop(clip, width=clip.w, height=round(clip.w/0.5625), \
                                    x_center=clip.w / 2, \
                                    y_center=clip.h / 2)
                    else:
                        if get_verbose():
                            info(f" => Resizing Image: {image_path} to 1920x1080")
                        clip = crop(clip, width=round(0.5625*clip.h), height=clip.h, \
                                    x_center=clip.w / 2, \
                                    y_center=clip.h / 2)
                    clip = clip.resize((1080, 1920))

                    # FX (Fade In)
                    #clip = clip.fadein(2)

                    clips.append(clip)
                    tot_dur += clip.duration
                except Exception as e:
                    if get_verbose():
                        warning(f"Failed to process image {image_path}: {str(e)}")
                    continue

        if not clips:
            error("Failed to create any valid video clips")
            self.state_manager.mark_failed(self.session_id, "Failed to create any valid video clips")
            return None

        final_clip = concatenate_videoclips(clips)
        final_clip = final_clip.set_fps(30)
        
        # Get a random background song
        random_song = choose_random_song()
        
        subtitles_path = self.generate_subtitles(self.tts_path)

        # Equalize srt file
        equalize_subtitles(subtitles_path, 10)
        
        # Burn the subtitles into the video
        subtitles = SubtitlesClip(subtitles_path, generator)
        subtitles.set_pos(("center", "center"))

        # Create audio composition
        audio_clips = [tts_clip.set_fps(44100)]
        
        # Add background music if a valid song was found
        if random_song:
            try:
                random_song_clip = AudioFileClip(random_song).set_fps(44100)
                # Turn down volume
                random_song_clip = random_song_clip.fx(afx.volumex, 0.1)
                audio_clips.append(random_song_clip)
            except Exception as e:
                if get_verbose():
                    warning(f"Failed to load background song: {str(e)}")
        elif get_verbose():
            warning("No valid background song found, continuing without background music")
            
        comp_audio = CompositeAudioClip(audio_clips)

        final_clip = final_clip.set_audio(comp_audio)
        final_clip = final_clip.set_duration(tts_clip.duration)

        # Add subtitles
        final_clip = CompositeVideoClip([
            final_clip,
            subtitles
        ])

        final_clip.write_videofile(combined_image_path, threads=threads)

        # Save video to permanent directory
        video_name = os.path.basename(combined_image_path)
        permanent_path = os.path.join(ROOT_DIR, "videos", video_name)
        shutil.copy2(combined_image_path, permanent_path)
        
        if get_verbose():
            success(f"Wrote Video to \"{combined_image_path}\"")
            success(f"Saved permanently to \"{permanent_path}\"")

        self.video_path = os.path.abspath(permanent_path)
        
        # Mark the session as completed
        self.state_manager.mark_completed(self.session_id, self.video_path)
        
        return permanent_path

    def generate_video(self, tts_instance: TTS) -> str:
        """
        Generates a Video based on the provided niche and language.

        Args:
            tts_instance (TTS): Instance of TTS Class.

        Returns:
            path (str): The path to the generated MP4 File.
        """
        try:
            # Check if we already have all images from a previous session
            session = self.state_manager.get_session(self.session_id)
            has_all_images = False
            if session and "images" in session["data"]:
                image_paths = session["data"]["images"].get("paths", [])
                # Check if we have all images (one for each prompt)
                if len(image_paths) == len(self.image_prompts or []):
                    has_all_images = True
                    self.images = image_paths
                    if get_verbose():
                        info(" => Loaded existing images from previous session")

            # Generate the Topic
            self.generate_topic()

            # Generate the Script
            self.generate_script()

            # Generate the Metadata
            self.generate_metadata()

            # Generate the Image Prompts
            self.generate_prompts()

            # Generate the Images if not already generated
            if not has_all_images:
                for prompt in self.image_prompts:
                    self.generate_image(prompt)
                
                # Save state after all images are generated
                self.state_manager.save_step_result(self.session_id, "images", {
                    "paths": self.images,
                    "completed": True
                })
                if get_verbose():
                    info(f" => Generated and saved {len(self.images)} images")

            # Generate the TTS
            self.generate_script_to_speech(tts_instance)

            # Combine everything
            path = self.combine()

            if get_verbose():
                info(f" => Generated Video: {path}")

            return path
        except Exception as e:
            error_msg = f"Failed to generate video: {str(e)}"
            self.state_manager.mark_failed(self.session_id, error_msg)
            if get_verbose():
                error(error_msg)
            return None 