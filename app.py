import os
import sys
import ffmpeg
import whisper
import requests # Import the requests library for OpenRouter API calls
from flask import Flask, request, render_template, jsonify, send_from_directory
import logging
from datetime import timedelta, datetime
import re
import subprocess
from dotenv import load_dotenv
import uuid
import json

load_dotenv()

# --- Basic Setup ---
app = Flask(__name__)

# --- Get OpenRouter API Key ---
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    print("ERROR: OpenRouter API key not found.")
    print("Please set the OPENROUTER_API_KEY environment variable.")
    sys.exit(1)

# --- Configure Folder Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
SUBS_DIR = os.path.join(BASE_DIR, "subs")
EXTRACTED_AUDIO_DIR = os.path.join(BASE_DIR, "extracted_audio")
TRANSCRIPTS_DIR = os.path.join(BASE_DIR, "transcripts")

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SUBS_DIR, exist_ok=True)
os.makedirs(EXTRACTED_AUDIO_DIR, exist_ok=True)
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)

# New logging directories for OpenRouter
OPENROUTER_LOG_DIR = os.path.join(BASE_DIR, "logs", "openrouter_requests")
os.makedirs(OPENROUTER_LOG_DIR, exist_ok=True)

OPENROUTER_ERROR_LOG_DIR = os.path.join(BASE_DIR, "logs", "openrouter_errors")
os.makedirs(OPENROUTER_ERROR_LOG_DIR, exist_ok=True)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- AI Model Loading ---
def load_whisper_model():
    """Loads the Whisper model."""
    model = whisper.load_model("base")
    logging.info("Whisper model loaded.")
    return model

# Pre-load models on startup
WHISPER_MODEL = load_whisper_model()

# --- Helper Functions (The Pipeline) ---

def extract_audio(video_path, output_audio_path):
    """Extracts audio from a video file."""
    logging.info(f"Extracting audio from {video_path}...")
    try:
        (
            ffmpeg
            .input(video_path)
            .output(output_audio_path, ac=1, ar='16000') # Set audio channels to 1 and sample rate to 16000
            .overwrite_output()
            .run(quiet=True, capture_stdout=True, capture_stderr=True)
        )
        logging.info(f"Audio extracted and saved to {output_audio_path}")
        return True
    except ffmpeg.Error as e:
        logging.error("ffmpeg error during audio extraction:")
        logging.error(e.stderr.decode('utf8'))
        return False

def transcribe_audio(audio_path, language_code=None):
    """
    Transcribes audio using Whisper.
    Returns the transcribed segments and the detected language.
    """
    logging.info(f"Transcribing {audio_path}...")
    try:
        transcribe_options = {'task': 'transcribe', 'verbose': False}

        if language_code and language_code.lower() != 'auto':
            logging.info(f"User specified source language: {language_code}")
            transcribe_options['language'] = language_code.lower()
        else:
            logging.info("Auto-detecting source language.")

        result = WHISPER_MODEL.transcribe(audio_path, **transcribe_options)

        detected_language = result['language']
        segments = result['segments']

        logging.info(f"Transcription complete. Language confirmed as: {detected_language}")
        return segments, detected_language

    except Exception as e:
        logging.error(f"Error during transcription: {e}")
        return None, None

def save_transcription(segments, output_path):
    """Saves the full transcribed text to a .txt file."""
    logging.info(f"Saving transcription to {output_path}...")
    try:
        full_transcript = " ".join(segment['text'].strip() for segment in segments)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_transcript)
        logging.info(f"Transcription saved successfully to {output_path}")
        return True
    except Exception as e:
        logging.error(f"Error saving transcription file: {e}")
        return False

def translate_full_transcript_via_openrouter(segments, src_lang, tgt_lang):
    """
    Translates the full transcript using a single OpenRouter AI API call,
    then re-maps the translations to the original timestamps.
    """
    logging.info(f"Translating full transcript from '{src_lang}' to '{tgt_lang}' using OpenRouter AI...")
    
    # Use a unique, unlikely separator to split segments.
    separator = "|||SEGMENT_BREAK|||"
    
    # Join all original text segments with the separator.
    full_transcript = separator.join([segment['text'].strip() for segment in segments])

    # A unique ID for logging this single, large request.
    request_id = str(uuid.uuid4())

    try:
        # Craft a prompt that instructs the model to preserve the separators.
        prompt = (
            f"You are a professional translator for video subtitles. "
            f"Translate the following text, which is composed of multiple segments separated by '{separator}', from {src_lang} to {tgt_lang}. "
            f"**Crucially, you MUST preserve the '{separator}' separators in their original positions in your translated output.** "
            f"Your response must contain only the translated text, with the separators intact. Do not add any explanations or preamble.\n\n"
            f"Original text:\n\"{full_transcript}\""
        )
        
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            # Optional: Add HTTP-Referer and X-Title for OpenRouter's leaderboards/tracking
            #"HTTP-Referer": "https://your-app-domain.com", # Replace with your actual app domain
            #"X-Title": "Video Subtitler App", # Replace with your app name
        }
        
        payload = {
            "model": "deepseek/deepseek-r1-0528:free", # You can choose another OpenRouter-supported model here
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        
        response_json = response.json()
        full_translation = response_json['choices'][0]['message']['content'].strip()
        
        # Split the single translated string back into individual segments.
        translated_texts = full_translation.split(separator)
        
        # --- VALIDATION ---
        # Check if the number of translated segments matches the original number.
        if len(translated_texts) != len(segments):
            logging.error(f"Translation segment count mismatch! Original: {len(segments)}, Translated: {len(translated_texts)}. Falling back to original text.")
            log_mismatch_error(request_id, prompt, full_translation, segments)
            return segments # Fallback to original untranslated segments

        # --- SUCCESS LOGGING ---
        log_openrouter_request(request_id, "success", prompt, full_translation, segments)

        # Re-map the translated texts back to the original segment data (with timestamps).
        translated_segments = []
        for i, segment in enumerate(segments):
            translated_segments.append({
                'start': segment['start'],
                'end': segment['end'],
                'text': translated_texts[i].strip()
            })
            
        logging.info("Full transcript translation complete and re-mapped to timestamps.")
        return translated_segments

    except requests.exceptions.RequestException as e:
        logging.error(f"OpenRouter API call failed for the full transcript. Network or API error: {e}")
        log_openrouter_request(request_id, "error", prompt, str(e), segments)
        return segments # Fallback to original untranslated segments
    except KeyError:
        logging.error(f"OpenRouter API response structure unexpected. No 'choices' or 'message' found. Response: {response_json}")
        log_openrouter_request(request_id, "error", prompt, json.dumps(response_json), segments)
        return segments # Fallback to original untranslated segments
    except Exception as e:
        logging.error(f"An unexpected error occurred during OpenRouter API call: {e}")
        log_openrouter_request(request_id, "error", prompt, str(e), segments)
        return segments # Fallback to original untranslated segments


def log_openrouter_request(request_id, status, prompt, response_text, original_segments):
    """Logs the details of an OpenRouter API request."""
    log_data = {
        "id": request_id,
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "prompt_sent": prompt,
        "response_received": response_text,
        "original_segment_count": len(original_segments),
    }
    log_dir = OPENROUTER_LOG_DIR if status == "success" else OPENROUTER_ERROR_LOG_DIR
    log_filename = f"{request_id}_{status}.json"
    log_path = os.path.join(log_dir, log_filename)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=4)

def log_mismatch_error(request_id, prompt, response_text, original_segments):
    """Logs a specific error for when segment counts do not match."""
    error_details = {
        "error_type": "SegmentCountMismatch",
        "message": "The number of segments returned by OpenRouter did not match the number of segments sent.",
        "original_segment_count": len(original_segments),
        "translated_segment_count": len(response_text.split("|||SEGMENT_BREAK|||"))
    }
    log_data = {
        "id": request_id,
        "status": "error",
        "timestamp": datetime.now().isoformat(),
        "prompt_sent": prompt,
        "response_received": response_text,
        "error_details": error_details
    }
    log_path = os.path.join(OPENROUTER_ERROR_LOG_DIR, f"{request_id}_mismatch_error.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=4)

def format_time(seconds):
    """Formats seconds into SRT time format (HH:MM:SS,ms)."""
    delta = timedelta(seconds=seconds)
    hours, remainder = divmod(delta.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02},{milliseconds:03}"

def generate_srt(segments, output_path):
    """Generates an SRT subtitle file from segments."""
    logging.info(f"Generating SRT file at {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        for i, segment in enumerate(segments):
            f.write(f"{i + 1}\n")
            f.write(f"{format_time(segment['start'])} --> {format_time(segment['end'])}\n")
            f.write(f"{segment['text'].strip()}\n\n")
    logging.info("SRT file generated.")
    return output_path

def escape_ffmpeg_path(path):
    """Escapes a path for use in an ffmpeg filter command, especially for Windows."""
    if os.name == 'nt':
        # For Windows, escape backslashes and colons in the path
        return path.replace('\\', '/').replace(':', '\\:')
    return path

def burn_subtitles(video_path, srt_path, output_video_path):
    """Burns subtitles into a video file using ffmpeg."""
    logging.info(f"Burning subtitles from {srt_path} into {video_path}...")

    # The srt_path needs to be properly escaped for the ffmpeg filtergraph
    escaped_srt_path = escape_ffmpeg_path(os.path.abspath(srt_path))
    filter_command = f"subtitles=filename='{escaped_srt_path}'"

    cmd = [
        'ffmpeg', '-y', '-i', video_path,
        '-vf', filter_command,
        '-c:a', 'copy', # Copy audio stream without re-encoding
        output_video_path
    ]
    
    logging.info(f"Running ffmpeg command: {' '.join(cmd)}")
    
    try:
        # Using subprocess.run to execute the command
        result = subprocess.run(
            cmd,
            capture_output=True, # Capture stdout and stderr
            text=True, # Decode as text
            check=True # Raise CalledProcessError on non-zero exit codes
        )
        logging.info(f"Subtitled video saved to {output_video_path}")
        return output_video_path
    except subprocess.CalledProcessError as e:
        logging.error("Subtitle burning failed.")
        logging.error(f"ffmpeg stdout: {e.stdout}")
        logging.error(f"ffmpeg stderr: {e.stderr}")
        return None

# --- Flask Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/output/<filename>')
def serve_output_file(filename):
    return send_from_directory(OUTPUT_DIR, filename)

@app.route('/process-video', methods=['POST'])
def process_video_route():
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided"}), 400

    video_file = request.files['video']
    source_language_input = request.form['source_language']
    target_language = request.form['target_language']

    base_filename = os.path.splitext(video_file.filename)[0]
    sanitized_filename = re.sub(r'[^a-zA-Z0-9_-]', '', base_filename) # Sanitize filename
    input_video_path = os.path.join(INPUT_DIR, f"{sanitized_filename}{os.path.splitext(video_file.filename)[1]}")

    extracted_audio_path = os.path.join(EXTRACTED_AUDIO_DIR, f"{sanitized_filename}_audio.wav")
    transcription_path = os.path.join(TRANSCRIPTS_DIR, f"{sanitized_filename}_transcription.txt")
    srt_path = os.path.join(SUBS_DIR, f"{sanitized_filename}_{target_language}.srt")
    output_video_path = os.path.join(OUTPUT_DIR, f"{sanitized_filename}_{target_language}_subtitled.mp4")
    output_video_filename = os.path.basename(output_video_path)

    video_file.save(input_video_path)

    if not extract_audio(input_video_path, extracted_audio_path):
        return jsonify({"error": "Failed to extract audio."}), 500

    transcribed_segments, actual_source_language = transcribe_audio(extracted_audio_path, source_language_input)
    if not transcribed_segments:
        return jsonify({"error": "Failed to transcribe audio."}), 500

    save_transcription(transcribed_segments, transcription_path)
    
    # Call the new OpenRouter translation function
    translated_segments = translate_full_transcript_via_openrouter(transcribed_segments, actual_source_language, target_language)
    if not translated_segments:
        # The function now includes a fallback, but we check again in case of total failure
        return jsonify({"error": "Failed to translate text."}), 500
        
    generate_srt(translated_segments, srt_path)

    final_video_path = burn_subtitles(input_video_path, srt_path, output_video_path)
    if not final_video_path:
        return jsonify({"error": "Failed to burn subtitles into video. Check ffmpeg logs."}), 500

    return jsonify({
        "message": "Video processed successfully!",
        "video_url": f"/output/{output_video_filename}"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

