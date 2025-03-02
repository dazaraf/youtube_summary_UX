import re
from yt_dlp import YoutubeDL
import requests

# Function to clean VTT-style captions
def clean_vtt_captions(subtitles_text):
    # Remove timestamps (e.g., 00:01:39.150 --> 00:01:41.560)
    cleaned_text = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}', '', subtitles_text)
    # Remove other metadata like "WEBVTT Kind: captions Language: en"
    cleaned_text = re.sub(r'WEBVTT.*?\n', '', cleaned_text, flags=re.DOTALL)
    # Remove empty lines and excessive spaces
    cleaned_text = re.sub(r'\n+', ' ', cleaned_text).strip()
    return cleaned_text

# YouTube URL
url = 'https://www.youtube.com/watch?v=2lAe1cqCOXo'  # Replace with your video URL

# yt-dlp options
ydl_opts = {
    'quiet': True,
    'writesubtitles': True,
    'subtitleslangs': ['en'],  # English subtitles
    'skip_download': True,
}

# Extract captions
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
    print(cleaned_captions)  # Final cleaned text output
else:
    print("No English captions found.")
