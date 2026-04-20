⚡ Microgrid Panel Designer

Microgrid Panel Designer is a desktop application built to streamline the design of low-voltage electrical panels. It enables engineers to configure inputs, perform calculations, generate diagrams, and export deliverables — all from a single, unified interface.

📌 Overview

This application reduces manual effort in panel design by combining electrical calculations, diagram generation, and export functionality into one workflow.

It is designed for internal engineering use, ensuring:

Faster design iterations
Consistent outputs
Reduced drafting errors

The desktop interface is powered by PyWebView, combining a Python backend with a lightweight web-based UI.

🚀 Key Features
⚙️ Design & Calculation
Automatic current calculation
Busbar sizing based on input parameters
Standardized engineering logic

📊 Diagram Generation
Generate SLD (Single Line Diagram)
Generate GA (General Arrangement)

📦 Bill of Materials (BOM)
Auto-generated BOM based on design inputs
Structured output for procurement and documentation

📤 Export Capabilities
Export Design Report (PDF)
Export GA Drawing (PDF)
Export BOM (Excel)

🏗️ System Architecture

The application follows a modular layered architecture for scalability and maintainability:

1. Desktop Host (main.py)
Entry point of the application
Initializes the PyWebView window
Connects backend logic with frontend UI
2. API Bridge (api/bridge.py)
Acts as a communication layer
Connects frontend actions with backend processing
Handles user-triggered events
3. Core Adapters (core/)
Interface between API layer and domain logic
Standardizes data flow
Ensures modular integration
4. Domain Logic (src/)
Contains all engineering calculations
Handles:
Electrical sizing
Diagram generation logic
BOM computation
5. Frontend UI (ui/)
User interface layer
Built using web technologies (HTML/CSS/JS)
Provides input forms, output display, and export controls

🔄 Application Workflow
User enters design parameters through the UI
Data is passed to backend via API bridge
Core logic processes calculations and generates outputs
Results are displayed in the UI
User exports required deliverables

🧩 Project Structure Reference

For detailed internal structure, refer to:

architecture.md → Complete architecture breakdown
Module responsibilities
Data flow diagrams
Extension guidelines

⚡ Quick Start
1. Install Dependencies

Make sure Python is installed, then run:

pip install -r requirements.txt
2. Run the Application
python main.py

🧑‍💻 How to Use
Open the application
Enter required design inputs
Click Generate
Review generated:
SLD - Single Line Daigram
GA - General Arrangement 
BOM - Bill of Materail 
Export outputs as needed:
PDF reports
Excel BOM

🎨 UI & Rendering Notes
Supports Light and Dark themes
Exported files are automatically adjusted for light-mode readability
Designed for clarity and engineering usability



