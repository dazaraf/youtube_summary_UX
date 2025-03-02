from youtube_transcript_api import YouTubeTranscriptApi

# Function to extract captions
def get_youtube_transcript(video_id, lang='en'):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
        text = " ".join([entry['text'] for entry in transcript])  # Combine all text
        return text
    except Exception as e:
        return f"Error fetching transcript: {e}"

# Example: Extract transcript
video_id = "2lAe1cqCOXo"  # Replace with your video ID
captions_text = get_youtube_transcript(video_id)
print(captions_text)
