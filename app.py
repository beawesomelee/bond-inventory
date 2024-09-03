from flask import Flask, jsonify, render_template
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import logging
from flask_caching import Cache  # This is the correct import
import os
import json
import psycopg2
from psycopg2.extras import Json
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
data_cache = {}
scheduler = None
initialized = False

# Database connection
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgres://u5sb0048vfu1g0:p747121bf78784730076f00603de6be1e96200eafa77ba66e872c511fe134835d@c5hilnj7pn10vb.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/dajdlrk8ce1154')

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

url = urlparse(DATABASE_URL)
db_config = {
    'dbname': url.path[1:],
    'user': url.username,
    'password': url.password,
    'host': url.hostname,
    'port': url.port
}

def get_db_connection():
    return psycopg2.connect(**db_config)

def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS inventory_data (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP,
                    data JSONB
                )
            """)
        conn.commit()

def save_data(data):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO inventory_data (timestamp, data) VALUES (NOW(), %s)",
                (Json(data),)
            )
        conn.commit()

def load_data():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM inventory_data ORDER BY timestamp DESC LIMIT 1")
            result = cur.fetchone()
            return result[0] if result else {}

def fetch_data():
    global data_cache
    url = "https://bonds-dashboard-api-deaf0d7d55b7.herokuapp.com/collector/inventory"
    try:
        # Load existing data
        data_cache = load_data()
        
        logger.info("Attempting to fetch data from API")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        raw_data = response.json()
        if not raw_data:
            logger.warning("API returned empty data")
            return
        logger.info(f"Received data: {raw_data[:100]}...")  # Log first 100 characters of raw data
        
        timestamp = datetime.now().isoformat()
        for chain in raw_data:
            chainId = str(chain['chainId'])
            totalRemainingValue = chain.get('totalRemainingValue')
            if totalRemainingValue is not None:
                totalRemainingValue = float(totalRemainingValue)
            else:
                totalRemainingValue = 0.0
            if chainId not in data_cache:
                data_cache[chainId] = {}
            # Add new data point without overwriting existing ones
            data_cache[chainId][timestamp] = totalRemainingValue
        
        # Calculate and store aggregate
        aggregate_value = sum(float(chain.get('totalRemainingValue', 0)) for chain in raw_data if chain.get('totalRemainingValue') is not None)
        if 'aggregate' not in data_cache:
            data_cache['aggregate'] = {}
        data_cache['aggregate'][timestamp] = aggregate_value
        
        # Save updated data
        save_data(data_cache)
        
        logger.info(f"Processed data: {data_cache}")
    except requests.RequestException as e:
        logger.error(f"Error fetching data: {e}")
    except ValueError as e:
        logger.error(f"Error parsing JSON data: {e}")
    except Exception as e:
        logger.error(f"Unexpected error processing data: {e}")

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
            logger.info("Data cache is empty, loading from file")
            data_cache = load_data()
        if not data_cache:
            logger.info("No data in file, fetching new data")
            fetch_data()
        if not data_cache:
            logger.warning("No data available after fetch attempt")
            return jsonify({"error": "No data available"}), 404
        logger.info(f"Returning data: {data_cache}")
        return jsonify(data_cache)
    except Exception as e:
        logger.error(f"Error in get_data route: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)