from flask import Flask, render_template, request, send_file, jsonify, after_this_request
import yt_dlp
import io
import tempfile
import os
import threading
import uuid
import glob
import shutil

app = Flask(__name__)

tasks = {}

def progress_update(d, task_id):
    if d['status'] == 'downloading':
        total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
        if total_bytes:
            percent = (d['downloaded_bytes'] / total_bytes) * 100
            tasks[task_id]['progress'] = min(100, percent)
    elif d['status'] == 'finished':
        tasks[task_id]['progress'] = 100

@app.route('/')
def index():
    """Renders the main page."""
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    """Handles the video download request."""
    video_url = request.form.get('url')

    if not video_url:
        return jsonify({'error': 'Please provide a video URL.'}), 400

    task_id = str(uuid.uuid4())

    try:
        # Get info first
        ydl_opts_info = {
            'noplaylist': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info_dict = ydl.extract_info(video_url, download=False)
            video_title = info_dict.get('title', 'video')
            video_ext = info_dict.get('ext', 'mp4')
            filename = f"{video_title}.{video_ext}"

        tasks[task_id] = {
            'progress': 0,
            'done': False,
            'error': None,
            'filepath': None,
            'filename': filename,
            'tmpdir': None
        }

        def download_in_thread():
            try:
                tmpdir = tempfile.mkdtemp()
                tasks[task_id]['tmpdir'] = tmpdir
                ydl_opts = {
                    'format': 'best',
                    'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
                    'noplaylist': True,
                    'progress_hooks': [lambda d: progress_update(d, task_id)]
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl_download:
                    ydl_download.download([video_url])

                # Find the downloaded file
                files = glob.glob(os.path.join(tmpdir, '*'))
                if files:
                    # Assume the first (or only) file is the final one; in practice, sort by name or check size
                    filepath = max(files, key=os.path.getsize)  # largest file as final
                    tasks[task_id]['filepath'] = filepath
                    actual_filename = os.path.basename(filepath)
                    tasks[task_id]['filename'] = actual_filename
                tasks[task_id]['progress'] = 100
                tasks[task_id]['done'] = True
            except Exception as e:
                tasks[task_id]['error'] = f'An error occurred during download: {str(e)}'
                tasks[task_id]['done'] = True

        thread = threading.Thread(target=download_in_thread, daemon=True)
        thread.start()

        return jsonify({'task_id': task_id})

    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

@app.route('/progress/<task_id>')
def get_progress(task_id):
    """Get progress for a task."""
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify({
        'progress': task['progress'],
        'done': task['done'],
        'error': task['error'],
        'filename': task.get('filename')
    })

@app.route('/file/<task_id>')
def get_file(task_id):
    """Serve the downloaded file."""
    task = tasks.get(task_id)
    if not task or not task['done'] or task['error'] or not task['filepath']:
        if task and task['error']:
            return jsonify({'error': task['error']}), 500
        return jsonify({'error': 'Download not ready or failed'}), 404

    try:
        ext = task['filepath'].split('.')[-1]
        @after_this_request
        def cleanup(response):
            try:
                os.unlink(task['filepath'])
                if task.get('tmpdir'):
                    shutil.rmtree(task['tmpdir'])
            except Exception:
                pass
            if task_id in tasks:
                del tasks[task_id]
            return response

        return send_file(
            task['filepath'],
            as_attachment=True,
            download_name=task['filename'],
            mimetype=f'video/{ext}'
        )
    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)