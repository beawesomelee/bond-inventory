from flask import Flask, jsonify, render_template
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import logging

app = Flask(__name__)
data_cache = {}

def fetch_data():
    global data_cache
    url = "https://bonds-dashboard-api-deaf0d7d55b7.herokuapp.com/collector/inventory"
    response = requests.get(url)
    if response.status_code == 200:
        raw_data = response.json()
        processed_data = {}
        timestamp = datetime.now().isoformat() 
        for chain in raw_data:
            chainId = str(chain['chainId'])  # Convert chainId to string
            totalRemainingValue = chain.get('totalRemainingValue')
            if totalRemainingValue is not None:
                totalRemainingValue = float(totalRemainingValue)
            else:
                totalRemainingValue = 0.0
            if chainId not in processed_data:
                processed_data[chainId] = {}
            processed_data[chainId][timestamp] = totalRemainingValue
        
        # Add an aggregate of all chains
        processed_data['aggregate'] = {
            timestamp: sum(float(chain.get('totalRemainingValue', 0)) for chain in raw_data if chain.get('totalRemainingValue') is not None)
        }
        
        data_cache = processed_data
        print("Data fetched and processed:", data_cache)  # Debug print
    else:
        print(f"Failed to fetch data. Status code: {response.status_code}")

# Schedule data fetch every 4 hours
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_data, 'interval', hours=4)
scheduler.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def get_data():
    try:
        # Your existing data fetching code
        data = fetch_data_from_database()
        app.logger.info(f"Data fetched successfully: {data}")
        return jsonify(data)
    except Exception as e:
        app.logger.error(f"Error fetching data: {str(e)}")
        return jsonify({"error": "Failed to fetch data"}), 500

if __name__ == '__main__':
    fetch_data()  # Fetch data initially
    app.run(debug=True)