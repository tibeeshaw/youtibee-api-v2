import os
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import base64

app = Flask(__name__)

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://youtube.tibeechaw.com",
]

CORS(app, resources={r"/download/audio": {"origins": ALLOWED_ORIGINS}})

def get_cookies_from_env():
    # Placeholder for getting cookies from the environment variable
    cookies_base64 = os.getenv('YT_COOKIE_BASE64')
    if not cookies_base64:
        raise ValueError("YT_COOKIE_BASE64 environment variable is not set.")
    return base64.b64decode(cookies_base64).decode('utf-8')  # In a real scenario, you would decode this and write to the file as needed.

@app.route('/download/audio', methods=['GET'])
def download_audio():
    video_url = request.args.get('url')
    
    if not video_url:
        return jsonify({'error': 'No video URL provided'}), 400
    
    cookie_file_path = 'cookies.txt'

    try:
        cookies = get_cookies_from_env()  # Get cookies from the environment variable
        # Print cookies for debugging (remove in production)
        print(f"Cookies: {cookies}")  

        # Write cookies to a temporary file
        with open(cookie_file_path, 'w') as cookie_file:
            cookie_file.write(cookies)

        ydl_opts = {
            'format': 'm4a/bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
                'preferredquality': '192',
            }],
            'outtmpl': 'downloads/%(title)s.%(ext)s',  # Save location
            'cookiefile': cookie_file_path,  # Pass the cookies directly
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=True)
            title = info_dict.get('title', 'Unknown Title')
            downloaded_file_path = f"downloads/{title}.m4a"  # Assuming 'm4a' format

        # Send the file to the client
        response = send_file(downloaded_file_path, as_attachment=True, download_name=f"{title}.m4a")

        # Clean up the downloaded file after sending it
        os.remove(downloaded_file_path)

        return response

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        # Clean up the cookie file after usage
        if os.path.exists(cookie_file_path):
            os.remove(cookie_file_path)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
