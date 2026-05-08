import os
import sys

# Force UTF-8 output to prevent print encoding errors on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from core.assistant import Assistant

# Load environment variables (API Key)
load_dotenv(".env.txt")

app = Flask(__name__)
# Instantiate Cynthia in web mode (bypasses audio/terminal I/O)
assistant = Assistant(text_mode=True, web_mode=True)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/greet", methods=["GET"])
def greet():
    """Fetch the initial greeting when the UI loads."""
    greeting = assistant._build_greeting()
    # Make sure we clear any stray messages that might have accumulated during init
    assistant.get_messages() 
    return jsonify({"greeting": greeting})

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    # Process user input through Cynthia
    assistant.process_input(user_message)
    
    # Retrieve Cynthia's responses (including possible triggered reminders)
    responses = assistant.get_messages()
    return jsonify({"responses": responses})

@app.route("/api/state", methods=["GET"])
def get_state():
    """Fetch current tasks, goal, and any background messages (like timed reminders)."""
    messages = assistant.get_messages()
    all_tasks = assistant.tasks.get_all()
    pending_tasks = [task for task in all_tasks if not task.get("done")]
    completed_tasks = [task for task in all_tasks if task.get("done")]
    reminders = assistant.scheduler.get_all()
    
    return jsonify({
        "tasks": pending_tasks,
        "completedTasks": completed_tasks,
        "reminders": reminders,
        "goal": assistant.memory.get("goal"),
        "memory": assistant.memory.all(),
        "stats": {
            "pending": len(pending_tasks),
            "completed": len(completed_tasks),
            "reminders": len([r for r in reminders if not r.get("fired")])
        },
        "messages": messages
    })

@app.route("/api/tasks/<int:position>/complete", methods=["POST"])
def complete_task(position):
    """Complete a visible pending task by its 1-based position."""
    result = assistant.tasks.complete(position - 1)
    return jsonify({"message": result})

@app.route("/api/tasks/<int:position>", methods=["DELETE"])
def delete_task(position):
    """Delete a visible pending task by its 1-based position."""
    result = assistant.tasks.delete(position - 1)
    return jsonify({"message": result})

@app.route("/api/listen", methods=["POST"])
def listen_mic():
    """Use the local system microphone for accurate STT via sounddevice."""
    import speech_recognition as sr
    import sounddevice as sd
    import scipy.io.wavfile as wav
    import tempfile
    import os

    try:
        duration = 5  # Listen for 5 seconds
        fs = 16000
        
        # Record audio
        recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
        sd.wait()
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
            temp_path = temp_audio.name
        
        # Write wav file outside the with block to ensure it's closed properly
        wav.write(temp_path, fs, recording)
            
        # Transcribe
        recognizer = sr.Recognizer()
        with sr.AudioFile(temp_path) as source:
            audio_data = recognizer.record(source)
            
        os.remove(temp_path)
        
        text = recognizer.recognize_google(audio_data)
        return jsonify({"text": text})
    except sr.UnknownValueError:
        return jsonify({"error": "Didn't catch that. Try again."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("="*60)
    print(" CYNTHIA WEB SERVER RUNNING ON http://localhost:5000")
    print("="*60)
    app.run(host="0.0.0.0", port=5000, debug=False)
