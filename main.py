import os
import random
import csv
import requests
import subprocess
from datetime import datetime

# ============================================================
# إعدادات - يتم قراءتها من GitHub Secrets
# ============================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# ============================================================
# الخطوة 1: قراءة فكرة عشوائية من CSV
# ============================================================
def get_random_idea():
    with open("ideas.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        ideas = list(reader)
    
    if not ideas:
        raise Exception("No ideas found in ideas.csv!")
    
    idea = random.choice(ideas)
    print(f"✅ Selected: {idea['property']} in {idea['location']}")
    return idea

# ============================================================
# الخطوة 2: توليد Caption بـ Gemini
# ============================================================
def generate_caption(idea):
    url = "https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent"
    
    prompt = f"""You are a luxury real estate Instagram expert.

Property: {idea['property']}
Location: {idea['location']}
Style: {idea['style']}
Price: {idea['price_range']}

Create in this EXACT format:

CAPTION: [Luxury Instagram caption 150 words, aspirational tone, ends with 'Link in bio 🔗']

HEADLINE: [5-6 words ALL CAPS for video overlay, luxury feel]

SUBTITLE: [Location + price hint, 3-4 words]

HASHTAGS: [30 hashtags: #LuxuryLiving #DreamHome #LuxuryRealEstate #MansionLife #LuxuryLifestyle #MillionDollarListing #LuxuryHomes #RealEstate #HomeGoals #LuxuryLife and 20 more relevant ones]"""

    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    response = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        params={"key": GEMINI_API_KEY},
        json=data
    )
    
    result = response.json()
    full_text = result["candidates"][0]["content"]["parts"][0]["text"]
    
    def extract(text, label):
        lines = text.split("\n")
        idx = next((i for i, l in enumerate(lines) if l.startswith(label + ":")), -1)
        if idx == -1:
            return ""
        result = lines[idx].replace(label + ":", "").strip()
        for i in range(idx + 1, len(lines)):
            if any(lines[i].startswith(l + ":") for l in ["CAPTION", "HEADLINE", "SUBTITLE", "HASHTAGS"]):
                break
            result += "\n" + lines[i]
        return result.strip()
    
    caption = extract(full_text, "CAPTION")
    headline = extract(full_text, "HEADLINE") or "LUXURY LIVING REDEFINED"
    subtitle = extract(full_text, "SUBTITLE") or idea["location"]
    hashtags = extract(full_text, "HASHTAGS")
    
    print(f"✅ Caption generated: {len(caption)} chars")
    return caption, headline, subtitle, hashtags

# ============================================================
# الخطوة 3: جلب مقاطع فيديو من Pexels
# ============================================================
def get_pexels_videos(idea):
    queries = [
        f"{idea['style']} luxury villa",
        f"luxury mansion {idea['location']}",
        "luxury villa swimming pool",
        "modern luxury house interior",
        "luxury real estate aerial view"
    ]
    
    query = random.choice(queries)
    print(f"🔍 Searching Pexels: {query}")
    
    response = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={
            "query": query,
            "per_page": 15,
            "min_duration": 5,
            "max_duration": 30,
            "orientation": "portrait"
        }
    )
    
    data = response.json()
    
    if not data.get("videos"):
        raise Exception(f"No videos found for: {query}")
    
    # اختيار 3 مقاطع عشوائية
    videos = random.sample(data["videos"], min(3, len(data["videos"])))
    video_urls = []
    
    for video in videos:
        files = video["video_files"]
        # اختيار أفضل جودة portrait
        portrait_files = [f for f in files if f.get("height", 0) > f.get("width", 0)]
        best = portrait_files[0] if portrait_files else files[0]
        video_urls.append(best["link"])
    
    print(f"✅ Found {len(video_urls)} videos")
    return video_urls

# ============================================================
# الخطوة 4: تحميل مقاطع الفيديو
# ============================================================
def download_videos(video_urls):
    os.makedirs("temp_videos", exist_ok=True)
    local_paths = []
    
    for i, url in enumerate(video_urls):
        path = f"temp_videos/clip_{i+1}.mp4"
        print(f"⬇️ Downloading clip {i+1}...")
        
        response = requests.get(url, stream=True)
        with open(path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        local_paths.append(path)
        print(f"✅ Downloaded: {path}")
    
    return local_paths

# ============================================================
# الخطوة 5: إنشاء الـ Reel بـ FFmpeg
# ============================================================
def create_reel(video_paths, headline, subtitle, output_path="reel_output.mp4"):
    print("🎬 Creating Reel with FFmpeg...")
    
    # تحضير الموسيقى (صمت إذا لم تكن متاحة)
    music_filter = ""
    
    # بناء الـ filter_complex
    num_clips = len(video_paths)
    
    # إدخالات الفيديو
    inputs = []
    for path in video_paths:
        inputs.extend(["-i", path])
    
    # تحويل كل مقطع إلى 9:16 و5 ثوانٍ
    filter_parts = []
    for i in range(num_clips):
        filter_parts.append(
            f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,"
            f"trim=duration=5,"
            f"setpts=PTS-STARTPTS[v{i}]"
        )
    
    # دمج المقاطع
    concat_input = "".join([f"[v{i}]" for i in range(num_clips)])
    filter_parts.append(f"{concat_input}concat=n={num_clips}:v=1:a=0[base]")
    
    # إضافة طبقة داكنة شفافة
    filter_parts.append(
        "[base]drawbox=x=0:y=0:w=iw:h=ih:color=black@0.4:t=fill[darkened]"
    )
    
    # إضافة الـ Headline
    headline_escaped = headline.replace("'", "\\'").replace(":", "\\:")
    subtitle_escaped = subtitle.replace("'", "\\'").replace(":", "\\:")
    
    filter_parts.append(
        f"[darkened]drawtext="
        f"text='{headline_escaped}':"
        f"fontsize=72:"
        f"fontcolor=white:"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        f"x=(w-text_w)/2:"
        f"y=(h-text_h)/2-60:"
        f"box=1:boxcolor=black@0.3:boxborderw=10[titled]"
    )
    
    # إضافة الـ Subtitle
    filter_parts.append(
        f"[titled]drawtext="
        f"text='{subtitle_escaped}':"
        f"fontsize=42:"
        f"fontcolor=#C9A84C:"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        f"x=(w-text_w)/2:"
        f"y=(h-text_h)/2+40:"
        f"box=1:boxcolor=black@0.3:boxborderw=8[final]"
    )
    
    filter_complex = ";".join(filter_parts)
    
    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[final]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-r", "30",
        "-t", str(num_clips * 5),
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"FFmpeg Error: {result.stderr}")
        raise Exception("FFmpeg failed!")
    
    print(f"✅ Reel created: {output_path}")
    return output_path

# ============================================================
# الخطوة 6: إرسال الـ Reel لـ Telegram
# ============================================================
def send_to_telegram(video_path, caption, hashtags, idea):
    print("📱 Sending to Telegram...")
    
    # رسالة 1: الفيديو
    with open(video_path, "rb") as video_file:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": f"🏡 NEW LUXURY REEL READY!\n📍 {idea['property']} - {idea['location']}"
            },
            files={"video": video_file}
        )
    
    print(f"Video sent: {response.status_code}")
    
    # رسالة 2: الـ Caption
    full_message = f"""📝 CAPTION (copy & paste):
━━━━━━━━━━━━━━━━
{caption}

{hashtags}
━━━━━━━━━━━━━━━━

🔗 Affiliate Link:
{idea.get('affiliate_url', 'Add your link here')}"""

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": full_message
        }
    )
    
    # رسالة 3: تعليمات النشر
    instructions = """📱 POSTING INSTRUCTIONS:

1️⃣ Save the video to your phone
2️⃣ Open Instagram → + → Reel
3️⃣ Select the video
4️⃣ Paste the caption above
5️⃣ Update bio link to affiliate URL
6️⃣ Post between 6PM - 9PM

💡 Best days: Tuesday, Wednesday, Friday
🔥 Reply with ✅ when posted!"""

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": instructions
        }
    )
    
    print("✅ All messages sent to Telegram!")

# ============================================================
# الخطوة 7: تنظيف الملفات المؤقتة
# ============================================================
def cleanup():
    import shutil
    if os.path.exists("temp_videos"):
        shutil.rmtree("temp_videos")
    if os.path.exists("reel_output.mp4"):
        os.remove("reel_output.mp4")
    print("✅ Cleanup done")

# ============================================================
# التشغيل الرئيسي
# ============================================================
def main():
    print(f"\n{'='*50}")
    print(f"🚀 Luxury Reels Automation Started")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")
    
    try:
        # الخطوة 1: فكرة عشوائية
        idea = get_random_idea()
        
        # الخطوة 2: توليد المحتوى
        caption, headline, subtitle, hashtags = generate_caption(idea)
        
        # الخطوة 3: جلب مقاطع الفيديو
        video_urls = get_pexels_videos(idea)
        
        # الخطوة 4: تحميل المقاطع
        video_paths = download_videos(video_urls)
        
        # الخطوة 5: إنشاء الـ Reel
        reel_path = create_reel(video_paths, headline, subtitle)
        
        # الخطوة 6: إرسال لـ Telegram
        send_to_telegram(reel_path, caption, hashtags, idea)
        
        print(f"\n{'='*50}")
        print("🎉 SUCCESS! Reel sent to Telegram!")
        print(f"{'='*50}\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        # إرسال إشعار خطأ
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": f"❌ Automation Error!\n\n{str(e)}\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
        )
        raise
    
    finally:
        cleanup()

if __name__ == "__main__":
    main()
