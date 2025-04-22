# HackerNews Scraper

This project is a simple scraper for HackerNews. It fetches and processes data from the HackerNews website.

## Prerequisites

Make sure you have Python 3 installed on your system. You will also need the following Python packages:

- `requests`
- `beautifulsoup4`
- `langchain-openai`
- `langchain-core`

## Installation

To install the required dependencies, run:

```bash
pip3 install requests beautifulsoup4 langchain-openai langchain-core
```

## Usage

To start a local HTTP server and serve the project, run:

```bash
python3 -m http.server 8000
```

Then, open your browser and navigate to `http://localhost:8000`.

## Files

- `hackernews_scraper.py`: The main script for scraping HackerNews.
- `index.html`: A simple HTML file for displaying the scraped data.
- `README.md`: This documentation file.

## License

This project is licensed under the MIT License.