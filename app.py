from flask import Flask, request, render_template, jsonify
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound
import os
import requests
import logging
import time  # Import time module for sleep
import re
from yt_dlp import YoutubeDL

app = Flask(__name__)

# Set up API Key for DeepSeek
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

# Set up logging configuration
logging.basicConfig(level=logging.DEBUG)

def get_transcript(video_id):
    try:
        # YouTube URL
        url = f"https://www.youtube.com/watch?v={video_id}"

        # yt-dlp options
        ydl_opts = {
            'quiet': True,
            'writesubtitles': True,
            'subtitleslangs': ['en'],  # English subtitles
            'skip_download': True,
        }

        # Extract captions using yt-dlp
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            subtitles = info_dict.get('subtitles', {}).get('en', [])
            automatic_captions = info_dict.get('automatic_captions', {}).get('en', [])

        # Get the best available English captions
        subtitle_url = None
        if subtitles:
            subtitle_url = subtitles[-1]['url']
        elif automatic_captions:
            subtitle_url = automatic_captions[-1]['url']

        # Fetch and clean the captions
        if subtitle_url:
            response = requests.get(subtitle_url)
            raw_captions = response.text
            cleaned_captions = clean_vtt_captions(raw_captions)
            logging.info("Successfully retrieved transcript using yt-dlp")
            return cleaned_captions
        else:
            logging.error("No English captions found via yt-dlp")
            return "No transcript available for this video using yt-dlp."
    except Exception as e:
        logging.error(f"An error occurred while retrieving the transcript with yt-dlp: {str(e)}")
        return f"An error occurred: {str(e)}"

# Update the fallback function to remove pytube references
def get_transcript_with_fallback(video_id):
    try:
        # First try with youtube_transcript_api
        return get_transcript(video_id)
    except Exception as e:
        logging.warning(f"Primary transcript method failed: {str(e)}, trying fallback...")
        # Fallback to yt-dlp (already implemented in get_transcript)
        return get_transcript(video_id)  # Reuse the same function

def format_summary(summary_text):
    # Replace Markdown bold syntax with HTML tags
    formatted_text = summary_text.replace("**", "<strong>").replace("**", "</strong>")
    
    # Add line breaks for better readability
    formatted_text = formatted_text.replace("\n", "<br>")  # Replace newlines with <br> tags
    
    # Optionally, you can add headings based on keywords or structure
    # For example, if you have specific keywords for sections, you can replace them with <h2> tags
    formatted_text = formatted_text.replace("Key Takeaways:", "<h2>Key Takeaways:</h2>")
    
    return formatted_text

def generate_summary(input_content=None):
    if not DEEPSEEK_API_KEY:
        logging.error("DeepSeek API key not found.")
        return "DeepSeek API key not found."
    
    system_prompt = "You are a summarization agent designed to create a powerful, engaging, and chronological summary of a video transcription. Keep it concise, social-media friendly, and exciting."
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Summarize the following text: \n{input_content}"}
        ],
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
    logging.debug("Sending request to DeepSeek API with payload: %s", payload)

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload)
            logging.debug("Received response status: %s", response.status_code)
            logging.debug("Received response text: %s", response.text)  # Log the raw response text
            
            if response.status_code != 200:
                logging.error("Error from DeepSeek API: %s - %s", response.status_code, response.text)
                return f"API error: {response.status_code} - {response.text}"
            
            if not response.text:
                logging.error("Received empty response from DeepSeek API. Attempt %d of %d.", attempt + 1, max_attempts)
                time.sleep(5)  # Wait for 5 seconds before retrying
                continue  # Retry the request
            
            response_data = response.json()
            summary = response_data['choices'][0]['message']['content']
            
            # Format the summary before returning
            return format_summary(summary)
        
        except Exception as e:
            logging.error("Exception occurred: %s", str(e))
            return "An error occurred while calling the API."
    
    return "Error: Received empty response from API after multiple attempts."

def extract_video_id(video_url):
    # Use regex to extract the video ID from the URL
    match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11})', video_url)
    if match:
        return match.group(1)
    return None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        video_url = request.form['video_url'].strip()  # Strip whitespace
        video_id = extract_video_id(video_url)  # Extract video ID
        
        if not video_id:
            return jsonify({"error": "Invalid YouTube URL format"})
        
        # Call the get_transcript function to get the transcript text
        transcript = get_transcript(video_id)
        if "An error occurred" in transcript:
            return jsonify({"error": transcript})
        
        # Call the generate_summary function with the transcript
        summary = generate_summary(transcript)  # Pass the transcript to the function
        return summary  # Return the summary as plain text
        
    return render_template('index.html', summary=None)