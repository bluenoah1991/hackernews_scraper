import os
import requests
from bs4 import BeautifulSoup
import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import argparse
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


# Configure session with retry strategy
session = requests.Session()
retry_strategy = Retry(
    total=3,  # Retry up to 3 times
    backoff_factor=1,  # Wait 1 second between retries
    # Retry on these HTTP status codes
    status_forcelist=[429, 500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount('http://', adapter)
session.mount('https://', adapter)


def scrape_hackernews(pages=3):
    """
    Scrape titles and links from the first N pages of Hacker News
    """
    base_url = "https://news.ycombinator.com"
    all_items = []

    # Define HTTP proxy
    proxies = {
        "http": os.getenv("HTTP_PROXY"),
        "https": os.getenv("HTTPS_PROXY")
    }

    for page in range(1, pages + 1):
        url = f"{base_url}/news?p={page}" if page > 1 else base_url
        response = session.get(url, proxies=proxies)
        time.sleep(1)  # Wait 1 second between requests
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all title lines
        titlelines = soup.find_all('span', class_='titleline')

        for titleline in titlelines:
            a_tag = titleline.find('a')
            if a_tag:
                title = a_tag.text
                href = a_tag['href']

                # Handle relative links
                if href.startswith('item?'):
                    href = f"{base_url}/{href}"

                all_items.append({
                    'title': title,
                    'url': href
                })

    return all_items


def filter_by_topics(items, topics):
    """
    Filter projects by multiple topics in a single API call and translate titles to Chinese.
    """
    # Initialize LLM
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    )

    # Prepare prompt template for multiple topics and translation
    prompt = ChatPromptTemplate.from_template(
        """Please analyze whether this Hacker News project is related to any of the following topics:
        
        Topics:
        {topics_list}
        
        For each topic, answer only "yes" or "no", separated by commas in the order of topics listed above.
        No explanation needed.
        
        Additionally, translate the project title into Chinese and append it directly after the yes/no responses, separated by commas.
        
        Project title: {title}
        Project URL: {url}"""
    )

    # Create processing chain
    chain = prompt | llm | StrOutputParser()

    # Initialize result dictionary
    results = {topic_name: [] for topic_name in topics.keys()}

    # For testing purposes, limit the number of items to process
    # items = items[:3]  # Limit to first 3 items for testing

    for item in items:
        # Dynamically generate topics list for the prompt
        topics_list = "\n".join(
            [f"{i + 1}. {desc}" for i, desc in enumerate(topics.values())])

        print(
            f"Sending request to DeepSeek with title: {item['title']} and URL: {item['url']}")
        response = chain.invoke({
            'topics_list': topics_list,
            'title': item['title'],
            'url': item['url']
        })

        # Parse the response (expecting "yes,no,yes,translated_title" format)
        *responses, translated_title = [r.strip() for r in response.split(',')]

        # Add item to appropriate result lists
        for i, (topic_name, _) in enumerate(topics.items()):
            if i < len(responses) and 'yes' in responses[i].lower():
                results[topic_name].append({
                    'title': item['title'],
                    'url': item['url'],
                    'translated_title': translated_title
                })

    return results


def summarize_article(url):
    """
    Fetch and summarize the article content from the given URL using DeepSeek.
    """
    # Initialize LLM for summarization
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    )

    # Prepare prompt template for summarization
    prompt = ChatPromptTemplate.from_template(
        """Please summarize the main content of the article at the following URL:
        {url}
        Provide a concise summary in one sentence, in Chinese."""
    )

    # Create processing chain
    chain = prompt | llm | StrOutputParser()

    print(f"Summarizing article at URL: {url}")
    try:
        summary = chain.invoke({'url': url})
        return summary.strip()
    except Exception as e:
        print(f"Error summarizing article at {url}: {e}")
        return "Summary unavailable"


def add_summaries_to_data(data):
    """Add article summaries to the data."""
    for item in data:
        item['summary'] = summarize_article(item['url'])
    return data


def save_to_json(data, filename):
    """Save data to JSON file in the 'out' directory."""
    output_path = os.path.join('out', filename)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Control script behavior.")
    parser.add_argument("--browser-only", action="store_true",
                        help="Scrape 50 pages and filter only for browser topics.")
    args = parser.parse_args()

    # Adjust parameters based on the argument
    pages = 50 if args.browser_only else 3
    topics = {
        "browsers": "Browsers, including browser engines, plugin development, performance optimization, and cross-browser compatibility"
    } if args.browser_only else {
        "artificial_intelligence": "Artificial intelligence, including machine learning, deep learning, natural language processing, computer vision, reinforcement learning, and AI applications",
        "ecommerce": "E-commerce, including online shopping platforms, payment gateways, logistics solutions, e-commerce marketing tools, and multi-language/multi-currency support",
        "computer_science": "Computer science, including algorithms, data structures, programming languages, software engineering, artificial intelligence, computer systems, and theoretical computer science",
        "browsers": "Browsers, including browser engines, plugin development, performance optimization, and cross-browser compatibility",
        "astronomy": "Astronomy, including astrophysics, astronomical research, telescope technology, and space exploration",
        "entrepreneurship": "Entrepreneurship, including startups, business models, venture capital, product development, and market strategies"
    }

    # 1. Scrape Hacker News data
    print("Scraping Hacker News data...")
    hackernews_items = scrape_hackernews(pages=pages)
    print(f"Found {len(hackernews_items)} projects")

    # 2. Filter for all topics in a single call
    print("Filtering projects for all topics...")
    filtered_results = filter_by_topics(
        hackernews_items, topics)

    # 3. Add summaries for each topic
    summarized_results = {}
    for topic_name, filtered_items in filtered_results.items():
        print(
            f"Adding summaries for {len(filtered_items)} {topic_name} projects")
        summarized_results[topic_name] = add_summaries_to_data(filtered_items)

    # Save results for each topic
    for topic_name, summarized_items in summarized_results.items():
        output_file = f"hackernews_{topic_name}.json"
        save_to_json(summarized_items, output_file)
        print(f"Results with summaries saved to {output_file}")


if __name__ == "__main__":
    main()
