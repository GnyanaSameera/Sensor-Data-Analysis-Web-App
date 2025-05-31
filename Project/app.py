from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import pandas as pd
import numpy as np
import os
import zipfile
import tempfile
import shutil
import json
import plotly.express as px
import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder

app = Flask(__name__)
CORS(app)

# Configuration
TEMP_THRESHOLD = 50.0  # Default temperature threshold in °C
STRAIN_THRESHOLD = 5000.0  # Default strain threshold
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'zip'}

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_platform_from_column(column_name):
    """Extract platform (WIN/NC) from column name"""
    if 'WIN' in column_name.upper():
        return 'WIN'
    elif 'NC' in column_name.upper():
        return 'NC'
    return 'Unknown'

def categorize_sensor_type(column_name):
    """Categorize sensor type from column name"""
    column_lower = column_name.lower()
    if 'temp' in column_lower:
        return 'temperature'
    elif 'strain' in column_lower:
        return 'strain'
    return 'unknown'

def process_csv_files(zip_path):
    """Process all CSV files in the zip and return combined data"""
    all_data = []
    alerts = []
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Extract zip file
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Find all CSV files
        csv_files = []
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.endswith('.csv'):
                    csv_files.append(os.path.join(root, file))
        
        if not csv_files:
            return None, ["No CSV files found in the uploaded zip"]
        
        # Process each CSV file
        for csv_file in csv_files:
            try:
                df = pd.read_csv(csv_file)
                
                # Process each sensor column
                for col in df.columns:
                    if col == 'TimeStamp':
                        continue
                    
                    sensor_type = categorize_sensor_type(col)
                    platform = extract_platform_from_column(col)
                    
                    if sensor_type in ['temperature', 'strain']:
                        # Create records for each measurement
                        for idx, row in df.iterrows():
                            if pd.notna(row[col]) and pd.notna(row['TimeStamp']):
                                record = {
                                    'timestamp': row['TimeStamp'],
                                    'day': row['TimeStamp'].strftime('%Y-%m-%d') if pd.notna(row['TimeStamp']) else None,
                                    'value': float(row[col]),
                                    'sensor_type': sensor_type,
                                    'platform': platform,
                                    'sensor_id': col,
                                    'file_source': os.path.basename(csv_file)
                                }
                                all_data.append(record)
                                
                                # Check for alerts
                                if sensor_type == 'temperature' and row[col] > TEMP_THRESHOLD:
                                    alerts.append({
                                        'type': 'temperature',
                                        'value': float(row[col]),
                                        'threshold': TEMP_THRESHOLD,
                                        'sensor': col,
                                        'platform': platform,
                                        'timestamp': row['TimeStamp'].strftime('%Y-%m-%d %H:%M:%S'),
                                        'file': os.path.basename(csv_file)
                                    })
                                elif sensor_type == 'strain' and row[col] > STRAIN_THRESHOLD:
                                    alerts.append({
                                        'type': 'strain',
                                        'value': float(row[col]),
                                        'threshold': STRAIN_THRESHOLD,
                                        'sensor': col,
                                        'platform': platform,
                                        'timestamp': row['TimeStamp'].strftime('%Y-%m-%d %H:%M:%S'),
                                        'file': os.path.basename(csv_file)
                                    })
                
            except Exception as e:
                alerts.append(f"Error processing {os.path.basename(csv_file)}: {str(e)}")
    
    return all_data, alerts

def create_visualizations(data):
    """Create Plotly visualizations for the data"""
    if not data:
        return None, None
    
    df = pd.DataFrame(data)
    
    # Temperature visualization
    temp_data = df[df['sensor_type'] == 'temperature']
    temp_fig = px.line(temp_data, x='day', y='value', color='platform', 
                       title='Temperature Trends by Platform',
                       labels={'value': 'Temperature (°C)'},
                       hover_data=['sensor_id'])
    temp_fig.add_hline(y=TEMP_THRESHOLD, line_dash="dash", line_color="red", 
                       annotation_text=f"Critical Threshold ({TEMP_THRESHOLD}°C)")
    
    # Strain visualization
    strain_data = df[df['sensor_type'] == 'strain']
    strain_fig = px.line(strain_data, x='day', y='value', color='platform',
                        title='Strain Trends by Platform',
                        labels={'value': 'Strain'},
                        hover_data=['sensor_id'])
    strain_fig.add_hline(y=STRAIN_THRESHOLD, line_dash="dash", line_color="red",
                        annotation_text=f"Critical Threshold ({STRAIN_THRESHOLD})")
    
    return temp_fig, strain_fig

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        filename = file.filename
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Process the uploaded file
        data, alerts = process_csv_files(filepath)
        
        if data is None:
            return jsonify({'error': 'Failed to process CSV files', 'alerts': alerts}), 400
        
        # Create visualizations
        temp_fig, strain_fig = create_visualizations(data)
        
        # Convert plots to JSON
        temp_json = json.dumps(temp_fig, cls=PlotlyJSONEncoder) if temp_fig else None
        strain_json = json.dumps(strain_fig, cls=PlotlyJSONEncoder) if strain_fig else None
        
        # Calculate summary statistics
        df = pd.DataFrame(data)
        summary = {
            'total_records': len(data),
            'platforms': df['platform'].unique().tolist(),
            'temperature_stats': {
                'min': df[df['sensor_type'] == 'temperature']['value'].min() if not df[df['sensor_type'] == 'temperature'].empty else None,
                'max': df[df['sensor_type'] == 'temperature']['value'].max() if not df[df['sensor_type'] == 'temperature'].empty else None,
                'avg': df[df['sensor_type'] == 'temperature']['value'].mean() if not df[df['sensor_type'] == 'temperature'].empty else None
            },
            'strain_stats': {
                'min': df[df['sensor_type'] == 'strain']['value'].min() if not df[df['sensor_type'] == 'strain'].empty else None,
                'max': df[df['sensor_type'] == 'strain']['value'].max() if not df[df['sensor_type'] == 'strain'].empty else None,
                'avg': df[df['sensor_type'] == 'strain']['value'].mean() if not df[df['sensor_type'] == 'strain'].empty else None
            }
        }
        
        # Clean up uploaded file
        os.remove(filepath)
        
        return jsonify({
            'success': True,
            'data': data[:1000],  # Limit data for frontend performance
            'alerts': alerts,
            'summary': summary,
            'plots': {
                'temperature': temp_json,
                'strain': strain_json
            }
        })
    
    return jsonify({'error': 'Invalid file type. Please upload a ZIP file.'}), 400

@app.route('/update_thresholds', methods=['POST'])
def update_thresholds():
    global TEMP_THRESHOLD, STRAIN_THRESHOLD
    
    data = request.get_json()
    if 'temp_threshold' in data:
        TEMP_THRESHOLD = float(data['temp_threshold'])
    if 'strain_threshold' in data:
        STRAIN_THRESHOLD = float(data['strain_threshold'])
    
    return jsonify({
        'success': True,
        'temp_threshold': TEMP_THRESHOLD,
        'strain_threshold': STRAIN_THRESHOLD
    })

@app.route('/get_thresholds', methods=['GET'])
def get_thresholds():
    return jsonify({
        'temp_threshold': TEMP_THRESHOLD,
        'strain_threshold': STRAIN_THRESHOLD
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)