import os
import socket
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import base64
import redis
import requests
import socks
import random
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# Rate limiting settings
RATE_LIMIT = int(os.getenv("RATE_LIMIT", 5))  # Max requests per window
TIME_WINDOW = int(os.getenv("TIME_WINDOW", 60))  # Time window in seconds (1 minute)

# Redis connection (Render provides an internal Redis URL)
REDIS_URL = os.getenv("REDIS_URL")  # e.g., redis://your-redis-host:6379
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

SOCKS5_PROXY = os.getenv("SOCKS5_PROXY")  # Example: socks5h://your-proxy-ip:1080

# Set up SOCKS5 proxy if configured
if SOCKS5_PROXY:
    proxy_host, proxy_port = SOCKS5_PROXY.replace("socks5h://", "").split(":")
    proxy_port = int(proxy_port)
    
    socks.set_default_proxy(socks.SOCKS5, proxy_host, proxy_port)
    socket.socket = socks.socksocket  # Override default socket with proxy support

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://youtube.tibeechaw.com",
]

CORS(app, origins=ALLOWED_ORIGINS)

# default_proxy_list = os.getenv("PROXY_LIST", "").split(",")  # Convertir en liste
# Load proxies from proxy.txt
def load_proxies(file_path="proxy.txt"):
    try:
        with open(file_path, "r") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("⚠️ proxy.txt not found, proceeding without proxies.")
        return []

default_proxy_list = load_proxies()
print(f"Liste des proxies par défaut chargés : {default_proxy_list}")

default_proxy_list = [proxy.strip() for proxy in default_proxy_list if proxy]  # Nettoyer la liste

# Récupérer des proxies gratuits depuis ProxyScrape
proxy_scrape_url = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all"

print(f"Liste des proxies nettoyés par défaut chargés : {default_proxy_list}")

def test_proxy(proxy):
    """Tests if a proxy is working and returns it if valid."""
    test_proxy = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
    try:
        test_response = requests.get("https://www.google.com", proxies=test_proxy, timeout=5)
        if test_response.status_code == 200:
            print(f"✅ Proxy works: {proxy}")
            return proxy
    except requests.RequestException:
        print(f"❌ Proxy failed: {proxy}")
    return None

def get_working_proxies(proxy_list, max_threads=10):
    """Runs proxy testing in parallel and returns a list of working proxies."""
    working_proxies = []
    
    # Run tests in parallel
    with ThreadPoolExecutor(max_threads) as executor:
        results = list(executor.map(test_proxy, proxy_list))

    # Filter out None values (failed proxies)
    working_proxies = [proxy for proxy in results if proxy]
    return working_proxies

def validate_google_token(token):
    """Validate the opaque token with Google's API and extract the email."""
    print(f"Validating Google token: {token}")
    url = f"https://www.googleapis.com/oauth2/v3/tokeninfo?access_token={token}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        print(f"Token valid. Extracted email: {data.get('email')}")
        return data.get("email")  # Extract email if token is valid
    print("Token validation failed.")
    return None

def get_cookies_from_env():
    cookies_base64 = os.getenv('YT_COOKIE_BASE64')
    if not cookies_base64:
        print("No cookies found in environment variable.")
        return ""
    print("Cookies found in environment variable.")
    return base64.b64decode(cookies_base64).decode('utf-8')

def get_secret_from_env():
    secret = os.getenv('SECRET')
    if not secret:
        print("SECRET environment variable is not set.")
        raise ValueError("SECRET environment variable is not set.")
    print("SECRET environment variable retrieved successfully.")
    return secret

@app.route("/ping", methods=["GET"])
def ping():
    print("Ping endpoint called.")
    return jsonify({"message": "pong"}), 200

@app.route("/rate-limit", methods=["GET"])
def get_rate_limit():
    """Returns the user's current rate limit usage."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    email = validate_google_token(token)

    if not email:
        return jsonify({"error": "Invalid or expired token"}), 401

    # Redis key for tracking usage per user
    redis_key = f"rate_limit:{email}"

    # Get request count from Redis
    request_count = redis_client.get(redis_key)
    if request_count is None:
        request_count = 0
    else:
        request_count = int(request_count)

    return jsonify({
        "email": email,
        "requests_used": request_count,
        "requests_remaining": max(0, RATE_LIMIT - request_count),
        "limit": RATE_LIMIT,
        "window_seconds": TIME_WINDOW
    })

@app.route('/download/audio', methods=['GET'])
def download_audio():
    print("Download audio endpoint called.")

    # Secret validation
    secret = get_secret_from_env()
    secretParam = request.args.get('secret')

    if not secretParam:
        print("No secret provided.")
        return jsonify({'error': 'No secret provided'}), 400

    secretParam = base64.b64decode(secretParam).decode('utf-8')

    if secretParam != secret:
        print("Invalid secret provided.")
        return jsonify({'error': 'Invalid secret provided'}), 403

    # Check video URL parameter
    video_url = request.args.get('url')
    if not video_url:
        print("No video URL provided.")
        return jsonify({'error': 'No video URL provided'}), 400
    print(f"Video URL: {video_url}")

    # Rate limit
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        print("Unauthorized: Missing or invalid Authorization header.")
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    email = validate_google_token(token)

    if not email:
        print("Invalid or expired token.")
        return jsonify({"error": "Invalid or expired token"}), 401

    print("Getting rate_limit from Redis for email:", email)
    redis_key = f"rate_limit:{email}"
    request_count = redis_client.get(redis_key)

    if request_count is None:
        print(f"First request for {email}. Setting rate limit.")
        redis_client.setex(redis_key, TIME_WINDOW, 1)
        request_count = 1
    else:
        request_count = int(request_count)
        print(f"Request count for {email}: {request_count}")

        if request_count >= RATE_LIMIT:
            print("Rate limit exceeded.")
            return jsonify({"error": "Rate limit exceeded. Try again later."}), 429

        redis_client.incr(redis_key)

    cookie_file_path = 'cookies.txt'

    try:
        cookies = get_cookies_from_env()
        if cookies:
            print(f"Writing cookies to {cookie_file_path}")
            with open(cookie_file_path, 'w') as cookie_file:
                cookie_file.write(cookies)
        else:
            print("No cookies provided, proceeding without cookies.")

        ydl_opts = {
            'format': 'm4a/bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
                'preferredquality': '192',
            }],
            'outtmpl': 'downloads/%(title)s.%(ext)s',
        }

        # response = requests.get(proxy_scrape_url)

        # if response.status_code == 200:
        #     proxy_list = response.text.split("\n")
        #     proxy_list = [proxy.strip() for proxy in proxy_list if proxy]  # Nettoyer la liste

        #     if proxy_list:
        #         print(f"Liste des proxies chargés depuis proxy_scrape_url: {proxy_list}")
        #     else:
        #         print("Aucun proxy trouvé dans la liste.")
        #         proxy_list = default_proxy_list.copy()
        # else:
        #     proxy_list = default_proxy_list.copy()

        # working_proxies = get_working_proxies(proxy_list)
        # proxy_list = default_proxy_list.copy()

        # if proxy_list:
        #     selected_proxy = random.choice(proxy_list)
        #     print(f"Utilisation du proxy : {selected_proxy}")
        #     ydl_opts["proxy"] = selected_proxy

        if cookies:
            ydl_opts['cookiefile'] = cookie_file_path

        print("Starting yt-dlp download...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=True)
            title = info_dict.get('title', 'Unknown Title')
            downloaded_file_path = f"downloads/{title}.m4a"
            print(f"Download complete. File saved at {downloaded_file_path}")

        response = send_file(downloaded_file_path, as_attachment=True, download_name=f"{title}.m4a")
        os.remove(downloaded_file_path)
        print(f"Downloaded file {downloaded_file_path} removed after sending.")

        if cookies and os.path.exists(cookie_file_path):
            os.remove(cookie_file_path)
            print(f"Cookie file {cookie_file_path} removed.")

        return response

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

    finally:
        if os.path.exists(cookie_file_path):
            os.remove(cookie_file_path)
            print(f"Cookie file {cookie_file_path} cleaned up in finally block.")

if __name__ == '__main__':
    print("Starting Flask app...")
    app.run(debug=True, host='0.0.0.0', port=5000)
