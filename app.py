from flask import Flask, jsonify, render_template
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import logging
from flask_caching import Cache

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
data_cache = {}

cache = Cache(app, config={'CACHE_TYPE': 'simple'})

def fetch_data():
    global data_cache
    url = "https://bonds-dashboard-api-deaf0d7d55b7.herokuapp.com/collector/inventory"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # This will raise an exception for HTTP errors
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
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        # You might want to set data_cache to a default value here
    except Exception as e:
        print(f"Error processing data: {e}")
        # You might want to set data_cache to a default value here

# Schedule data fetch every 4 hours
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_data, 'interval', hours=4)
scheduler.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
@cache.cached(timeout=3600)  # Cache for 1 hour
def get_data():
    global data_cache
    try:
        if not data_cache:
            fetch_data()  # Attempt to fetch data if cache is empty
        if not data_cache:
            return jsonify({"error": "No data available"}), 404
        return jsonify(data_cache)
    except Exception as e:
        app.logger.error(f"Error in get_data route: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    fetch_data()  # Fetch data initially
    app.run(debug=True)