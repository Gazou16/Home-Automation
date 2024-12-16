import os
from collections import deque
from email.policy import default
from functools import wraps

import paho.mqtt.client as paho
import pytz
import flask
from flask import Flask, render_template, session, redirect, url_for, jsonify, json, flash
from markupsafe import Markup
from flask import request
import sqlite3
from datetime import datetime, timedelta


app = flask.Flask(__name__)
app.secret_key = "your_secret_key"
app.config["Debug"] = True
app.secret_key = os.urandom(24)  # Secret key for session management

# Hardcoded credentials for login
USERNAME = 'rhc'
PASSWORD = '123'

# Local timezone
LOCAL_TIMEZONE = pytz.timezone("America/Toronto")  # Adjust for your local timezone

# MQTT Configuration
BROKER = "rpi2024.local"  # MQTT broker address
PORT = 1883  # MQTT port
TOPIC_TEMPERATURE = "home/temperature"  # Topic for temperature data
TOPIC_HUMIDITY = "home/humidity"  # Topic for humidity data
TOPIC_MOTION = "home/motion"  # Topic for motion data
TOPIC_SOUND = "home/sound"  # Topic for sound data
TOPIC_LED_CONTROL = "led/control"  # Topic for controlling LEDs
TOPIC_LED_STATUS = "led/status"  # Topic for LED status updates

# Store live sensor and status data in memory
sensor_data = {
    "temperature": deque(maxlen=20),  # Store the last 20 temperature readings
    "humidity": deque(maxlen=20),  # Store the last 20 humidity readings
    "motion": None,  # Current motion level
    "sound": None,  # Current motion level
    "led_status": "Unknown",  # Current LED status
}

# Tracks the last time sensor data was saved to the database
last_saved_time = datetime.now(LOCAL_TIMEZONE)

# MQTT Client setup
mqtt_client = paho.Client()


def init_db():
    """
    Initializes the SQLite database to store sensor data.
    Creates a table if it doesn't exist.
    """
    conn = sqlite3.connect('home_data.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            temperature REAL,
            humidity REAL,
            motion TEXT
            sound TEXT
        )
    ''')
    conn.commit()
    conn.close()



def save_sensor_data(temperature, humidity, motion, sound):
    """
    Saves sensor data to the SQLite database with a timestamp.
    """
    conn = sqlite3.connect('home_data.db')
    c = conn.cursor()
    timestamp = datetime.now(LOCAL_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')  # Local timestamp
    c.execute('''
        INSERT INTO sensor_data (timestamp, temperature, humidity, motion, sound)
        VALUES (?, ?, ?, ?)
    ''', (timestamp, temperature, humidity, motion, sound))
    conn.commit()
    conn.close()


# MQTT Callback Functions
def on_connect(client, userdata, flags, rc):
    """
    Called when the MQTT client connects to the broker.
    Subscribes to all necessary topics.
    """
    print(f"Connected with result code {rc}")
    client.subscribe([
        (TOPIC_TEMPERATURE, 0),
        (TOPIC_HUMIDITY, 0),
        (TOPIC_MOTION, 0),
        (TOPIC_SOUND, 0),
        (TOPIC_LED_STATUS, 0)
    ])

def on_message(client, userdata, msg):
    """
    Called when a message is received on a subscribed topic.
    Updates the sensor data and status in memory.
    """
    global sensor_data, last_saved_time
    topic = msg.topic
    payload = msg.payload.decode()

    # Handle temperature updates
    if topic == TOPIC_TEMPERATURE:
        temperature = float(payload)
        sensor_data["temperature"].append(temperature)
    # Handle humidity updates
    elif topic == TOPIC_HUMIDITY:
        humidity = float(payload)
        sensor_data["humidity"].append(humidity)
    # Handle motion updates
    elif topic == TOPIC_MOTION:
        motion = "yes" if str(payload) else "no"
        sensor_data["motion"] = motion
    elif topic == TOPIC_SOUND:
        sound = "yes" if str(payload) else "no"
        sensor_data["motion"] = sound

    # Save data to the database every minute
    current_time = datetime.now(LOCAL_TIMEZONE)
    if (current_time - last_saved_time) >= timedelta(minutes=1):
        if len(sensor_data["temperature"]) > 0 and len(sensor_data["humidity"]) > 0:
            save_sensor_data(
                sensor_data["temperature"][-1],
                sensor_data["humidity"][-1],
                sensor_data["motion"],
                sensor_data["sound"]
            )
            last_saved_time = current_time

    # Handle LED status updates
    elif topic == TOPIC_LED_STATUS:
        sensor_data["led_status"] = payload


#-----------------------------------------------------------------------------------------------------------------------
#To save on a JSON file
def export_to_json(file_name):
    """
    Exports all sensor data from the SQLite database to a JSON file.
    """
    conn = sqlite3.connect('home_data.db')
    c = conn.cursor()
    c.execute('SELECT * FROM sensor_data')
    rows = c.fetchall()



    # Fetch column names for JSON keys
    column_names = [description[0] for description in c.description]

    # Convert rows to a list of dictionaries
    data = [dict(zip(column_names, row)) for row in rows]

    # Write data to JSON file
    with open(file_name, 'w') as json_file:
        json.dump(data, json_file, indent=4, default=str)  # `default=str` to handle datetime serialization

    conn.close()
    print(f"Data exported to {file_name}")


#-----------------------------------------------------------------------------------------------------------------------

# Flask login decorator
def login_required(func):
    """
    Decorator to restrict access to routes for logged-in users only.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'logged_in' in session and session['logged_in']:
            return func(*args, **kwargs)
        else:
            flash("You must log in to access this page.", "warning")
            return redirect(url_for('login'))
    return wrapper


@app.route("/notifications", methods=["GET"])
@login_required
def notifications():
    return render_template("notifications.html")


@app.route("/graphs", methods=["GET"])
@login_required
def graphs():
    return render_template("graphs.html")

@app.route("/setting", methods=["GET"])
@login_required
def settings():
    return render_template("setting.html")

#Redirect Function
@app.route("/datacollection", methods=["GET"])
@login_required
def datacollection():
    return redirect(url_for("dataCol"))


@app.route('/')
def index():
    # Check if the user is logged in
    username = session.get('username')
    return render_template('index.html', username=username)



@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login route. Validates user credentials.
    """
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == USERNAME and password == PASSWORD:
            session['logged_in'] = True
            flash("Login successful!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid credentials. Please try again.", "danger")
    return render_template('login.html')


@app.route('/logout')
def logout():
    """
    Logout route. Clears the session.
    """
    session.pop('logged_in', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))



if __name__ == "__main__":
    app.run()
    init_db()
    # Export data to JSON
    export_to_json('sensor_data.json')