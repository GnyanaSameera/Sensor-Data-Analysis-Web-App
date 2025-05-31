
# Sensor Data Analysis Web App

This is a simple and powerful web application built to process and visualize temperature and strain data from structural platforms (WIN and NC). 

# What It Does

*Easy File Upload*: Just drag and drop a ZIP file full of CSVs – the app handles the rest.
*Smart Data Processing*: Automatically extracts sensor readings and organizes the data.
*Interactive Visuals*: Generates real-time Plotly charts for temperature and strain values.
*Alerts*: Notifies you when sensor readings cross critical thresholds (like 50°C or 5000 strain).
*Data Summary*: View average, max, and min stats for quick insights.

# Folder Structure


├── templates/
│   └── index.html         # Web interface
├── uploads/               # Stores uploaded ZIP files temporarily
├── app.py                 # Main Flask backend with python
├── requirements.txt       # Python dependencies that you have to download
└── README.md              # You're reading this!


# Getting Started

**Install the required Python libraries:**

   pip install -r requirements.txt

**Start the Flask server:**

   python app.py (run this in your terminal)

**Visit the app in your browser:**
   Open [http://localhost:5000]

# How to Use It

1.Upload a `.zip` file that contains your CSV sensor data.(You can also drag and drop!)
2.Click "Upload & Process" to start the analysis.
3.View real-time graphs of all temperature and strain sensors.
4.See instant alerts when readings go beyond safe limits.
5.Customize thresholds if you want to modify safety margins.
6.You can also view the summary of the sensors.

# CSV File Format

I will attach the zip file below
(you can use your own zip file but it should have some columns like:
'TimeStamp', 'temp1_268503/0001', 'strain1_slanted_268503/0001_NC', 
'temp2_268504/0001', 'strain2_vertical_268504/0001_NC', 
'temp3_268505/0001', 'strain3_horizontal_268505/0001_NC', 
'temp_alone_268518/0001_NC', 'temp1_268515/0001_WIN', 
'strain1_horizontal_268515/0001_WIN', 'tem2_268516/002_WIN', 
'Strain2_Vertical_268516/002', 'temp3_268517/0001_WIN', 
'strain3_slanted_268517/0001?_WIN', 'temp_alone268518/0002_WIN' ...)


# Default Thresholds

*Temperature*: Anything over `50°C` triggers a warning.
*Strain*: Readings above `5000` are flagged as critical.
(You can adjust the thresholds too!)

# Example Results

Here’s what your dashboard might tell you after uploading a ZIP file:

*Date Range*: May 31, 2025 – 9:04 AM to 10:43 AM
*Temperature Range*: 30.4°C to 58.4°C (Average: 46.6°C)
*Strain Range*: 1790 to 6581 (Average: 3204)

# Tech Stack

*Backend*: Python Flask + pandas for processing CSVs
*Frontend*: HTML5 + CSS3 + JavaScript
*Visualization*: Plotly.js for smooth, interactive visualizations


# Behind the Scenes

This project has main features like:

*Scalability*: Handles large data and multiple files
*User Experience*: Clean, responsive interface with drag-and-drop support
*Real-Time Feedback*: Instant alerts and charts after upload
*Flexibility*: Easy to customize thresholds or add more platforms

*Screenshots*: I have also uploaded a folder #images# where you can look at the screenshots of the working web app
