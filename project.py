from flask import Flask, request, send_from_directory, redirect, session, jsonify
import sqlite3
import bcrypt
import requests
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta, timezone
import base64
from math import radians, sin, cos, sqrt, atan2

# secret key security
load_dotenv()

app = Flask(__name__, static_folder='public')
app.secret_key = os.environ.get('SECRET_KEY')
if not app.secret_key:
    if os.environ.get('FLASK_ENV') == 'development':
        app.secret_key = os.urandom(24)  # temp key for testing
        print("Warning: Using a temporary secret key for development.")
    else:
        raise ValueError("Error: You must set a SECRET_KEY in production!")
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS
app.config['PERMANENT_SESSION_LIFETIME'] = 24 * 60 * 60  # 24 hour session
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB to fix entity to large error 413

# will run on port in dev and ready for deploying to production
def main():
    """Run the Flask development server."""
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

# create uploads directory
uploads_dir = os.path.join('static', 'uploads')
if not os.path.exists(uploads_dir):
    os.makedirs(uploads_dir)

def init_db():
    with sqlite3.connect('fishing.db') as conn:
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
        c.execute('''CREATE TABLE IF NOT EXISTS catches (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            image TEXT,
            date TEXT,
            location TEXT,
            lure TEXT,
            size TEXT,
            weight TEXT,
            tide TEXT,
            moon_phase TEXT,
            latitude REAL,
            longitude REAL
        )''')
        conn.commit()
init_db()

# load NOAA tide stations
stations = []
def load_stations():
    """Load the list of NOAA tide stations with predictions."""
    global stations
    url = "https://api.tidesandcurrents.noaa.gov/mdapi/v1.0/webapi/stations.json?type=tidepredictions"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        stations = data['stations']
    else:
        stations = []
load_stations()

# functions grouped

def format_time(date_str):
    """Format the time from ISO format to 'AM/PM'."""
    time_str = date_str.split('T')[1][:5]
    hours, minutes = map(int, time_str.split(':'))
    period = 'AM' if hours < 12 else 'PM'  # am pm logic
    hours = hours % 12 or 12  # 24 hour to 12-hour issues all fixed with this new code
    return f"{hours}:{minutes:02d}{period}"

def geocode_location(location):
    """Convert an automatic 'lat, lon' location string to latitude and longitude."""
    try:
        lat, lon = map(float, location.split(','))
        return lat, lon
    except ValueError:
        print(f"Error parsing location '{location}' as coordinates")
        return None, None

def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points on Earth."""
    R = 6371  # earth radius in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def find_nearest_station(lat, lon, stations):
    """Find the tide station closest to the given coordinates."""
    min_distance = float('inf')
    nearest_station = None
    for station in stations:
        station_lat = float(station['lat'])
        station_lon = float(station['lng'])
        distance = haversine(lat, lon, station_lat, station_lon)
        if distance < min_distance:
            min_distance = distance
            nearest_station = station
    return nearest_station

# NOAA tide data
def get_tide_prediction(station_id, date_time):
    """Get the tide level prediction for a specific station and time."""
    begin_date = date_time.strftime("%Y%m%d %H:%M")
    end_date = (date_time + timedelta(minutes=1)).strftime("%Y%m%d %H:%M")
    url = f"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=predictions&begin_date={begin_date}&end_date={end_date}&datum=MLLW&station={station_id}&time_zone=lst_ldt&units=english&format=json"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if 'predictions' in data and data['predictions']:
            prediction = data['predictions'][0]
            return prediction['v']
    return None

def get_moon_phase(date):
    """Calculate the moon phase based on the given date."""
    known_new_moon = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    cycle_length = 29.53058867  # number of lunar cycle days
    days_since_new_moon = (date - known_new_moon).total_seconds() / (24 * 3600)
    phase_fraction = (days_since_new_moon % cycle_length) / cycle_length
    if phase_fraction < 0:
        phase_fraction += 1
    if phase_fraction < 0.02 or phase_fraction >= 0.98:
        return 'New Moon'
    elif phase_fraction < 0.23:
        return 'Waxing Crescent'
    elif phase_fraction < 0.27:
        return 'First Quarter'
    elif phase_fraction < 0.48:
        return 'Waxing Gibbous'
    elif phase_fraction < 0.52:
        return 'Full Moon'
    elif phase_fraction < 0.73:
        return 'Waning Gibbous'
    elif phase_fraction < 0.77:
        return 'Last Quarter'
    elif phase_fraction < 0.98:
        return 'Waning Crescent'
    return 'Unknown'

# all routes grouped for style, my original code had routes and functions all together; was confusing me when debugging
@app.route('/')
def index():
    if 'user' in session:
        return send_from_directory('public', 'dashboard.html')
    return send_from_directory('public', 'login.html')

# storing/serving photos from the catch log
@app.route('/static/uploads/<filename>')
def serve_uploaded_file(filename):
    return send_from_directory('static/uploads', filename)

@app.route('/calendar')
def calendar():
    if 'user' not in session:
        return redirect('/')
    return send_from_directory('public', 'calendar.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return send_from_directory('public', 'register.html')
    elif request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            return 'Missing username or password', 400
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        try:
            with sqlite3.connect('fishing.db') as conn:
                c = conn.cursor()
                c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed))
                conn.commit()
                user_id = c.lastrowid
                session['user'] = {'id': user_id, 'username': username}
                return redirect('/')
        except sqlite3.IntegrityError:
            return 'Username already exists', 400

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return send_from_directory('public', 'login.html')
    elif request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            return 'Missing username or password', 400
        with sqlite3.connect('fishing.db') as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = c.fetchone()
        if user and bcrypt.checkpw(password.encode('utf-8'), user[2]):
            session['user'] = {'id': user[0], 'username': user[1]}
            return redirect('/')
        return 'Invalid credentials', 401

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return redirect('/')

@app.route('/catch', methods=['GET', 'POST'])
def catch():
    if 'user' not in session:
        return 'Not logged in', 401
    if request.method == 'GET':
        return send_from_directory('public', 'catch.html')
    elif request.method == 'POST':
        image_data = request.form.get('image_data', '')
        date_str = request.form.get('date')
        location = request.form.get('location')
        lure = request.form.get('lure')
        size = request.form.get('size')
        weight = request.form.get('weight')
        if not all([date_str, location, lure, size, weight]):
            return 'Missing required fields', 400

        # avoiding all typeerrors and other errors with offset aware issues
        date = datetime.fromisoformat(date_str.replace('T', ' ')).replace(tzinfo=timezone.utc)
        moon_phase = get_moon_phase(date)

        # get tide data and coordinates
        lat, lon = geocode_location(location)
        tide = 'Unknown'
        if lat is not None and lon is not None:
            nearest_station = find_nearest_station(lat, lon, stations)
            if nearest_station:
                station_id = nearest_station['id']
                tide_level = get_tide_prediction(station_id, date)
                tide = f"{tide_level} ft" if tide_level is not None else 'Unknown'


        image_path = ''
        if image_data and image_data.startswith('data:image'):
            comma_index = image_data.find(',')
            if comma_index != -1:
                base64_data = image_data[comma_index+1:]
                image_bytes = base64.b64decode(base64_data)
                filename = f"catch_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                filepath = os.path.join(uploads_dir, filename)
                with open(filepath, 'wb') as f:
                    f.write(image_bytes)
                image_path = filename

        with sqlite3.connect('fishing.db') as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO catches (
                user_id, image, date, location, lure, size, weight, tide, moon_phase, latitude, longitude
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (session['user']['id'], image_path, date_str, location, lure, size, weight, tide, moon_phase, lat, lon))
            conn.commit()
        return redirect('/')
# table data logic
@app.route('/catches')
def catches():
    if 'user' not in session:
        return 'Not logged in', 401
    date = request.args.get('date')
    with sqlite3.connect('fishing.db') as conn:
        c = conn.cursor()
        if date:
            c.execute('SELECT * FROM catches WHERE user_id = ? AND date LIKE ?', (session['user']['id'], date + '%'))
        else:
            c.execute('SELECT * FROM catches WHERE user_id = ?', (session['user']['id'],))
        rows = c.fetchall()
    if date:
        catches = []
        for row in rows:
            catch_data = {
                'id': row[0],
                'image': row[2],
                'date': row[3],
                'location': row[4],
                'lure': row[5],
                'size': row[6],
                'weight': row[7],
                'tide': row[8],
                'moon_phase': row[9],
                'latitude': row[10],
                'longitude': row[11]
            }
            if catch_data['latitude'] and catch_data['longitude']:
                catch_data['maps_link'] = f"https://www.google.com/maps?q={catch_data['latitude']},{catch_data['longitude']}"
            else:
                catch_data['maps_link'] = None
            catches.append(catch_data)
        return jsonify(catches)
    else:
        events = []
        for row in rows:
            title = format_time(row[3])  # Set title to "4:38p"
            events.append({'id': str(row[0]), 'title': title, 'start': row[3]})
        return jsonify(events)

@app.route('/weather')
def weather():
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    if not lat or not lon:
        return jsonify({'error': 'Missing lat or lon'}), 400
    api_key = os.environ.get('WEATHER_API_KEY')
    url = f'http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=imperial'
    response = requests.get(url)
    if response.status_code == 200:
        return jsonify(response.json())
    return jsonify({'error': 'Weather API error'}), 500


if __name__ == '__main__':
    main()
