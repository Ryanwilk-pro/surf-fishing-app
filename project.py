from flask import Flask, request, send_from_directory, redirect, session, jsonify, render_template
import psycopg2
import sqlite3
import bcrypt
import requests
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta, timezone
import base64
from math import radians, sin, cos, sqrt, atan2
import logging
import re

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='public', template_folder='public')

# Set secret key from environment variable
app.secret_key = os.environ.get('SECRET_KEY')
if not app.secret_key:
    if os.environ.get('FLASK_ENV') == 'development':
        app.secret_key = os.urandom(24)
        print("Warning: Using a temporary secret key for development.")
    else:
        raise ValueError("Error: You must set a SECRET_KEY in production!")

# Production configurations
app.config['SESSION_COOKIE_SECURE'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 24 * 60 * 60
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['PREFERRED_URL_SCHEME'] = 'https' if os.environ.get('FLASK_ENV') != 'development' else 'http'

# Logging setup for production
if os.environ.get('FLASK_ENV') != 'development':
    logging.basicConfig(level=logging.INFO)

# Create uploads directory
uploads_dir = os.path.join('static', 'uploads')
if not os.path.exists(uploads_dir):
    os.makedirs(uploads_dir)

# Database connection function
def get_db_connection():
    if os.environ.get('FLASK_ENV') == 'development':
        db_path = os.path.join(os.path.dirname(__file__), 'fishing.db')
        conn = sqlite3.connect(db_path)
    else:
        conn = psycopg2.connect(os.environ['DATABASE_URL'])
    return conn

# Initialize database
def init_db():
    conn = get_db_connection()
    try:
        c = conn.cursor()
        if os.environ.get('FLASK_ENV') == 'development':
            c.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS catches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                longitude REAL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )''')
        else:
            c.execute('''CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS catches (
                id SERIAL PRIMARY KEY,
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
                longitude REAL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )''')
        conn.commit()
        print("Tables created successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")
        if os.environ.get('FLASK_ENV') != 'development':
            logging.error(f"Error initializing database: {e}")
    finally:
        conn.close()

# Load NOAA tide stations
stations = []
def load_stations():
    """Load the list of NOAA tide stations with predictions."""
    global stations
    url = "https://api.tidesandcurrents.noaa.gov/mdapi/v1.0/webapi/stations.json?type=tidepredictions"
    response = requests.get(url)
    if response.status_code == 200:
        stations = response.json()['stations']
    else:
        stations = []

# Helper functions
def format_time(date_str):
    """Format the time from ISO format to 'AM/PM'."""
    time_str = date_str.split('T')[1][:5]
    hours, minutes = map(int, time_str.split(':'))
    period = 'AM' if hours < 12 else 'PM'
    hours = hours % 12 or 12
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
    R = 6371  # Earth radius in km
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
    cycle_length = 29.53058867  # Lunar cycle in days
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

# Validation functions for usernames and passwords
def validate_username(username):
    """Validate username: 3-20 characters, alphanumeric and underscores only."""
    if len(username) < 3 or len(username) > 20:
        return False, "Username must be between 3 and 20 characters"
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "Username can only contain letters, numbers, and underscores"
    return True, ""

def validate_password(password, confirm_password=None):
    """Validate password: min 8 chars, with upper, lower, digit, and special char."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    if not re.search(r'[!@#$%^&*]', password):
        return False, "Password must contain at least one special character (!@#$%^&*)"
    if confirm_password is not None and password != confirm_password:
        return False, "Passwords do not match"
    return True, ""

# Routes
@app.route('/')
def index():
    if 'user' in session:
        return send_from_directory('public', 'dashboard.html')
    return send_from_directory('public', 'login.html')

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
        confirm_password = request.form.get('confirm_password')
        if not username or not password or not confirm_password:
            logging.error("Missing username, password, or confirm password")
            return jsonify({'success': False, 'message': 'Missing username, password, or confirm password'}), 400

        valid_username, username_error = validate_username(username)
        if not valid_username:
            logging.error(f"Invalid username: {username_error}")
            return jsonify({'success': False, 'message': username_error}), 400

        valid_password, password_error = validate_password(password, confirm_password)
        if not valid_password:
            logging.error(f"Invalid password: {password_error}")
            return jsonify({'success': False, 'message': password_error}), 400

        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        hashed_str = hashed.decode('utf-8')
        conn = get_db_connection()
        try:
            c = conn.cursor()
            if os.environ.get('FLASK_ENV') == 'development':
                c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_str))
                user_id = c.lastrowid
            else:
                c.execute('INSERT INTO users (username, password) VALUES (%s, %s) RETURNING id', (username, hashed_str))
                user_id = c.fetchone()[0]
            conn.commit()
            session['user'] = {'id': user_id, 'username': username}
            logging.info(f"User registered: {username}")
            return jsonify({'success': True, 'redirect': '/'}), 200
        except (sqlite3.IntegrityError, psycopg2.IntegrityError):
            logging.error(f"Username already exists: {username}")
            return jsonify({'success': False, 'message': 'Username already exists'}), 400
        except Exception as e:
            logging.error(f"Error during registration: {e}")
            return jsonify({'success': False, 'message': 'Registration failed'}), 500
        finally:
            conn.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return send_from_directory('public', 'login.html')
    elif request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            logging.error("Missing username or password")
            return 'Missing username or password', 400
        conn = get_db_connection()
        try:
            c = conn.cursor()
            if os.environ.get('FLASK_ENV') == 'development':
                c.execute('SELECT id, username, password FROM users WHERE username = ?', (username,))
            else:
                c.execute('SELECT id, username, password FROM users WHERE username = %s', (username,))
            user = c.fetchone()
            if user:
                logging.info(f"User found: {user[1]}")
                stored_hash = user[2].encode('utf-8')
                if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
                    session['user'] = {'id': user[0], 'username': user[1]}
                    logging.info("Password matched")
                    return redirect('/')
                else:
                    logging.error("Password did not match")
            else:
                logging.error("No user found")
            return 'Invalid credentials', 401
        except Exception as e:
            logging.error(f"Error during login: {e}")
            return 'Login failed', 500
        finally:
            conn.close()

@app.route('/account', methods=['GET', 'POST'])
def account():
    if 'user' not in session:
        return redirect('/login')

    if request.method == 'GET':
        return render_template('account.html', username=session['user']['username'], message=None)

    elif request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not old_password or not new_password or not confirm_password:
            logging.error("Missing old password, new password, or confirm password")
            return render_template('account.html', username=session['user']['username'], message='Missing old password, new password, or confirm password'), 400

        # Validate new password
        valid_password, password_error = validate_password(new_password, confirm_password)
        if not valid_password:
            logging.error(f"Invalid new password: {password_error}")
            return render_template('account.html', username=session['user']['username'], message=password_error), 400

        # Verify old password and update if correct
        conn = get_db_connection()
        try:
            c = conn.cursor()
            user_id = session['user']['id']
            if os.environ.get('FLASK_ENV') == 'development':
                c.execute('SELECT password FROM users WHERE id = ?', (user_id,))
            else:
                c.execute('SELECT password FROM users WHERE id = %s', (user_id,))
            user = c.fetchone()
            if user:
                stored_hash = user[0].encode('utf-8')
                if bcrypt.checkpw(old_password.encode('utf-8'), stored_hash):
                    new_hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
                    new_hashed_str = new_hashed.decode('utf-8')
                    if os.environ.get('FLASK_ENV') == 'development':
                        c.execute('UPDATE users SET password = ? WHERE id = ?', (new_hashed_str, user_id))
                    else:
                        c.execute('UPDATE users SET password = %s WHERE id = %s', (new_hashed_str, user_id))
                    conn.commit()
                    logging.info(f"Password updated for user ID: {user_id}")
                    return render_template('account.html', username=session['user']['username'], message='Password updated successfully')
                else:
                    logging.error("Old password incorrect")
                    return render_template('account.html', username=session['user']['username'], message='Incorrect old password'), 401
            else:
                logging.error("User not found")
                return render_template('account.html', username=session['user']['username'], message='User not found'), 404
        except Exception as e:
            logging.error(f"Error updating password: {e}")
            return render_template('account.html', username=session['user']['username'], message='Failed to update password'), 500
        finally:
            conn.close()

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

        date = datetime.fromisoformat(date_str.replace('T', ' ')).replace(tzinfo=timezone.utc)
        moon_phase = get_moon_phase(date)

        lat, lon = geocode_location(location)
        tide = 'Unknown'
        if lat is not None and lon is not None:
            nearest_station = find_nearest_station(lat, lon, stations)
            if nearest_station:
                station_id = nearest_station['id']
                tide_level = get_tide_prediction(station_id, date)
                tide = f"{tide_level} ft" if tide_level is not None else 'Unknown'

        image_path = ''
        try:
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
        except Exception as e:
            logging.error(f"Error saving image: {e}")
            image_path = ''

        conn = get_db_connection()
        try:
            c = conn.cursor()
            user_id = int(session['user']['id'])
            if os.environ.get('FLASK_ENV') == 'development':
                c.execute('''INSERT INTO catches (
                    user_id, image, date, location, lure, size, weight, tide, moon_phase, latitude, longitude
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                          (user_id, image_path, date_str, location, lure, size, weight, tide, moon_phase, lat, lon))
            else:
                c.execute('''INSERT INTO catches (
                    user_id, image, date, location, lure, size, weight, tide, moon_phase, latitude, longitude
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                          (user_id, image_path, date_str, location, lure, size, weight, tide, moon_phase, lat, lon))
            conn.commit()
            return redirect('/')
        except Exception as e:
            logging.error(f"Error saving catch: {e}")
            return 'Failed to save catch', 500
        finally:
            conn.close()

@app.route('/catches')
def catches():
    if 'user' not in session:
        return 'Not logged in', 401
    date = request.args.get('date')
    conn = get_db_connection()
    try:
        c = conn.cursor()
        if date:
            if os.environ.get('FLASK_ENV') == 'development':
                c.execute('SELECT * FROM catches WHERE user_id = ? AND date LIKE ?', (session['user']['id'], date + '%'))
            else:
                c.execute('SELECT * FROM catches WHERE user_id = %s AND date LIKE %s', (session['user']['id'], date + '%'))
        else:
            if os.environ.get('FLASK_ENV') == 'development':
                c.execute('SELECT * FROM catches WHERE user_id = ?', (session['user']['id'],))
            else:
                c.execute('SELECT * FROM catches WHERE user_id = %s', (session['user']['id'],))
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
                title = format_time(row[3])
                events.append({'id': str(row[0]), 'title': title, 'start': row[3]})
            return jsonify(events)
    except Exception as e:
        logging.error(f"Error fetching catches: {e}")
        return 'Failed to fetch catches', 500
    finally:
        conn.close()

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

# Error handlers for production
@app.errorhandler(404)
def not_found(error):
    return 'Page not found', 404

@app.errorhandler(500)
def server_error(error):
    return 'Internal server error', 500

# Initialize database and load stations
init_db()
load_stations()

# Run locally in development
if os.environ.get('FLASK_ENV') == 'development':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)