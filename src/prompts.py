"""
Collection of prompts used for content generation.
Each prompt is designed for a specific purpose and can be formatted with variables.
"""

def get_image_prompts_prompt(n_prompts: int, subject: str, script: str) -> str:
    """Get the prompt for generating AI image prompts.
    
    Args:
        n_prompts: Number of image prompts to generate
        subject: The subject/topic of the video
        script: The full script text for context
        
    Returns:
        The formatted prompt string
    """
    return f"""
    Generate {n_prompts} Image Prompts for AI Image Generation,
    depending on the subject of a video.
    Subject: {subject}

    The image prompts are to be returned as
    a JSON-Array of strings.

    Each search term should consist of a full sentence,
    always add the main subject of the video.

    Be emotional and use interesting adjectives to make the
    Image Prompt as detailed as possible.
    
    YOU MUST ONLY RETURN THE JSON-ARRAY OF STRINGS.
    YOU MUST NOT RETURN ANYTHING ELSE. 
    YOU MUST NOT RETURN THE SCRIPT.
    
    The search terms must be related to the subject of the video.
    Here is an example of a JSON-Array of strings:
    ["image prompt 1", "image prompt 2", "image prompt 3"]

    For context, here is the full text:
    {script}
    """ 