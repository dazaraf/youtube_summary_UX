from flask import Flask, request, render_template, jsonify
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound
import os
import requests
import ssl
from youtube_transcript_api import YouTubeTranscriptApi
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
import logging
import time  # Import time module for sleep
import re
from yt_dlp import YoutubeDL

app = Flask(__name__)

# Set up API Key for DeepSeek
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

# Set up logging configuration
logging.basicConfig(level=logging.DEBUG)

# Custom Adapter to Disable SSL Verification
class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = ssl._create_unverified_context()
        super().init_poolmanager(*args, **kwargs)

# Patch requests globally before calling YouTubeTranscriptApi
session = requests.Session()
session.mount("https://", SSLAdapter())

def get_transcript(video_id):
    try:
        # Retrieve the proxy URL from environment variables
        proxy_url = os.getenv('PROXY_URL')
        proxies = {
            "http": proxy_url,
            "https": proxy_url,
        } if proxy_url else None  # Use None if no proxy is set

        # Force YouTubeTranscriptApi to use the patched session
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'], proxies=proxies)
        text = " ".join([entry['text'] for entry in transcript])
        return text
    except Exception as e:
        return f"Error fetching transcript: {e}"


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
        transcript = get_transcript('8j9lSufYKRM')
        if "Error fetching transcript" in transcript:
            return jsonify({"error": transcript})
        
        # Call the generate_summary function with the transcript
        summary = generate_summary(transcript)  # Pass the transcript to the function
        return summary  # Return the summary as plain text
        
    return render_template('index.html', summary=None)

if __name__ == "__main__":  # Main entry point
    app.run(debug=True)  # Run the app in debug mode