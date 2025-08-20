# ITS Procurement Business Intelligence Platform

## 1. Executive Summary

The ITS Procurement Business Intelligence Platform is a complete, end-to-end system designed to forecast future procurement opportunities in the public sector Intelligent Transportation Systems (ITS) market. It moves beyond simple keyword monitoring by leveraging a multi-source data pipeline, a hybrid AI for information extraction, and a hierarchical machine learning model to predict the likelihood of an agency releasing a Request for Proposal (RFP).

The platform automates the entire intelligence lifecycle:

1.  **Data Acquisition:** It systematically scrapes and aggregates planning documents, meeting minutes, news articles, and federal funding data from hundreds of state and local agencies.
2.  **Information Extraction:** It uses a tiered AI approach to analyze unstructured text, identifying key signals like project discussions, budget allocations, and timelines.
3.  **Predictive Forecasting:** It trains an XGBoost model on historical data to learn the complex patterns that precede a procurement event, understanding the intricate relationships between parent and constituent government agencies.
4.  **Interactive Analysis:** It presents this intelligence through a dynamic, map-based dashboard that includes a conversational AI, allowing analysts to explore opportunities and generate data-driven reports.

This tool is designed to provide a significant competitive advantage by enabling business development teams to proactively identify and engage with high-potential clients long before a formal solicitation is ever released.

## 2. Core Features

*   **Automated Multi-Source Scraping:** Dedicated agents for scraping agency websites, harvesting news (via NewsAPI), and monitoring federal funding portals.
*   **Hybrid NLP Engine:** Uses **spaCy** for high-speed, cost-effective triage of all documents and a swappable, locally-hosted **Large Language Model (via Ollama)** for deep reasoning and synthesis tasks.
*   **Hierarchical Prediction Model:** The machine learning model understands that signals from a small municipality can "roll up" to influence the forecast for its parent MPO or State DOT.
*   **Geographic Intelligence Dashboard:** An interactive map of the United States with clickable state polygons and agency-specific points, allowing for intuitive drill-down from national to local views.
*   **Conversational UI:** A chat interface powered by the local LLM allows users to ask natural-language questions about their current data selection (e.g., *"Which members are putting out RFPs soon?"*).
*   **On-Demand AI Reporting:** A two-stage system to generate and preview AI-written reports in Markdown, which can then be downloaded as finalized PDFs.
*   **Human-in-the-Loop (HITL) Quality Assurance:** An integrated "Quality Engineering" workflow where an AI agent flags uncertain data for human review, continuously improving the quality of the training data over time.
*   **Comprehensive Backtesting Framework:** A full simulation engine to validate the model's predictive accuracy against years of historical data, providing a statistical basis for trust.

## 3. System Architecture

The platform is fully containerized using Docker and orchestrated with a single `docker-compose.yml` file. This ensures a consistent, reproducible environment. The architecture consists of four main services:

*   **`db` (PostgreSQL):** The relational database that serves as the central data store for all scraped information, NLP entities, and predictions.
*   **`ollama`:** The self-hosted service that runs the chosen Large Language Model (e.g., Llama 3) and exposes it via an API for the other services to use.
*   **`app` (Dash/Gunicorn):** The user-facing web application. This service runs the interactive dashboard, the conversational UI, and the reporting engine.
*   **`scheduler` (Cron):** A lightweight, background service whose sole purpose is to run the automated data pipelines (`main_pipeline.py`, `agent_tasks.py`, etc.) on a predefined schedule.

### 3.1. Dual-Database Support (Production vs. Simulation)

To support both robust production deployments and lightweight local testing (e.g., in Google Colab), the application can run on either PostgreSQL or SQLite. This is controlled by the `DB_TYPE` environment variable in the `.env` file.

*   **`DB_TYPE=postgres` (Default/Production):** The application will use the `psycopg2` driver and connect to the PostgreSQL service defined in `docker-compose.yml`. This is the recommended mode for production.
*   **`DB_TYPE=sqlite` (Simulation/Development):** The application will use the built-in `sqlite3` driver and create a local database file (`local_database.db`). This mode is ideal for local testing and environments without Docker, like Colab.

All database interaction scripts have been refactored to be database-agnostic.

## 4. Deployment and Operational Guide

### Phase 1: Initial Setup (One-Time)

1.  **Prerequisites:** For production, ensure you have Docker and Docker Compose installed. For local simulation, ensure you have Python 3.10+ installed.
2.  **Populate Initial Data:** Place your complete `publicsector.csv` file inside the `data/` directory.
3.  **Configure Environment:** Open the `.env` file and set your desired `DB_TYPE`.
    *   If using `postgres`, set the `DB_USER`, `DB_PASSWORD`, and `DB_NAME`.
    *   Set your `NEWS_API_KEY` and `SAM_API_KEY`.
4.  **Build & Start Services (Production - Docker):**
    ```bash
    docker-compose up --build -d
    ```
5.  **Install Dependencies (Simulation - Local/Colab):**
    ```bash
    pip install -r requirements.txt
    # Or, if in Colab, run the provided setup script:
    !bash colab_setup.sh
    ```
6.  **Initialize Database:**
    *   **Production (Docker):**
        ```bash
        docker-compose exec scheduler python -m app.database_setup --setup
        ```
    *   **Simulation (Local/Colab):**
        ```bash
        python -m app.database_setup --setup
        ```
6.  **Download LLM Model:** Pull the model specified in your `.env` file into the Ollama service.
    ```bash
    docker-compose exec ollama ollama pull your_model_name
    ```
7.  **Initialize Database:** Run the one-time setup script to create all database tables and seed the initial agency data.
    ```bash
    docker-compose exec scheduler python -m app.database_setup --setup
    ```

### Phase 2: Historical Data Acquisition (The "Big Scrape")

This is a **manual, one-time, labor-intensive process** that is essential for training the model.

1.  **Scrape Historical Documents:** Modify and run the `scraper.py` script to collect planning documents and meeting minutes going back to your chosen start date (recommended: 2009). **Crucially, this requires enhancing the scraper to parse the actual `publication_date` of each document.**
2.  **Scrape Historical Solicitations:** Write and execute a dedicated scraper to gather all relevant ITS RFPs from procurement portals from 2009 to the present. This data must be inserted into the `historical_solicitations` table.

### Phase 3: Model Training & Validation

Once you have a rich historical dataset, you can train and validate the model.

1.  **Train the Model:** Run the training script from inside the `scheduler` container.
    ```bash
    docker-compose exec scheduler python train.py
    ```
    This creates the `training_data.csv` and, most importantly, the `app/xgb_model.json` file that the live system uses.
2.  **Analyze the Model:** Run the model analyzer to understand which data sources are the most predictive.
    ```bash
    docker-compose exec scheduler python model_analyzer.py
    ```
    Review the generated `feature_importance_shap.png` image to gain strategic insights.

### Phase 4: Live Operation

The platform is now ready for continuous, automated operation.

1.  **Automated Pipeline:** The `cron` jobs will run automatically, scraping new data and generating fresh predictions daily.
2.  **Access the Dashboard:** Navigate to `http://<your_server_ip>:8050`.
3.  **Intelligence Workflow:** Use the map, table, filters, and conversational UI to explore opportunities.
4.  **Data Curation:** Periodically use the "Quality Engineering Review Queue" to validate AI-extracted data, which will be used in future model retraining cycles.

## 5. Project File Structure and Module Descriptions

This section details the purpose of each file in the final project structure.

```
/its_forecasting_platform/
|-- docker-compose.yml        # Orchestrates all services (DB, LLM, App, Scheduler).
|-- Dockerfile                # Builds the Python application image for the App and Scheduler.
|-- requirements.txt          # A complete list of all Python package dependencies.
|-- crontab                   # Defines the schedules for all automated background jobs.
|-- .env                      # Stores secrets and environment-specific configurations.
|-- train.py                  # Standalone script to perform the historical model training process.
|-- model_analyzer.py         # Standalone script to analyze the trained model and generate feature importance charts.
|-- README.md                 # This documentation file.
|-- .gitignore                # Specifies files and directories for Git to ignore.
|-- data/
|   |-- publicsector.csv      # The initial seed data containing the list of agencies to monitor.
|-- app/
    |-- __init__.py           # Makes the 'app' directory a Python package.
    |-- app.py                # The main Dash application; contains the layout and all callbacks for the dashboard UI.
    |-- database.py           # Contains the core function for establishing a connection to the PostgreSQL database.
    |-- database_setup.py     # A utility script to create the database schema, seed initial data, and generate mock data for testing.
    |-- scraper.py            # Contains all logic for scraping agency websites for documents and harvesting news via APIs.
    |-- nlp_processor.py      # The Tiered NLP Engine: uses spaCy for triage and calls the LLM for deep analysis.
    |-- prediction_model.py   # Handles feature engineering from database data and generates live predictions using the trained model.
    |-- conversation_agent.py # The backend logic for the conversational UI, including intent routing.
    |-- report_generator.py   # The AI-powered engine for synthesizing data and generating Markdown/PDF reports.
    |-- agent_tasks.py        # The "Guardian" agent for nightly data integrity checks and feedback loop creation.
    |-- quality_auditor_agent.py # The "Auditor" agent that flags data for the Human-in-the-Loop review queue.
    |-- backtester.py         # The historical simulation engine for model validation.
    |-- main_pipeline.py      # The master script for the daily scheduled job, orchestrating the scraper, NLP, and prediction modules.
```

## 6. Known Limitations and Future Outlook

No system is perfect. This platform is incredibly powerful, but its operators must be aware of its limitations to use it effectively and plan for future improvements.

### 6.1. Critical Limitations

*   **Scraper Fragility (High Risk):** The scrapers are the most brittle part of the system. Websites change layouts, which will break the scrapers. **Action:** Implement a robust monitoring and alerting system (e.g., Healthchecks.io) that the `main_pipeline.py` pings on successful completion. If a ping is missed, an alert must be sent to the development team.
*   **Historical Data Quality:** The accuracy of the backtest and the initial trained model depends entirely on the quality and accuracy of the historical data you can scrape, especially the `publication_date` of documents. Inconsistent or missing dates are a major challenge.
*   **"Cold Start" Problem:** The model's predictions will be less reliable for a new agency for which there is little historical data. The model will improve as it observes more data over time for that agency.
*   **LLM Hallucination/Consistency:** The local LLM, while powerful, can sometimes provide inconsistent or creatively formatted responses, especially for the open-ended report generation. The prompts are engineered to minimize this, but it can still occur.

### 6.2. Future Enhancements Roadmap

*   **Relationship Discovery UI:** Build a dedicated interface in the dashboard for the "Relationship Manager," where an a a can see the AI's suggested agency relationships and approve or reject them with a single click.
*   **Advanced Scrapers:** Develop more sophisticated scrapers that can handle JavaScript-heavy sites more robustly and use heuristics or NLP to find the `publication_date` of documents more reliably.
*   **Sentiment Analysis:** Enhance the `nlp_processor.py` module to perform sentiment analysis on meeting minutes and news articles to gauge public and political support or opposition to projects.
*   **Asynchronous Report Generation:** For very large "roll-up" reports, convert the report generation from a synchronous request into an asynchronous background job using a task queue like Celery or Redis, which would notify the user when their report is ready to download.
*   **GPU Enablement:** If LLM processing speed becomes a bottleneck, deploy the stack on a GPU-enabled server and use the corresponding Ollama image to dramatically accelerate all AI-driven tasks.
