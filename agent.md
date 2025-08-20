Agent Onboarding: Public Procurement Intelligence Platform
1. Project Overview
This project is an automated, AI-enhanced intelligence platform designed to forecast public procurement opportunities in the transportation sector across the United States. Its primary function is to systematically scrape, analyze, and structure data from a wide array of government sources to predict when agencies will release Requests for Proposals (RFPs) for Intelligent Transportation Systems (ITS) and related projects.

The platform moves beyond simple keyword monitoring by analyzing the entire procurement lifecycle, from early-stage planning documents and public meeting minutes to final contract awards. It uses a hybrid AI approach, combining specialized NLP models with Large Language Models (LLMs), to extract actionable intelligence and provide users with a strategic advantage in the public procurement marketplace.

2. Core Technologies & Architecture
The platform is built on a modern, containerized microservices architecture to ensure scalability, resilience, and maintainability.

Key Technologies:
Backend: Python

Containerization: Docker & Docker Compose

Database: PostgreSQL (Production) & SQLite (Development/Testing)

Web Scraping: Scrapy (for broad discovery) & Playwright (for targeted, dynamic extraction)

AI/NLP: Google Gemini API, spaCy, and various NLP libraries for a tiered analysis approach.

Dashboarding: Dash by Plotly

Orchestration: Cron-based scheduling within Docker

Architectural Approach:
The system is designed as a collection of independent services orchestrated by Docker Compose. This includes a database service, multiple scraper services, a data transformation service for NLP and cleaning, and a web application service for the user-facing dashboard. This microservices model allows for individual components to be updated and scaled independently.

3. The Data Acquisition Engine
The core of the platform is a sophisticated, two-stage data acquisition engine designed to handle the fragmented and complex nature of public sector websites.

Stage 1: Broad Discovery (Scrapy)
A Scrapy-based spider performs large-scale, high-speed crawling of government directories and agency lists. Its primary goal is not deep data extraction but the discovery and classification of procurement portal URLs, which are then stored in the database for the next stage.

Stage 2: Targeted, AI-Enhanced Extraction (Playwright)
For each URL identified in Stage 1, a specialized Playwright-based scraper is dispatched. This scraper controls a headless browser, allowing it to render JavaScript-heavy sites and simulate user interactions.

A key feature is the AI-driven link finder. Instead of relying on brittle CSS selectors, the scraper sends the full HTML of a page to the Gemini API with a prompt asking it to intelligently identify and return a list of URLs that point to relevant documents (e.g., planning reports, meeting minutes, RFPs). This makes the scraper highly resilient to website layout changes.

The scraper is also equipped to download and parse multiple document formats, including PDF, Word (.docx), PowerPoint (.pptx), and Excel (.xlsx).

4. The Data Transformation & AI Pipeline
Once raw data is acquired, it passes through a multi-stage transformation and analysis pipeline.

Multi-Modal Parsing
A robust parsing engine extracts text from various document formats. For image-based PDFs, an Optical Character Recognition (OCR) engine is used.

Hybrid NLP Strategy
The platform employs a tiered NLP strategy for efficiency and depth of analysis:

Tier 1 (Specialized Models): A custom-trained spaCy model performs fast, high-volume Named Entity Recognition (NER) to spot a predefined set of high-signal keywords (e.g., project names, budget figures, specific ITS technologies). This acts as an initial filter.

Tier 2 (Gemini LLM): Documents flagged as high-value by Tier 1 are sent to the Gemini API for deeper analysis. The LLM performs complex information extraction, relationship analysis (e.g., connecting a budget to a project), and executive summarization, returning the data in a structured JSON format.

Data Cleansing & Normalization
A final pipeline using the Pandas library cleans and standardizes the extracted data, handles missing values, and removes duplicates before ingestion into the database.

5. The Data Foundation
The platform's single source of truth is a PostgreSQL relational database.

OCDS-Aligned Schema
The database schema is modeled after the Open Contracting Data Standard (OCDS), a global standard for public procurement data. This ensures a comprehensive and interoperable data model. Key tables include agencies, documents, tenders, awards, and contracts.

Dual-Database Support
The codebase is architected to be database-agnostic. It can connect to either a PostgreSQL database for production (run via Docker) or a file-based SQLite database for local development, testing, and portability in environments like Google Colab. This is controlled by a DB_TYPE environment variable.

6. Setup and Execution
Production Environment (Docker)
The entire platform is orchestrated via a docker-compose.yml file.

Set Environment Variables: Configure the .env file with database credentials and the DB_TYPE=postgres.

Build and Run: Execute docker-compose up --build -d. This will build the necessary images and start all services (database, scrapers, dashboard).

Access Dashboard: The interactive dashboard will be available at http://localhost:8050.

Development/Simulation Environment (Google Colab)
For environments without Docker, the project can be run in a simulation mode using SQLite.

Setup: Run the colab_setup.sh script. This installs all necessary system dependencies (like Chrome/ChromeDriver for Playwright) and Python packages.

Execution: Run the run_colab_simulation.py script. This master script orchestrates the entire pipeline for a proof-of-concept run (e.g., for the Houston region):

It sets up the SQLite database.

It seeds the initial agency and relationship data.

It runs the targeted regional scrapers.

It verifies the data has been ingested correctly.

This dual-environment capability is a core feature, ensuring both robust production deployment and flexible, portable testing.
