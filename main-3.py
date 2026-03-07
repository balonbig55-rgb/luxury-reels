import os
import random
import csv
import requests
import subprocess
from datetime import datetime

# ========== GitHub Secrets ==========
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# ========== Step 1: Get random idea from CSV ==========
def get_random_idea():
    try:
        with open("ideas.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            ideas = list(reader)
            idea = random.choice(ideas)
            print(f"✅ Idea: {idea}")
            return idea
    except Exception as e:
        print(f"⚠️ Could not read ideas.csv: {e}")
        return {"title": "Luxury Villa", "location": "Maldives", "keywords": "luxury villa pool ocean"}

# ========== Step 2: Generate caption with Gemini ==========
def generate_caption(idea):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"""Write a short Instagram Reel caption for a luxury property called "{idea.get('title', 'Luxury Villa')}" in {idea.get('location', 'a beautiful location')}.
Include:
- 2-3 sentences max
- 1 call to action (Book via link in bio)
- 5 relevant hashtags
Keep it aspirational and exciting."""

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        data = response.json()
        caption = data["candidates"][0]["content"]["parts"][0]["text"]
        print("✅ Caption generated")
        return caption
    except Exception as e:
        print(f"⚠️ Gemini failed: {e}, using default caption")
        return f"✨ {idea.get('title', 'Dream Home')} in {idea.get('location', 'Paradise')} 🏡\n\nYour luxury escape awaits. Book now via link in bio!\n\n#LuxuryRealEstate #LuxuryTravel #DreamHome #Airbnb #LuxuryLiving"

# ========== Step 3: Get video from Pexels ==========
def get_video(idea):
    keywords = idea.get("keywords", "luxury villa")
    url = f"https://api.pexels.com/videos/search?query={keywords}&per_page=15&orientation=portrait"
    headers = {"Authorization": PEXELS_API_KEY}
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        data = response.json()
        videos = data["videos"]
        video = random.choice(videos)
        video_files = video["video_files"]
        hd_files = [f for f in video_files if f.get("height", 0) >= 720]
        chosen = hd_files[0] if hd_files else video_files[0]
        print(f"✅ Video found: {video['id']}")
        return chosen["link"]
    except Exception as e:
        print(f"❌ Pexels failed: {e}")
        return None

# ========== Step 4: Download video ==========
def download_video(video_url):
    print("⬇️ Downloading video...")
    try:
        response = requests.get(video_url, stream=True, timeout=60)
        filename = "reel.mp4"
        with open(filename, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        size = os.path.getsize(filename) / (1024 * 1024)
        print(f"✅ Downloaded: {size:.1f} MB")
        return filename
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return None

# ========== Step 5: Send to Telegram ==========
def send_to_telegram(video_path, caption):
    print("📤 Sending to Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    
    try:
        with open(video_path, "rb") as f:
            response = requests.post(url, data={
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption[:1024],
            }, files={"video": f}, timeout=120)
        
        if response.status_code == 200:
            print("✅ Sent to Telegram!")
            return True
        else:
            print(f"❌ Telegram error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Telegram failed: {e}")
        return False

# ========== Main ==========
def main():
    print("🚀 Luxury Reel Generator Started!")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    idea = get_random_idea()
    caption = generate_caption(idea)
    print(f"\n📝 Caption:\n{caption}\n")

    video_url = get_video(idea)
    if not video_url:
        print("❌ No video found. Exiting.")
        return

    video_path = download_video(video_url)
    if not video_path:
        print("❌ Download failed. Exiting.")
        return

    success = send_to_telegram(video_path, caption)

    if os.path.exists(video_path):
        os.remove(video_path)
        print("🧹 Cleaned up temp file")

    if success:
        print("\n🎉 Done! Check your Telegram.")
    else:
        print("\n❌ Failed to send reel.")

if __name__ == "__main__":
    main()
