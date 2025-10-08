from flask import Flask, render_template, request, send_file, jsonify
import yt_dlp
import io
import sys

app = Flask(__name__)

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

    try:
        # yt-dlp options
        ydl_opts = {
            'format': 'best',
            'outtmpl': '%(title)s.%(ext)s',
            'noplaylist': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=False)
            video_title = info_dict.get('title', 'video')
            video_ext = info_dict.get('ext', 'mp4')
            filename = f"{video_title}.{video_ext}"

            # Download the video to an in-memory buffer
            buffer = io.BytesIO()
            ydl_opts['outtmpl'] = '-'  # Direct output to stdout
            ydl_opts['logtostderr'] = True
            
            # Temporarily redirect stdout to capture the video data
            original_stdout = sys.stdout
            sys.stdout = buffer
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl_download:
                ydl_download.download([video_url])
                
            sys.stdout = original_stdout # Restore stdout
            buffer.seek(0)

            return send_file(
                buffer,
                as_attachment=True,
                download_name=filename,
                mimetype=f'video/{video_ext}'
            )

    except yt_dlp.utils.DownloadError as e:
        return jsonify({'error': f'An error occurred during download: {e}'}), 500
    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {e}'}), 500

if __name__ == '__main__':
    app.run(debug=True)