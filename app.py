from flask import Flask, jsonify, render_template
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import logging
from flask_caching import Cache  # This is the correct import
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
data_cache = {}
scheduler = None
initialized = False

def fetch_data():
    global data_cache
    url = "https://bonds-dashboard-api-deaf0d7d55b7.herokuapp.com/collector/inventory"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        raw_data = response.json()
        processed_data = {}
        timestamp = datetime.now().isoformat() 
        for chain in raw_data:
            chainId = str(chain['chainId'])
            totalRemainingValue = chain.get('totalRemainingValue')
            if totalRemainingValue is not None:
                totalRemainingValue = float(totalRemainingValue)
            else:
                totalRemainingValue = 0.0
            if chainId not in processed_data:
                processed_data[chainId] = {}
            processed_data[chainId][timestamp] = totalRemainingValue
        
        processed_data['aggregate'] = {
            timestamp: sum(float(chain.get('totalRemainingValue', 0)) for chain in raw_data if chain.get('totalRemainingValue') is not None)
        }
        
        data_cache = processed_data
        logger.info("Data fetched and processed successfully")
    except requests.RequestException as e:
        logger.error(f"Error fetching data: {e}")
        data_cache = {}  # Set to empty dict on error
    except Exception as e:
        logger.error(f"Error processing data: {e}")
        data_cache = {}  # Set to empty dict on error

def start_scheduler():
    global scheduler
    if scheduler is None:
        scheduler = BackgroundScheduler()
        scheduler.add_job(fetch_data, 'interval', hours=4)
        scheduler.start()
        logger.info("Scheduler started")

@app.before_request
def initialize():
    global initialized
    if not initialized:
        fetch_data()  # Fetch data immediately
        start_scheduler()  # Start the scheduler
        initialized = True

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
        logger.error(f"Error in get_data route: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)