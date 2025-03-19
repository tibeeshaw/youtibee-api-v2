import yt_dlp
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/download/audio', methods=['GET'])
def download_audio():
    video_url = request.args.get('url')
    if not video_url:
        return jsonify({'error': 'No video URL provided'}), 400

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',  # Correct key
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'downloads/%(title)s.%(ext)s',  # Save location
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=True)
            title = info_dict.get('title', None)
            return jsonify({'message': f'Audio downloaded for: {title}'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
