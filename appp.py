import os
import sys
import ffmpeg
import whisper
import google.generativeai as genai # Import Google Gemini library
from flask import Flask, request, render_template, jsonify, send_from_directory
import logging
from datetime import timedelta
import re # Import the regular expressions module

# --- Basic Setup ---
app = Flask(__name__)

# --- Get Gemini API Key ---
# IMPORTANT: Set this in your terminal before running the app
# On Windows: set GEMINI_API_KEY=your_key_here
# On macOS/Linux: export GEMINI_API_KEY=your_key_here
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("ERROR: Gemini API key not found.")
    print("Please set the GEMINI_API_KEY environment variable.")
    sys.exit(1)

# Configure the Gemini client
genai.configure(api_key=GEMINI_API_KEY)

# --- Configure Folder Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
SUBS_DIR = os.path.join(BASE_DIR, "subs")
AUDIO_TEMP_DIR = os.path.join(BASE_DIR, "output")

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SUBS_DIR, exist_ok=True)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)

# --- AI Model Loading ---
def load_whisper_model():
    """Loads the Whisper model."""
    model = whisper.load_model("base")
    logging.info("Whisper model loaded.")
    return model

# Pre-load models on startup
WHISPER_MODEL = load_whisper_model()
# Use a fast and capable model like gemini-1.5-flash
GEMINI_MODEL = genai.GenerativeModel('gemini-1.5-flash-latest')

# --- Helper Functions (The Pipeline) ---

def extract_audio(video_path, output_audio_path):
    logging.info(f"Extracting audio from {video_path}...")
    try:
        (
            ffmpeg
            .input(video_path)
            .output(output_audio_path, ac=1, ar='16000')
            .overwrite_output()
            .run(quiet=True, capture_stdout=True, capture_stderr=True) # Capture output
        )
        logging.info(f"Audio extracted to {output_audio_path}")
        return True
    except ffmpeg.Error as e:
        # Log the detailed ffmpeg error
        logging.error("ffmpeg error during audio extraction:")
        logging.error(e.stderr.decode('utf8'))
        return False

def transcribe_audio(audio_path):
    logging.info(f"Transcribing {audio_path}...")
    try:
        result = WHISPER_MODEL.transcribe(audio_path, verbose=False)
        logging.info("Transcription complete.")
        return result['segments']
    except Exception as e:
        logging.error(f"Error during transcription: {e}")
        return None

def translate_segments_via_gemini(segments, tgt_lang):
    """
    Translates text segments using the Google Gemini API.
    """
    logging.info(f"Translating text to {tgt_lang} using Gemini API...")
    
    translated_segments = []
    
    for segment in segments:
        try:
            # Create a very specific prompt to ensure the model only returns the translation
            prompt = f"Translate the following English text to {tgt_lang}. Do not add any extra explanations, introductory phrases, or translations of the instructions. Only return the translated text itself.\n\nEnglish text: \"{segment['text']}\""

            response = GEMINI_MODEL.generate_content(prompt)
            
            # Clean up the response text from potential markdown or quotes
            translated_text = response.text.strip().replace('"', '')

            if translated_text:
                translated_segments.append({
                    'start': segment['start'],
                    'end': segment['end'],
                    'text': translated_text
                })
            else:
                logging.warning(f"Gemini returned an empty response for segment: {segment['text']}. Using original text.")
                translated_segments.append(segment) # Fallback to original
        
        except Exception as e:
            logging.error(f"Gemini API call failed for segment: '{segment['text']}'. Error: {e}")
            translated_segments.append(segment) # Fallback to original text

    logging.info("Translation complete.")
    return translated_segments


def format_time(seconds):
    delta = timedelta(seconds=seconds)
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = delta.microseconds // 1000
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

def generate_srt(segments, output_path):
    logging.info(f"Generating SRT file at {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        for i, segment in enumerate(segments):
            f.write(f"{i + 1}\n")
            f.write(f"{format_time(segment['start'])} --> {format_time(segment['end'])}\n")
            f.write(f"{segment['text']}\n\n")
    logging.info("SRT file generated.")
    return output_path


def escape_ffmpeg_path(path):
    """
    Correctly escapes a Windows path for use in an ffmpeg filter.
    """
    if os.name == 'nt':
        # 1. Replace all backslashes with forward slashes
        path = path.replace('\\', '/')
        # 2. Escape the colon after the drive letter
        path = path.replace(':', '\\\\:')
    return path

def burn_subtitles(video_path, srt_path, output_video_path):
    """
    Burns subtitles into the video using the 'subtitles' filter with proper path escaping.
    Falls back to the 'drawtext' method on failure.
    """
    logging.info(f"Burning subtitles into {video_path}...")
    
    # Use the helper function to correctly escape the SRT file path
    escaped_srt_path = escape_ffmpeg_path(srt_path)
    
    cmd = [
        'ffmpeg',
        '-y',
        '-i', video_path,
        '-vf', f"subtitles='{escaped_srt_path}'",
        '-c:a', 'copy',
        output_video_path
    ]
    
    logging.info(f"Running ffmpeg command (Method 1): {' '.join(cmd)}")
    
    try:
        import subprocess
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True
        )
        logging.info(f"Subtitled video saved to {output_video_path}")
        return output_video_path
        
    except subprocess.CalledProcessError as e:
        logging.error("Method 1 (subtitles filter) failed. Trying fallback method...")
        logging.error(f"ffmpeg stderr: {e.stderr}")
        # Fallback to the drawtext method if the first method fails
        return burn_subtitles_drawtext_method(video_path, srt_path, output_video_path)
        
    except Exception as e:
        logging.error(f"An unexpected error occurred during subtitle burning: {e}")
        return None

# This helper function is still correct and necessary
def escape_ffmpeg_path(path):
    """
    Correctly escapes a Windows path for use in an ffmpeg filter.
    Produces a string like 'C\\:/path/to/file'
    """
    if os.name == 'nt':
        path = path.replace('\\', '/')
        path = path.replace(':', '\\\\:')
    return path

def burn_subtitles(video_path, srt_path, output_video_path):
    """
    Burns subtitles into the video using the 'subtitles' filter with proper path escaping.
    Falls back to the 'drawtext' method on failure.
    """
    logging.info(f"Burning subtitles into {video_path}...")
    
    # Use the helper function to correctly escape the SRT file path
    escaped_srt_path = escape_ffmpeg_path(srt_path)
    
    # THE FIX: Use the explicit 'filename=' parameter and NO inner quotes.
    filter_command = f"subtitles=filename={escaped_srt_path}"
    
    cmd = [
        'ffmpeg',
        '-y',
        '-i', video_path,
        '-vf', filter_command,
        '-c:a', 'copy',
        output_video_path
    ]
    
    logging.info(f"Running ffmpeg command (Method 1): {' '.join(cmd)}")
    
    try:
        import subprocess
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True,
            encoding='utf-8' # Specify encoding for better error handling
        )
        logging.info(f"Subtitled video saved to {output_video_path}")
        return output_video_path
        
    except subprocess.CalledProcessError as e:
        logging.error("Method 1 (subtitles filter) failed. Trying fallback method...")
        logging.error(f"ffmpeg stderr: {e.stderr}")
        # Fallback to the drawtext method if the first method fails
        return burn_subtitles_drawtext_method(video_path, srt_path, output_video_path)
        
    except Exception as e:
        logging.error(f"An unexpected error occurred during subtitle burning: {e}")
        return None

def burn_subtitles_drawtext_method(video_path, srt_path, output_video_path):
    """
    Alternative method using the 'drawtext' filter. This method is more complex
    but can be more reliable. It correctly handles text and path escaping.
    """
    logging.info("Using fallback 'drawtext' method...")
    
    try:
        import subprocess
        
        subtitles = parse_srt_file(srt_path)
        if not subtitles:
            logging.error("Failed to parse SRT file for drawtext method.")
            return None
            
        # Escape the font file path
        font_path = escape_ffmpeg_path("C:/Windows/Fonts/arial.ttf")
        
        # Build drawtext filters for each subtitle segment
        filters = []
        for sub in subtitles:
            # IMPORTANT: Escape special characters within the subtitle text itself for ffmpeg
            text = sub['text'].replace("\\", "\\\\").replace("'", "’").replace(":", "\\:").replace("%", "\\%").replace(",", "\\,")
            
            # THE FIX: Remove the single quotes around the font_path and the text value.
            filter_str = (
                f"drawtext=fontfile={font_path}:"
                f"text='{text}':"  # Keep quotes around the text itself
                "fontsize=24:fontcolor=white:bordercolor=black:borderw=2:"
                "x=(w-text_w)/2:y=h-th-20:" # Position text 20px from the bottom
                f"enable='between(t,{sub['start']},{sub['end']})'"
            )
            filters.append(filter_str)
        
        # Correctly chain the filters together with commas
        vf_param = ",".join(filters)
        
        cmd = [
            'ffmpeg',
            '-y',
            '-i', video_path,
            '-vf', vf_param,
            '-c:a', 'copy',
            output_video_path
        ]
        
        logging.info("Running ffmpeg command (Method 2 - drawtext)...")

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True,
            encoding='utf-8' # Specify encoding
        )
        
        logging.info(f"Subtitled video saved using drawtext method: {output_video_path}")
        return output_video_path
        
    except subprocess.CalledProcessError as e:
        logging.error("Drawtext method also failed.")
        logging.error(f"Failed command: {' '.join(e.cmd)}")
        logging.error(f"ffmpeg stderr: {e.stderr}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred in drawtext method: {e}")
        return None


# Your existing `parse_srt_file` function is good, no changes needed there.
def parse_srt_file(srt_path):
    """
    Parse SRT file and return list of subtitle dictionaries.
    """
    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        subtitles = []
        # Use regex for more robust parsing of blocks and timings
        blocks = re.findall(r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n([\s\S]*?)(?=\n\n|\Z)', content)
        
        for block in blocks:
            start_str = block[1]
            end_str = block[2]
            text = block[3].strip().replace('\n', ' ')

            subtitles.append({
                'start': parse_time_to_seconds(start_str),
                'end': parse_time_to_seconds(end_str),
                'text': text
            })
            
        return subtitles
    except Exception as e:
        logging.error(f"Error parsing SRT file: {e}")
        return None

# Your existing `parse_time_to_seconds` function is also fine.
def parse_time_to_seconds(time_str):
    """
    Convert SRT time format (HH:MM:SS,mmm) to seconds.
    """
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds
    
#
# ... (rest of your Flask routes) ...
#

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
    target_language = request.form['language']
    
    base_filename = os.path.splitext(video_file.filename)[0]
    input_video_path = os.path.join(INPUT_DIR, video_file.filename)
    audio_temp_path = os.path.join(AUDIO_TEMP_DIR, f"{base_filename}_temp_audio.wav")
    srt_path = os.path.join(SUBS_DIR, f"{base_filename}_{target_language}.srt")
    output_video_path = os.path.join(OUTPUT_DIR, f"{base_filename}_{target_language}_subtitled.mp4")
    output_video_filename = os.path.basename(output_video_path)

    video_file.save(input_video_path)
    
    if not extract_audio(input_video_path, audio_temp_path):
        return jsonify({"error": "Failed to extract audio."}), 500
    
    transcribed_segments = transcribe_audio(audio_temp_path)
    if not transcribed_segments:
        return jsonify({"error": "Failed to transcribe audio."}), 500
        
    translated_segments = translate_segments_via_gemini(transcribed_segments, target_language)
    if not translated_segments:
        return jsonify({"error": "Failed to translate text."}), 500
        
    generate_srt(translated_segments, srt_path)
    
    final_video_path = burn_subtitles(input_video_path, srt_path, output_video_path)
    if not final_video_path:
        return jsonify({"error": "Failed to burn subtitles into video."}), 500

    if os.path.exists(audio_temp_path):
        os.remove(audio_temp_path)
        
    return jsonify({
        "message": "Video processed successfully!",
        "video_url": f"/output/{output_video_filename}"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
