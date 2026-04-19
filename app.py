import os
import threading
from flask import Flask, request, jsonify, send_from_directory, render_template, Response
from flask_cors import CORS
from downloader import get_video_info, download_audio, ensure_ffmpeg, DOWNLOAD_DIR
import queue
import json

import sys

if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Ensure FFmpeg is available on startup
threading.Thread(target=ensure_ffmpeg, daemon=True).start()

# Global dictionary to track progress of downloads
download_progress = {}

@app.route('/')
def serve_index():
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/api/info', methods=['POST'])
def api_get_info():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({'success': False, 'error': 'URL is required'}), 400

    info = get_video_info(url)
    return jsonify(info)

@app.route('/api/download', methods=['POST'])
def api_download():
    data = request.json
    url = data.get('url')
    quality = data.get('quality', '192')
    
    if not url:
        return jsonify({'success': False, 'error': 'URL is required'}), 400

    # Ensure downloads directory exists
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    
    # Reset or initialize progress
    download_id = hash(url)
    download_progress[download_id] = {'status': 'starting', 'progress': 0}

    def hook(d):
        if d['status'] == 'downloading':
            try:
                # Remove ANSI escape sequences and convert to string
                p = d['_percent_str']
                # Clean up the string to convert to float
                p = p.replace('\x1b[0;94m', '').replace('\x1b[0m', '').replace('%', '').strip()
                download_progress[download_id] = {
                    'status': 'downloading',
                    'progress': float(p)
                }
            except Exception:
                pass
        elif d['status'] == 'finished':
            download_progress[download_id] = {
                'status': 'processing',
                'progress': 100
            }

    try:
        result = download_audio(url, quality, progress_hook=hook)
        if result['success']:
            filename = os.path.basename(result['file_path'])
            return jsonify({
                'success': True,
                'download_url': f'/api/files/{filename}'
            })
        else:
            return jsonify(result), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/progress/<int:download_id>')
def api_progress(download_id):
    progress = download_progress.get(download_id, {'status': 'not_found', 'progress': 0})
    return jsonify(progress)

@app.route('/api/files/<path:filename>')
def serve_file(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

import webbrowser
from threading import Timer

def open_browser():
    webbrowser.open_new('http://127.0.0.1:5000/')

if __name__ == '__main__':
    Timer(1, open_browser).start()
    app.run(debug=True, use_reloader=False, port=5000)
