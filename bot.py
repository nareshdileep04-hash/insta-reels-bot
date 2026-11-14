import os
import json
import time
import asyncio
import random
import requests
import edge_tts
from moviepy.editor import VideoFileClip, AudioFileClip

PIXABAY_KEY = os.environ["PIXABAY_API_KEY"]
IG_TOKEN = os.environ["IG_ACCESS_TOKEN"]
IG_USER_ID = os.environ["IG_USER_ID"]
LOG_FILE = "analytics_log.json"

# Pre-written viral scripts tailored for your jewelry boxes, displays, and tools
JEWELRY_SCRIPTS = [
    {
        "search_keyword": "velvet jewelry box",
        "voiceover": "Stop storing your precious gold and diamond jewelry in random plastic bags. Elevate your collection with our premium velvet jewelry boxes designed to prevent scratches, tangles, and tarnish. Give your jewelry the luxury home it truly deserves today.",
        "caption": "Protect your precious collection in style! ✨ Luxury velvet jewelry boxes now available. DM to order! #JewelryBox #JewelryStorage #LuxuryPackaging #JewelryDisplay #GoldJewelry"
    },
    {
        "search_keyword": "jewelry display tray",
        "voiceover": "Running a jewelry store or setting up an exhibition? Showcase your rings, earrings, and necklaces like a high-end boutique using our sleek display trays. Elegant organization that instantly catches your customers eyes.",
        "caption": "Elegance meets perfection in every display. 💎 Shop professional display trays for your store or studio. #JewelryDisplay #StoreDesign #JewelryShowcase #DisplayTrays #JewelryTools"
    },
    {
        "search_keyword": "goldsmith melting furnace",
        "voiceover": "Take your jewelry crafting to the next level with our professional-grade melting furnaces and precision cutting tools. Safe, efficient, and built for serious goldsmiths and modern artisans.",
        "caption": "Built for precision and performance. 🔥 Explore professional jewelry making tools and melting furnaces with us! #GoldsmithTools #MeltingFurnace #JewelryMaking #Craftsman #JewelryStudio"
    }
]

def generate_script():
    # Randomly select a high-performing script for your jewelry business
    return random.choice(JEWELRY_SCRIPTS)

async def make_voiceover(text, output_audio="voice.mp3"):
    communicate = edge_tts.Communicate(text, "en-IN-PrabhatNeural", rate="+5%")
    await communicate.save(output_audio)

def download_stock_video(keyword, output_video="bg.mp4"):
    query = requests.utils.quote(keyword)
    url = f"https://pixabay.com/api/videos/?key={PIXABAY_KEY}&q={query}&per_page=5"
    res = requests.get(url).json()
    
    if not res.get("hits"):
        res = requests.get(f"https://pixabay.com/api/videos/?key={PIXABAY_KEY}&q=jewelry&per_page=5").json()
        
    videos = res["hits"][0]["videos"]
    video_url = videos.get("large", videos.get("medium"))["url"]
    with open(output_video, "wb") as f:
        f.write(requests.get(video_url).content)

def assemble_reel(voice_path="voice.mp3", bg_path="bg.mp4", final_path="final_reel.mp4"):
    audio = AudioFileClip(voice_path)
    duration = audio.duration + 0.5
    video = VideoFileClip(bg_path).without_audio()
    
    if video.duration < duration:
        video = video.loop(duration=duration)
    video = video.subclip(0, duration).resize(height=1920)
    video = video.crop(x_center=video.w/2, width=1080, height=1920)
    video = video.set_audio(audio)
    
    video.write_videofile(
        final_path, 
        fps=24, 
        codec="libx264", 
        audio_codec="aac", 
        audio_fps=44100,
        preset="medium",
        ffmpeg_params=["-movflags", "+faststart"]
    )

def upload_temp_host(file_path="final_reel.mp4"):
    with open(file_path, "rb") as f:
        res = requests.post("https://tmpfiles.org/api/v1/upload", files={"file": f}).json()
    raw_url = res["data"]["url"]
    return raw_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")

def post_to_instagram(video_url, caption):
    base = f"https://graph.facebook.com/v21.0/{IG_USER_ID}"
    container = requests.post(f"{base}/media", data={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": IG_TOKEN
    }).json()
    print("Container Response:", container)
    creation_id = container["id"]
    
    is_finished = False
    for _ in range(20):
        status = requests.get(f"https://graph.facebook.com/v21.0/{creation_id}", params={
            "fields": "status_code,status", "access_token": IG_TOKEN
        }).json()
        print("Status Check:", status)
        
        code = status.get("status_code")
        if code == "FINISHED":
            is_finished = True
            break
        elif code == "ERROR":
            raise Exception(f"Video Processing Error from Meta: {status}")
            
        time.sleep(15)
        
    if not is_finished:
        raise Exception("Video processing timed out on Instagram servers.")
        
    pub = requests.post(f"{base}/media_publish", data={
        "creation_id": creation_id, "access_token": IG_TOKEN
    }).json()
    print("Publish Response:", pub)
    
    if "id" not in pub:
        raise Exception(f"Publish Error: {pub}")
        
    return pub["id"]



def track_analytics(new_media_id, topic):
    logs = json.load(open(LOG_FILE)) if os.path.exists(LOG_FILE) else []
    for item in logs:
        mid = item["media_id"]
        stats = requests.get(f"https://graph.facebook.com/v21.0/{mid}/insights", params={
            "metric": "plays,reach,likes,comments,shares",
            "access_token": IG_TOKEN
        }).json()
        if "data" in stats:
            item["metrics"] = {m["name"]: m["values"][0]["value"] for m in stats["data"]}
            
    logs.append({"media_id": new_media_id, "topic": topic, "timestamp": time.ctime(), "metrics": {}})
    with open(LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2)

if __name__ == "__main__":
    print("1. Selecting script...")
    data = generate_script()
    print("2. Creating voiceover...")
    asyncio.run(make_voiceover(data["voiceover"]))
    print("3. Downloading stock footage from Pixabay...")
    download_stock_video(data["search_keyword"])
    print("4. Rendering 1080x1920 Reel...")
    assemble_reel()
    print("5. Uploading & Publishing to Instagram...")
    public_url = upload_temp_host()
    media_id = post_to_instagram(public_url, data["caption"])
    print(f"6. Published! Media ID: {media_id}. Updating analytics...")
    track_analytics(media_id, data["search_keyword"])
