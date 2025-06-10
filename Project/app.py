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
import re
from datetime import datetime

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

def is_temp_col(col_name):
    """Check if column is temperature using regex pattern like second code"""
    return bool(re.match(r'temp\d*[_\w/]*', col_name.lower()))

def is_strain_col(col_name):
    """Check if column is strain using regex pattern like second code"""
    return bool(re.match(r'strain\d*[_\w/]*', col_name.lower()))

def categorize_sensor_type(column_name):
    """Categorize sensor type from column name using improved logic"""
    if is_temp_col(column_name):
        return 'temperature'
    elif is_strain_col(column_name):
        return 'strain'
    return 'unknown'

def process_csv_files(zip_path):
    """Process all CSV files in the zip and return combined data with proper timestamp handling"""
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
                
                # Find timestamp column (case insensitive)
                timestamp_col = None
                for col in df.columns:
                    if 'timestamp' in col.lower():
                        timestamp_col = col
                        break
                
                if not timestamp_col:
                    alerts.append(f"No timestamp column found in {os.path.basename(csv_file)}")
                    continue
                
                # Convert timestamp to datetime
                df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors='coerce')
                
                # Find temperature and strain columns using improved regex
                temp_cols = [col for col in df.columns if is_temp_col(col)]
                strain_cols = [col for col in df.columns if is_strain_col(col)]
                
                # Process temperature columns
                if temp_cols:
                    temp_melted = df[[timestamp_col] + temp_cols].melt(
                        id_vars=timestamp_col, 
                        var_name='sensor_id', 
                        value_name='value'
                    )
                    temp_melted['sensor_type'] = 'temperature'
                    temp_melted['platform'] = temp_melted['sensor_id'].apply(extract_platform_from_column)
                    temp_melted['file_source'] = os.path.basename(csv_file)
                    temp_melted['timestamp'] = temp_melted[timestamp_col]
                    temp_melted['date'] = temp_melted[timestamp_col].dt.date
                    
                    # Remove rows with NaN values
                    temp_melted = temp_melted.dropna(subset=['value', 'timestamp'])
                    
                    # Add to all_data
                    for _, row in temp_melted.iterrows():
                        record = {
                            'timestamp': row['timestamp'],
                            'date': row['date'].isoformat() if row['date'] else None,
                            'value': float(row['value']),
                            'sensor_type': row['sensor_type'],
                            'platform': row['platform'],
                            'sensor_id': row['sensor_id'],
                            'file_source': row['file_source']
                        }
                        all_data.append(record)
                        
                        # Check for temperature alerts
                        if row['value'] > TEMP_THRESHOLD:
                            alerts.append({
                                'type': 'temperature',
                                'value': float(row['value']),
                                'threshold': TEMP_THRESHOLD,
                                'sensor': row['sensor_id'],
                                'platform': row['platform'],
                                'timestamp': row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                                'file': row['file_source']
                            })
                
                # Process strain columns
                if strain_cols:
                    strain_melted = df[[timestamp_col] + strain_cols].melt(
                        id_vars=timestamp_col, 
                        var_name='sensor_id', 
                        value_name='value'
                    )
                    strain_melted['sensor_type'] = 'strain'
                    strain_melted['platform'] = strain_melted['sensor_id'].apply(extract_platform_from_column)
                    strain_melted['file_source'] = os.path.basename(csv_file)
                    strain_melted['timestamp'] = strain_melted[timestamp_col]
                    strain_melted['date'] = strain_melted[timestamp_col].dt.date
                    
                    # Remove rows with NaN values
                    strain_melted = strain_melted.dropna(subset=['value', 'timestamp'])
                    
                    # Add to all_data
                    for _, row in strain_melted.iterrows():
                        record = {
                            'timestamp': row['timestamp'],
                            'date': row['date'].isoformat() if row['date'] else None,
                            'value': float(row['value']),
                            'sensor_type': row['sensor_type'],
                            'platform': row['platform'],
                            'sensor_id': row['sensor_id'],
                            'file_source': row['file_source']
                        }
                        all_data.append(record)
                        
                        # Check for strain alerts
                        if row['value'] > STRAIN_THRESHOLD:
                            alerts.append({
                                'type': 'strain',
                                'value': float(row['value']),
                                'threshold': STRAIN_THRESHOLD,
                                'sensor': row['sensor_id'],
                                'platform': row['platform'],
                                'timestamp': row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                                'file': row['file_source']
                            })
                
            except Exception as e:
                alerts.append(f"Error processing {os.path.basename(csv_file)}: {str(e)}")
    
    return all_data, alerts

def create_visualizations(data):
    """Create Plotly visualizations for the data with proper date handling"""
    if not data:
        return None, None
    
    df = pd.DataFrame(data)
    
    # Convert date strings back to datetime for plotting
    df['date'] = pd.to_datetime(df['date'])
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Create daily averages like in the second code
    df['date_only'] = df['timestamp'].dt.date
    
    # Temperature visualization
    temp_data = df[df['sensor_type'] == 'temperature'].copy()
    if not temp_data.empty:
        # Group by date and sensor to get daily averages
        temp_daily = temp_data.groupby(['date_only', 'sensor_id', 'platform'])['value'].mean().reset_index()
        temp_daily['date_only'] = pd.to_datetime(temp_daily['date_only'])
        
        temp_fig = px.line(temp_daily, 
                          x='date_only', 
                          y='value', 
                          color='sensor_id',
                          line_dash='platform',
                          title='Daily Average Temperature Trends by Sensor',
                          labels={'value': 'Temperature (°C)', 'date_only': 'Date'},
                          hover_data=['platform'])
        
        temp_fig.add_hline(y=TEMP_THRESHOLD, line_dash="dash", line_color="red", 
                          annotation_text=f"Critical Threshold ({TEMP_THRESHOLD}°C)")
        
        # Update x-axis formatting
        temp_fig.update_xaxes(tickformat='%Y-%m-%d', tickangle=45)
        temp_fig.update_layout(xaxis_title="Date", yaxis_title="Temperature (°C)")
    else:
        temp_fig = None
    
    # Strain visualization
    strain_data = df[df['sensor_type'] == 'strain'].copy()
    if not strain_data.empty:
        # Group by date and sensor to get daily averages
        strain_daily = strain_data.groupby(['date_only', 'sensor_id', 'platform'])['value'].mean().reset_index()
        strain_daily['date_only'] = pd.to_datetime(strain_daily['date_only'])
        
        strain_fig = px.line(strain_daily, 
                            x='date_only', 
                            y='value', 
                            color='sensor_id',
                            line_dash='platform',
                            title='Daily Average Strain Trends by Sensor',
                            labels={'value': 'Strain', 'date_only': 'Date'},
                            hover_data=['platform'])
        
        strain_fig.add_hline(y=STRAIN_THRESHOLD, line_dash="dash", line_color="red",
                            annotation_text=f"Critical Threshold ({STRAIN_THRESHOLD})")
        
        # Update x-axis formatting
        strain_fig.update_xaxes(tickformat='%Y-%m-%d', tickangle=45)
        strain_fig.update_layout(xaxis_title="Date", yaxis_title="Strain")
    else:
        strain_fig = None
    
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
        temp_data = df[df['sensor_type'] == 'temperature']
        strain_data = df[df['sensor_type'] == 'strain']
        
        summary = {
            'total_records': len(data),
            'platforms': df['platform'].unique().tolist(),
            'files_processed': len(df['file_source'].unique()),
            'date_range': {
                'start': df['date'].min() if not df.empty else None,
                'end': df['date'].max() if not df.empty else None
            },
            'temperature_stats': {
                'min': temp_data['value'].min() if not temp_data.empty else None,
                'max': temp_data['value'].max() if not temp_data.empty else None,
                'avg': temp_data['value'].mean() if not temp_data.empty else None,
                'sensors': temp_data['sensor_id'].unique().tolist() if not temp_data.empty else []
            },
            'strain_stats': {
                'min': strain_data['value'].min() if not strain_data.empty else None,
                'max': strain_data['value'].max() if not strain_data.empty else None,
                'avg': strain_data['value'].mean() if not strain_data.empty else None,
                'sensors': strain_data['sensor_id'].unique().tolist() if not strain_data.empty else []
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
