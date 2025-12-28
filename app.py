from dotenv import load_dotenv
from os import getenv

from flask import Flask, render_template, abort, request

from icalevents.icalevents import events
from datetime import datetime, timedelta

import calendar
from datetime import date

import requests

import psutil
import speedtest

from monday_sdk import MondayClient

from os.path import exists

import helper

load_dotenv()

app = Flask(__name__)

# Access ical URL and various tokens from env
ICAL_URL = getenv("ICAL_URL")
OPENWEATHER_TOKEN = getenv("OPENWEATHER_TOKEN")
CITY = getenv("CITY")
TRACK17_TOKEN = getenv("TRACK17_TOKEN")
MONDAY_TOKEN = getenv("MONDAY_TOKEN")
MONDAY_BOARD_ID = getenv("MONDAY_BOARD_ID")
STEAM_TOKEN = getenv("STEAM_TOKEN")
STEAM_IDS = getenv("STEAM_IDS")
COUNTDOWN_DATE = getenv("COUNTDOWN_DATE")

# OpenWeather API URLs
OPENWEATHER_API_URL_CURRENT = f"https://api.openweathermap.org/data/2.5/weather?q={CITY}&units=imperial&appid={OPENWEATHER_TOKEN}"
OPENWEATHER_API_URL_HOURLY = f"https://api.openweathermap.org/data/2.5/forecast/?q={CITY}&units=imperial&appid={OPENWEATHER_TOKEN}"

# Track17 API URL
TRACK17_API_URL = "https://api.17track.net/track/v2/gettrackinfo"

# Monday API URL
MONDAY_API_URL = "https://api.monday.com/v2"

# List of routes that are allowed for External access if binded to 0.0.0.0
EXTERNAL_ROUTES = []

@app.before_request
def limit_remote_addr():
    """
    Checks the remote IP address for specific routes and aborts the request
    if the IP is not localhost (127.0.0.1).
    """
    if request.remote_addr != "127.0.0.1" and request.path not in EXTERNAL_ROUTES:
        print(f"{request.remote_addr} | {request.path}")
        abort(403)


@app.route("/")
def home():
    return render_template("index.html")

@app.route('/get-weather')
def get_weather():
    # Call your Weather API here
    # current_weather = requests.get("http://127.0.0.1:5000/").json()
    current_weather = requests.get(OPENWEATHER_API_URL_CURRENT).json()
    icon_request = requests.get(f"https://openweathermap.org/img/wn/{current_weather['weather'][0]['icon']}@2x.png")

    if icon_request.status_code == 200:
        icon = f"<img src=https://openweathermap.org/img/wn/{current_weather['weather'][0]['icon']}@2x.png>"
    else:
        # Could make a local error photo instead
        icon = "Not Found"

    # forecast_weather = requests.get("http://127.0.0.1:5000/forecast").json()
    forecast_weather = requests.get(OPENWEATHER_API_URL_HOURLY).json()

    forecast_days = helper.sort_forecast_hours_to_days(forecast_weather['list'])

    # forecast_hours.append({'time':datetime.fromtimestamp(hour['dt']).strftime('%a %#I %p'),
    #                     'icon':icon,
    #                     'main':hour['main']})

    return render_template('partials/weather_card.html',
                           weather_icon=icon,
                           current_temp=current_weather['main']['temp'],
                           condition_text=current_weather['weather'][0]['description'].title(),
                           temp_high=round(current_weather['main']['temp_max']),
                           temp_low=round(current_weather['main']['temp_min']),
                           forecast_days=forecast_days)

@app.route('/get-calendar-events')
def get_calendar_events():
    now = datetime.now()
    month_name = now.strftime("%B %Y")
    
    # Get events for the next 30 days
    try:
        upcoming_events = events(url=f"{ICAL_URL}", start=now, end=now + timedelta(days=30))
        # Sort them by start time
        upcoming_events.sort(key=lambda x: x.start)
    except Exception as e:
        print(f"Error fetching calendar: {e}")
        upcoming_events = []

    # Get the month grid (same logic as before)
    month_days = calendar.monthcalendar(now.year, now.month)
    return render_template('partials/calendar_events_card.html', 
                           days=month_days, 
                           month_name=month_name, 
                           date_today=now.day,
                           events=upcoming_events[:8]) # Show top 8 events

@app.route('/get-tasks')
def get_tasks():
    client = MondayClient(token=MONDAY_TOKEN)
    items = client.boards.fetch_all_items_by_board_id(board_id=MONDAY_BOARD_ID)

    # Define color map for statuses
    status_colors = {
        "Done": "var(--success)",              # Green
        "Working on it": "var(--warning)",     # Amber/Orange
        "Stuck": "var(--danger)",              # Red
        "Not Started": "var(--text-muted)"     # Grey
    }

    tasks = []
    for item in items:
        task = {
            'name': item.name,
            'due_date': None,
            'timeline': None,
            'status': 'Ready',
            'status_color': 'var(--text-muted)',
            'priority': ''
        }

        for column in item.column_values:
            
            title = column.column.title
            text = column.text

            match (title):
                case 'Status':
                    task['status'] = text if text else 'Ready'
                    # Map the text to a color, default to grey
                    task['status_color'] = status_colors.get(text, "var(--text-muted)")

                case 'Due date':
                    task['due_date'] = text

                case 'Priority':
                    task['priority'] = text

                case _:
                    task[title] = text

            # Inside your loop, after getting task['due_date']:
            today_str = date.today().strftime("%Y-%m-%d")

            if task['due_date'] and task['due_date'] < today_str and task['status'] != 'Done':
                # Override the color to Red if overdue
                task['status_color'] = 'var(--danger)' 
                # Optional: Append text so you see it instantly
                task['name'] = f"! {task['name']}"

        tasks.append(task)

    sorted_tasks = helper.sort_tasks(tasks)

    return render_template('/partials/tasks_card.html', tasks=tasks)

@app.route('/get-shipping')
def get_shipping():
    headers = {
        "17token": TRACK17_TOKEN,
        "Content-Type": "application/json"
    }
    
    # List of tracking numbers you've already registered in their dashboard
    # You can move this list to your .env or a database later
    numbers = ["UUSC000015359599", "LP00784261169534", "9400150206217463973212", "887400357355", "UUSC000015417916"]

    data = [{"number": n} for n in numbers]
    print(data)
    try:
        response = requests.post(TRACK17_API_URL, headers=headers, json=data)
        result = response.json()
        
        # 17TRACK returns 'accepted' for successful tracks
        packages = result.get("data", {}).get("accepted", [])
    except Exception as e:
        print(f"Shipping Error: {e}")
        packages = []

    return render_template('partials/shipping_list_card.html', packages=packages)

@app.route('/get-system')
def get_system():
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    
    disk = psutil.disk_partitions()[0]
    disk_percent = psutil.disk_usage(disk.mountpoint).percent
    
    try:
        st = speedtest.Speedtest(secure=True)

        # Finds the best server based on ping
        st.get_best_server()

        # Results are returned in bits per second; divide by 10**6 for Mbps
        download = st.download() / 1_024 / 1_024
        upload = st.upload() / 1_024 / 1_024
    except Exception as e:
        print(e)
        upload = 0.00
        download = 0.00

    ipaddr = psutil.net_if_addrs()['Ethernet 2'][1].address

    return render_template('partials/system_card.html',
                           cpu_percent=cpu_percent,
                           ram_used=f"{(memory.used/1024**3):.2f}",
                           ram_total=f"{(memory.total/1024**3):.2f}",
                           ram_percent=memory.percent,
                           disk_name = disk.device,
                           disk_percent=disk_percent,
                           net_upload_speed=f"{upload:.2f}",
                           net_download_speed=f"{download:.2f}",
                           ipaddr=ipaddr)

@app.route('/calendar')
def calendar_():
    cal = helper.get_calendar_data()

    return render_template('partials/calendar_card.html',
                           month_name=cal['month_name'],
                           year=cal['year'],
                           calendar_weeks=cal['calendar_weeks'])

@app.route('/get-clock')
def get_clock():
    return render_template('partials/clock_card.html')

@app.route('/get-countdown')
def get_countdown():
    target_date = datetime.strptime(COUNTDOWN_DATE, "%m/%d/%Y")
    now = datetime.now()
    delta = target_date - now
    
    return render_template('partials/countdown_card.html', days=delta.days, event="Graduation")

@app.route('/get-sticky-note')
def get_sticky_note():
    content = "Edit note.txt to change this message."
    if exists('note.txt'):
        with open('note.txt', 'r') as f:
            content = f.read()
            
    return render_template('partials/note_card.html', note=content)

######################### Extended Cards #############################
import random

@app.route('/get-network-graph')
def get_network_graph():
    
    time = datetime.now().hour
    net_data = helper.log_network_data(time)

    ping_data = []
    down_data = []
    up_data = []
    if net_data:
        for hour in net_data['time']:
            ping_data.append(hour['ping'])
            down_data.append(hour['download'])
            up_data.append(hour['upload'])

    # Data Labels
    labels = ["12am", "1am", "2am", "3am", "4am", "5am", "6am", "7am", "8am", "9am", "10am", "11am", "12pm", "1pm", "2pm", "3pm", "4pm", "5pm", "6pm", "7pm", "8pm", "9pm", "10pm", "11pm"]

    chart_config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Ping (ms)",
                    "data": ping_data,
                    "borderColor": "#8b5cf6", # Purple
                    "backgroundColor": "rgba(139, 92, 246, 0.1)",
                    "tension": 0.4,
                    "yAxisID": 'y', # Linked to Left Axis
                    "fill": False
                },
                {
                    "label": "Download (Mbps)",
                    "data": down_data,
                    "borderColor": "#06b6d4", # Cyan
                    "backgroundColor": "rgba(6, 182, 212, 0.1)",
                    "tension": 0.4,
                    "yAxisID": 'y1', # Linked to Right Axis
                    "fill": False
                },
                {
                    "label": "Upload (Mbps)",
                    "data": up_data,
                    "borderColor": "#10b981", # Green
                    "backgroundColor": "rgba(16, 185, 129, 0.1)",
                    "tension": 0.4,
                    "yAxisID": 'y1', # Linked to Right Axis
                    "fill": False
                }
            ]
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "interaction": {
                "mode": 'index',
                "intersect": False,
            },
            "plugins": {
                "legend": { 
                    "display": True,
                    "labels": { "color": "#94a3b8", "font": { "size": 9 } } 
                }
            },
            "scales": {
                "x": {
                    "display": False,
                    "grid": { "display": False },
                    "ticks": { "color": "#94a3b8", "font": { "size": 10 } }
                },
                "y": { # LEFT AXIS (Ping)
                    "type": 'linear',
                    "display": True,
                    "position": 'left',
                    "title": { "display": True, "text": 'ms', "color": "#8b5cf6" },
                    "grid": { "color": "rgba(255,255,255,0.05)" },
                    "ticks": { "color": "#94a3b8" }
                },
                "y1": { # RIGHT AXIS (Speed)
                    "type": 'linear',
                    "display": True,
                    "position": 'right',
                    "title": { "display": True, "text": 'Mbps', "color": "#06b6d4" },
                    "grid": { "drawOnChartArea": False }, # Keeps grid clean
                    "ticks": { "color": "#94a3b8" }
                }
            }
        }
    }

    return render_template('partials/extended/graph_card.html', chart_config=chart_config)

@app.route('/get-sensors')
def get_sensors():
    # In reality, read your I2C/Analog pins here
    sensors = [
        {"name": "Light Level", "value": "450", "unit": "lux", "status": "normal"},
        {"name": "Soil Moisture", "value": "82", "unit": "%", "status": "good"},
        {"name": "CO2", "value": "412", "unit": "ppm", "status": "normal"},
        {"name": "Rack Temp", "value": "34.2", "unit": "°C", "status": "warning"} 
    ]
    return render_template('partials/extended/sensor_card.html', sensors=sensors)

@app.route('/get-simulation')
def get_simulation():
    # No data needed, it's all client-side JS
    return render_template('partials/extended/simulation_card.html')

import feedparser

@app.route('/get-news')
def get_news():
    feed_url = "https://feeds.feedburner.com/TheHackersNews"
    feed = feedparser.parse(feed_url)
    
    # Get top 5 entries
    articles = []
    for entry in feed.entries[:5]:
        articles.append({
            "title": entry.title,
            "published": entry.published.split(" ")[4][:5] # Grabs just the time "14:30"
        })
        
    return render_template('partials/extended/news_card.html', articles=articles)

@app.route('/get-canvas')
def get_canvas():
    # Replace with YOUR school's canvas URL (e.g. canvas.instructure.com, canvas.vt.edu, etc.)
    base_url = "https://canvas.instructure.com"
    token = "YOUR_ACCESS_TOKEN_HERE"
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # "Self upcoming events" grabs assignments across ALL your classes
    url = f"{base_url}/api/v1/users/self/upcoming_events"
    
    tasks = []
    try:
        resp = requests.get(url, headers=headers).json()
        
        # Canvas returns a list of dictionaries
        for item in resp[:4]: # Limit to top 4
            tasks.append({
                "title": item.get('title'),
                "class": item.get('context_name', 'Class'), # "History 101"
                "due": item.get('start_at', '')[:10] # Grab just the YYYY-MM-DD date part
            })
    except:
        pass # If API fails, return empty list

    return render_template('partials/extended/canvas_card.html', tasks=tasks)

@app.route('/get-steam')
def get_steam():
    api_key = STEAM_TOKEN
    # List of Steam64 IDs to track (Yours + Friends)
    steam_ids = STEAM_IDS 
    
    url = f"http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={api_key}&steamids={steam_ids}"
    
    try:
        data = requests.get(url).json()
        players = data['response']['players']
        
        friends_list = []
        for p in players:
            # 0=Offline, 1=Online, 2=Busy, 3=Away, etc.
            status_code = p.get('personastate', 0)
            game_name = p.get('gameextrainfo', None)
            
            # Logic: If playing a game, show that. Else show status.
            if game_name:
                status_text = game_name
                status_color = "#a3e635" # Lime Green for gaming
                priority = 2
            elif status_code == 1:
                status_text = "Online"
                status_color = "#60a5fa" # Blue for online
                priority = 1
            else:
                status_text = "Offline"
                status_color = "#94a3b8" # Grey
                priority = 0
            
            friends_list.append({
                'name': p['personaname'],
                'avatar': p['avatar'], 
                'status': status_text,
                'color': status_color,
                'priority': priority
            })
        
        # Sort by In Game, Online, Offline and Alphabetical if tie
        friends_list.sort(key=lambda friend: (-friend['priority'], friend['name'].lower()))
    except Exception as e:
        print(f"Steam API Error: {e}")
        friends_list = []

    return render_template('partials/extended/steam_card.html', friends=friends_list)

############################### End of Extended Cards #####################################

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080)
