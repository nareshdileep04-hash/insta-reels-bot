import os
import glob
import subprocess
import time
import requests
import google.generativeai as genai
from moviepy.editor import ImageClip, AudioFileClip

# Configure Gemini API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

def generate_ai_caption(product_name="jewelry item"):
    print("Generating unique caption with Gemini...")
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Write a short, trendy, highly engaging Instagram Reel caption with emojis and relevant hashtags for a stunning new {product_name}. Make it punchy and viral-style."
        response = model.generate_content(prompt)
        caption = response.text.strip()
        print("Generated Caption:", caption)
        return caption
    except Exception as e:
        print(f"Gemini caption generation failed ({e}), using default caption.")
        return "Check out this stunning new arrival! ✨ #Reels #Trending #JewelryGoals"

def assemble_reel(final_path="final_reel.mp4"):
    print("Searching for product images in products/ folder...")
    image_files = glob.glob("products/*.jpg") + glob.glob("products/*.png") + glob.glob("products/*.jpeg")
    
    if not image_files:
        raise Exception("No product images found in the 'products/' folder! Please upload at least one image.")
    
    # Sort files by upload time to pick the most recent one automatically
    image_files.sort(key=os.path.getmtime, reverse=True)
    product_image = image_files[0]
    print(f"Using the latest product image: {product_image}")
    
    audio_path = "voice.mp3"
    if os.path.exists(audio_path):
        audio = AudioFileClip(audio_path)
        duration = audio.duration + 0.5
    else:
        duration = 7.0
        audio = None

    # Format into a 9:16 vertical Reel (720x1280)
    clip = ImageClip(product_image).set_duration(duration)
    clip = clip.resize(height=1280)
    clip = clip.crop(x_center=clip.w/2, width=720, height=1280)
    
    if audio:
        clip = clip.set_audio(audio)
        
    clip.write_videofile(
        final_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        bitrate="1500k",
        ffmpeg_params=["-movflags", "+faststart"]
    )
    print("Moviepy - video ready:", final_path)

def upload_temp_host(file_path="final_reel.mp4"):
    print("Committing and pushing video to GitHub for Pages hosting...")
    repo = os.environ.get("GITHUB_REPOSITORY")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    token = os.environ.get("GITHUB_TOKEN")
    
    parts = repo.split("/")
    username = parts[0]
    repo_name = parts[1]
    
    subprocess.run(["git", "config", "--global", "user.name", "github-actions[bot]"], check=True)
    subprocess.run(["git", "config", "--global", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
    
    subprocess.run(["git", "add", file_path], check=True)
    subprocess.run(["git", "commit", "-m", "Auto-commit dynamic product reel for Pages"], check=True)
    
    remote_url = f"https://x-access-token:{token}@github.com/{repo}.git"
    subprocess.run(["git", "push", remote_url, branch], check=True)
    
    pages_url = f"https://{username}.github.io/{repo_name}/{file_path}"
    print("GitHub Pages Video URL:", pages_url)
    
    print("Waiting 10 seconds for GitHub Pages CDN sync...")
    time.sleep(10)
    
    return pages_url

def post_to_instagram(public_url):
    ig_user_id = os.environ.get("IG_USER_ID")
    access_token = os.environ.get("IG_ACCESS_TOKEN")
    
    # Dynamically generate unique caption via Gemini
    caption = generate_ai_caption()
    
    print("1. Creating container...")
    container_url = f"https://graph.facebook.com/v18.0/{ig_user_id}/media"
    payload = {
        "media_type": "REELS",
        "video_url": public_url,
        "caption": caption,
        "access_token": access_token
    }
    r = requests.post(container_url, data=payload)
    res = r.json()
    if "id" not in res:
        raise Exception(f"Container Creation Failed: {res}")
    
    creation_id = res["id"]
    print("Container ID:", creation_id)
    
    print("2. Publishing to Instagram...")
    publish_url = f"https://graph.facebook.com/v18.0/{ig_user_id}/media_publish"
    pub_payload = {
        "creation_id": creation_id,
        "access_token": access_token
    }
    pub_res = requests.post(publish_url, data=pub_payload).json()
    if "id" not in pub_res:
        raise Exception(f"Publish Failed: {pub_res}")
    
    print("Successfully posted! Media ID:", pub_res["id"])

if __name__ == "__main__":
    assemble_reel()
    video_url = upload_temp_host()
    post_to_instagram(video_url)
    
