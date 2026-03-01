from datetime import datetime, timedelta, timezone
from typing import List, Optional
import feedparser
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi

class Transcript(BaseModel):
    text: str

class ChannelVideo(BaseModel):
    title: str
    url: str
    video_id: str
    published_at: datetime
    description: str
    transcript: Optional[str] = None

class YouTubeScraper:
    def __init__(self):
        self.proxy_config = None
        self.transcript_api = YouTubeTranscriptApi()

    def _get_rss_url(self, channel_id: str) -> str:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    def _extract_video_id(self, video_url: str) -> str:
        if "watch?v=" in video_url: return video_url.split("v=")[1].split("&")[0]
        if "shorts/" in video_url: return video_url.split("shorts/")[1].split("?")[0]
        return video_url.split("/")[-1]

    def get_transcript(self, video_id: str, languages: List[str] = ['id', 'en']) -> Optional[Transcript]:
        try:
            transcript = self.transcript_api.fetch(video_id, languages=languages)
            text = " ".join([snippet.text for snippet in transcript.snippets])
            return Transcript(text=text)
        except Exception as e:
            print(f"Error transcript {video_id}: {e}")
            return None

    def get_latest_videos(self, channel_id: str, hours: int = 24) -> List[ChannelVideo]:
        feed = feedparser.parse(self._get_rss_url(channel_id))
        if not feed.entries: return []
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        videos = []
        
        for entry in feed.entries:
            published_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            if published_time >= cutoff_time:
                videos.append(ChannelVideo(
                    title=entry.title,
                    url=entry.link,
                    video_id=self._extract_video_id(entry.link),
                    published_at=published_time,
                    description=entry.get("summary", "")
                ))
        return videos

    def scrape_channel(self, channel_id: str, hours: int = 24) -> List[ChannelVideo]:
        videos = self.get_latest_videos(channel_id, hours)
        for video in videos:
            # Perbaikan di sini: Tambahkan default languages
            ts = self.get_transcript(video.video_id, languages=['id', 'en'])
            video.transcript = ts.text if ts else None
        return videos
    
# if __name__ == "__main__":
#     scraper = YouTubeScraper()
#     transcript: Transcript = scraper.get_transcript("1QP4Ulu90sM", ['id', 'en'])
#     print(transcript.text)
#     channel_videos: List[ChannelVideo] = scraper.scrape_channel("UCn8U8GiaHZNP9pFKzl3Cwlg", hours=24)
#     print(channel_videos)

