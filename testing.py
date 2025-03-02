from youtube_transcript_api import YouTubeTranscriptApi

transcript = YouTubeTranscriptApi.get_transcript("_TESlF4ZqKw")
formatted_transcript = "\n".join(entry['text'] for entry in transcript)
print(formatted_transcript)