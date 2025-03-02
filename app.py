from flask import Flask, request, render_template, jsonify
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound
import os
import requests
import logging
import time  # Import time module for sleep
import re
# Add pytube import at the top to ensure it's available
try:
    from pytube import YouTube
    logging.info("Successfully imported pytube")
except ImportError as e:
    logging.error(f"Failed to import pytube: {str(e)}")

app = Flask(__name__)

# Set up API Key for DeepSeek
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

# Set up logging configuration
logging.basicConfig(level=logging.DEBUG)

def get_transcript(video_id):
    try:
        # Log the attempt
        logging.info(f"Attempting to get transcript for video ID: {video_id}")
        
        # Try to get available transcript languages first
        available_transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
        logging.info(f"Available transcripts: {[t.language_code for t in available_transcripts]}")
        
        # First try to get English transcript if available
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
            logging.info("Successfully retrieved English transcript")
        except:
            # If English fails, get the first available transcript
            logging.info("English transcript not available, getting first available")
            transcript_list = list(available_transcripts)
            if transcript_list:
                first_transcript = transcript_list[0].fetch()
                transcript = first_transcript
            else:
                raise NoTranscriptFound("No transcripts available")
        
        formatted_transcript = "\n".join(entry['text'] for entry in transcript)
        return formatted_transcript
    except NoTranscriptFound:
        logging.error(f"No transcript found for video ID: {video_id}. Subtitles may be disabled.")
        return "Could not retrieve a transcript for the video! This is most likely caused by subtitles being disabled for this video."
    except Exception as e:
        logging.error(f"An error occurred while retrieving the transcript: {str(e)}")
        # More detailed error logging
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        return f"An error occurred: {str(e)}"
    
# And implement this fallback function
def get_transcript_with_fallback(video_id):
    try:
        # First try with youtube_transcript_api
        return get_transcript(video_id)
    except Exception as e:
        logging.warning(f"Primary transcript method failed: {str(e)}, trying fallback...")
        try:
            # Fallback to pytube
            from pytube import YouTube
            
            # Get the YouTube video
            yt = YouTube(f"https://www.youtube.com/watch?v={video_id}")
            
            # Check if captions are available
            if yt.captions and len(yt.captions) > 0:
                # Get English captions if available, otherwise use the first available
                caption_track = yt.captions.get('en', yt.captions.get('a.en', next(iter(yt.captions.values()))))
                
                # Get the caption track XML
                caption_xml = caption_track.xml_captions
                
                # Basic parsing of XML to get text (could be improved)
                text_content = re.sub(r'<.*?>', '', caption_xml)
                
                logging.info("Successfully retrieved transcript using fallback method")
                return text_content
            else:
                logging.error("No captions available via fallback method")
                return "No transcript available for this video using either method."
        except Exception as fallback_error:
            logging.error(f"Fallback transcript method also failed: {str(fallback_error)}")
            return f"Failed to retrieve transcript via both methods. Error: {str(e)} | Fallback error: {str(fallback_error)}"

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