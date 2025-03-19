import yt_dlp
import os
import base64
from flask import Flask, request, jsonify

app = Flask(__name__)

# Function to decode base64 and return the cookie string
def get_cookies_from_env():
    cookie_base64 = os.getenv('YT_COOKIE_BASE64')  # Get the base64 string from environment
    if not cookie_base64:
        raise ValueError('No cookies found in environment variable')
    
    cookie_bytes = base64.b64decode(cookie_base64)  # Decode the base64 string
    return cookie_bytes.decode('utf-8')  # Return as string

@app.route('/download/audio', methods=['GET'])
def download_audio():
    video_url = request.args.get('url')
    
    if not video_url:
        return jsonify({'error': 'No video URL provided'}), 400

    try:
        cookies = get_cookies_from_env()  # Get cookies from the environment variable
        print(f"Cookies: {cookies}")  # You can remove this line in production

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegAudioConvertor',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': 'downloads/%(title)s.%(ext)s',  # Save location
            'cookiefile': cookies,  # Pass the cookies directly
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=True)
            title = info_dict.get('title', None)
            return jsonify({'message': f'Audio downloaded for: {title}'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
