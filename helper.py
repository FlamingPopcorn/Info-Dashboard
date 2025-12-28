import calendar
from datetime import datetime

import speedtest, json

def get_calendar_data():
    now = datetime.now()
    year = now.year
    month = now.month
    today = now.day
    
    # Create a calendar object
    cal = calendar.Calendar()
    
    # monthdayscalendar returns a list of weeks, 
    # where each week is a list of day numbers (0 for empty slots)
    raw_weeks = cal.monthdayscalendar(year, month)
    
    formatted_weeks = []
    for week in raw_weeks:
        week_data = []
        for day_num in week:
            week_data.append({
                "day": day_num if day_num != 0 else None,
                "is_today": (day_num == today),
                "has_event": False # You can add logic here to check your DB
            })
        formatted_weeks.append(week_data)
        
    return {
        "month_name": now.strftime("%B"),
        "year": year,
        "calendar_weeks": formatted_weeks
    }

def sort_forecast_hours_to_days(forecast_hours):
    forecast_days = []
    prev_day = -1
    for hour in forecast_hours:
        icon = f"<img src=https://openweathermap.org/img/wn/{hour['weather'][0]['icon']}.png>"
        hour['icon_PNG'] = icon

        hour['formatted_time'] = datetime.fromtimestamp(hour['dt']).strftime('%#I %p')

        if forecast_days == []:
            forecast_days.append({"day": datetime.fromtimestamp(hour['dt']).strftime('%A, %B %#d, %Y'),
                                  "hour_data": [hour]})
        elif datetime.fromtimestamp(hour['dt']).day == prev_day:
            forecast_days[-1]["hour_data"].append(hour)
        else:
            forecast_days.append({"day": datetime.fromtimestamp(hour['dt']).strftime('%A, %B %#d, %Y'),
                                  "hour_data": [hour]})
        prev_day = datetime.fromtimestamp(hour['dt']).day
    return forecast_days
    
def log_network_data(time: int):
    ping = 0.00
    upload = 0.00
    download = 0.00
    attempt = 0
    while download == 0.00 and attempt < 5:
        try:
            st = speedtest.Speedtest(secure=True)

            # Finds the best server based on ping
            st.get_best_server()

            # Results are returned in bits per second; divide by 10**6 for Mbps
            ping = st.results.ping
            download = st.download() / 1_000_000
            upload = st.upload() / 1_000_000
        except Exception as e:
            print(e)
        attempt += 1


    net_db = None
    try:
        with open("network_db.json", "r") as db_file:
            db = json.load(db_file)
        
        # print({'ping': ping, 'download': download, 'upload': upload})
        db['time'].pop(0)
        db['time'].append({'ping': ping, 'download': download, 'upload': upload})

        with open("network_db.json", "w") as db_file:
            json.dump(db, db_file, indent=4)

        net_db = db
    except Exception as e:
        print(e)
        net_db = None
    
    return net_db

def sort_tasks(task_list):
    """
    Sorts tasks:
    1. Active tasks first, 'Done' tasks last.
    2. Within active tasks, sort by Date (ascending).
    3. Tasks with NO date go after active tasks WITH date.
    """
    def task_sort_key(t):
        # 1. Status Weight: 0 for active, 1 for 'Done' (pushes Done to bottom)
        status_weight = 1 if t['status'] == 'Done' else 0
        
        # 2. Date Weight: Convert YYYY-MM-DD to a sortable number
        # If date is None, use a massive number (Year 3000) so it drops to bottom of the active list
        if t['due_date']:
            try:
                date_val = datetime.strptime(t['due_date'], "%Y-%m-%d").timestamp()
            except ValueError:
                date_val = 32503680000.0 # Fallback for bad dates
        else:
            date_val = 32503680000.0 # Year 3000 (No date = bottom of active list)

        return (status_weight, date_val)

    return sorted(task_list, key=task_sort_key)
