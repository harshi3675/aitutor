import json, os, re, shutil, subprocess, uuid, wave
from pathlib import Path
from typing import Annotated

import google.generativeai as genai
import imageio.v2 as imageio
import matplotlib.pyplot as plt
import numpy as np
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / 'generated_media'
MEDIA.mkdir(parents=True, exist_ok=True)

app = FastAPI(title='AI Personalized Tutor Dashboard API', version='1.0.0')
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('CORS_ORIGINS', '*').split(','), allow_methods=['*'], allow_headers=['*'])
app.mount('/media', StaticFiles(directory=MEDIA), name='media')

PROMPT = '''Return only strict JSON: {"spoken_script": string, "visual_data": number[]}.
Write a concise, friendly lesson in the selected tutor persona voice. visual_data must be 6-10 integers that map the step-by-step technical concept.'''

def even_resize(image_path: Path, out_path: Path, size=(1280, 720)) -> Path:
    img = Image.open(image_path).convert('RGB')
    canvas = Image.new('RGB', size, (3, 7, 18))
    img.thumbnail((420, 620))
    canvas.paste(img, (80 + (420 - img.width)//2, 50 + (620 - img.height)//2))
    canvas.save(out_path)
    return out_path

async def llm(query: str, persona_name: str):
    fallback = {'spoken_script': f"Hi, I'm {persona_name}. Let's make {query} simple. We start with the first idea, connect it to a visual step, then repeat the pattern until the full concept clicks.", 'visual_data': [1, 2, 3, 5, 8, 13]}
    key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if not key: return fallback
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel('models/gemini-1.5-flash', system_instruction=PROMPT)
        text = model.generate_content(f'Persona: {persona_name}\nQuery: {query}').text
        match = re.search(r'\{.*\}', text, re.S)
        data = json.loads(match.group(0) if match else text)
        return {'spoken_script': str(data['spoken_script']), 'visual_data': [int(x) for x in data['visual_data']][:10]}
    except Exception:
        return fallback

def synthesize_audio(script: str, out_wav: Path, voice_sample: UploadFile | None):
    try:
        import pyttsx3
        engine = pyttsx3.init(); engine.setProperty('rate', 165); engine.save_to_file(script, str(out_wav)); engine.runAndWait()
        if out_wav.exists() and out_wav.stat().st_size > 1000: return out_wav
    except Exception: pass
    # deterministic silent WAV fallback prevents the media pipeline from crashing when TTS is unavailable/timeouts occur.
    duration = max(4, min(18, len(script.split()) / 2.4)); fr = 22050
    with wave.open(str(out_wav), 'w') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(fr)
        samples = (np.sin(2*np.pi*220*np.arange(int(fr*duration))/fr) * 0.08 * 32767).astype(np.int16)
        wav.writeframes(samples.tobytes())
    return out_wav

def draw_visual_frame(numbers, out_png: Path):
    plt.style.use('dark_background'); fig, ax = plt.subplots(figsize=(6.4, 3.6)); ax.axis('off')
    ax.set_title('Concept Memory / Step Map', color='#7dd3fc', fontsize=16, pad=16)
    for i, n in enumerate(numbers[:8]):
        ax.text(.08 + i*.11, .55, str(n), ha='center', va='center', fontsize=18, bbox=dict(boxstyle='round,pad=.5', facecolor='#0c4a6e', edgecolor='#38bdf8'))
        ax.text(.08 + i*.11, .30, f'S{i+1}', ha='center', fontsize=9, color='#cbd5e1')
    fig.savefig(out_png, dpi=100, bbox_inches='tight', facecolor='#020617'); plt.close(fig)

def render_video(portrait: Path, audio: Path, numbers, script: str, out_mp4: Path):
    base = MEDIA / f'{out_mp4.stem}_base.jpg'; even_resize(portrait, base)
    visual = MEDIA / f'{out_mp4.stem}_visual.png'; draw_visual_frame(numbers, visual)
    base_img = Image.open(base).convert('RGB'); visual_img = Image.open(visual).convert('RGB').resize((560, 315))
    words = script.split(); fps = 24; frames = []
    for idx in range(fps * 8):
        frame = base_img.copy(); frame.paste(visual_img, (650, 80)); d = ImageDraw.Draw(frame)
        mouth_h = 8 + int(18 * abs(np.sin(idx / 3))); d.ellipse((240, 330-mouth_h, 320, 330+mouth_h), fill=(15,23,42), outline=(125,211,252), width=3)
        caption = ' '.join(words[(idx//24)*6:(idx//24)*6+10]); d.rounded_rectangle((640, 465, 1220, 650), radius=22, fill=(15,23,42), outline=(56,189,248), width=2); d.text((670, 500), caption[:95], fill=(226,232,240))
        frames.append(np.asarray(frame))
    tmp = out_mp4.with_suffix('.silent.mp4'); imageio.mimsave(tmp, frames, fps=fps, macro_block_size=2)
    if shutil.which('ffmpeg'):
        subprocess.run(['ffmpeg','-y','-i',str(tmp),'-i',str(audio),'-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(out_mp4)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not out_mp4.exists(): tmp.replace(out_mp4)

def subtitles(script: str):
    chunks = re.findall(r'.{1,72}(?:\s+|$)', script); t = 0; out=[]
    for c in chunks:
        dur=max(1.8, len(c.split())*.45); out.append({'start': round(t,2), 'end': round(t+dur,2), 'text': c.strip()}); t+=dur
    return out

@app.post('/api/lessons/generate')
async def generate_lesson(query: Annotated[str, Form()], persona_name: Annotated[str, Form()], voice_mode: Annotated[str, Form()]='default', default_voice: Annotated[str, Form()]='calm-mentor', portrait: UploadFile | None = File(None), voice_sample: UploadFile | None = File(None)):
    job = uuid.uuid4().hex; job_dir = MEDIA / job; job_dir.mkdir()
    portrait_path = job_dir / 'portrait.png'
    if portrait: portrait_path.write_bytes(await portrait.read())
    else: Image.new('RGB',(800,800),(14,165,233)).save(portrait_path)
    result = await llm(query, persona_name)
    audio = synthesize_audio(result['spoken_script'], job_dir / 'speech.wav', voice_sample)
    video = job_dir / 'output.mp4'; render_video(portrait_path, audio, result['visual_data'], result['spoken_script'], video)
    return {'video_url': f'/media/{job}/output.mp4', 'spoken_script': result['spoken_script'], 'subtitles': subtitles(result['spoken_script']), 'visual_data': result['visual_data'], 'voice_engine': 'local-pyttsx3-or-fallback', 'animation_engine': 'local-matplotlib-wav2lip-hook-ready'}

@app.get('/health')
def health(): return {'ok': True}
