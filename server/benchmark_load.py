"""
benchmark_load.py

A standard concurrent benchmark utility to test local server throughput.
Measures requests per second (QPS) and response latency of the `/submit` endpoint.
"""

import time
import json
import urllib.request
import urllib.error
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

# Target Server Configuration
TARGET_IP = "192.168.137.1"
TARGET_PORT = 8765
SUBMIT_URL = f"http://{TARGET_IP}:{TARGET_PORT}/submit"

# Test parameters
TOTAL_REQUESTS = 100
CONCURRENT_WORKERS = 10

# Sample pools for randomizing the payload parameters
FIRST_NAMES = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Jamie", "Riley", "Cameron", "Skyler", "Rowan",
               "Serafim", "Lena", "Max", "Nina", "Tom", "Emma", "John", "Sophia", "Lucas", "Olivia"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Garcia", "Rodriguez", "Wilson",
              "Doe", "Benchmark", "Kovalev", "Schmidt", "Mueller", "Dupont", "Martin", "Lee", "Kim", "Singh"]
EMOJIS = ["⚡", "🦊", "🦋", "🐺", "🦅", "🐯", "🙂", "🐱", "🐶", "🦁", "🐰", "🐼", "🐨", "🐹", "🦄", "🐙", "🐠", "🍏", "🍕", "🚗"]
LANGUAGES_POOL = ["English", "German", "Spanish", "French", "Chinese", "Italian", "Japanese", "Russian"]

STORY_TEMPLATES = [
    "I love {interest_1}, {interest_2}, and {interest_3}. Looking for {wants}.",
    "Into {interest_1} and {interest_2}. Hope to find {wants}.",
    "Mainly interested in {interest_1}. Also enjoy {interest_2} and {interest_3}. Let's connect if you are {wants}."
]

INTERESTS = [
    "coding", "testing performance", "benchmarking local web services", "hiking in the Alps", "reading novels",
    "listening to jazz", "visiting art galleries", "cooking delicious food", "playing video games", "traveling",
    "gardening", "swimming in the lake", "yoga", "mindfulness", "exploring new cities", "nature photography",
    "watching sci-fi movies", "brewing coffee", "playing acoustic guitar", "learning languages"
]

WANTS_POOL = [
    "someone curious and active", "a long-term relationship", "a partner for outdoor adventures",
    "someone to share quiet evenings with", "a creative soul", "a career-oriented individual",
    "someone who loves deep conversations", "casual fun and good vibes", "someone spontaneous",
    "a partner for travel and exploration"
]

def generate_random_payload(request_id: int) -> dict:
    """Generates a randomized payload mimicking the client structure with realistic data."""
    first_name = f"{random.choice(FIRST_NAMES)}_{request_id}"
    last_name = random.choice(LAST_NAMES)
    age = random.randint(18, 70)
    avatar_index = random.randint(1, 10)
    avatar_emoji = random.choice(EMOJIS)
    
    my_gender = random.choice(["Male", "Female", "Non-binary"])
    target_gender = random.choice(["Male", "Female", "Non-binary", "any"])
    
    min_age = random.randint(18, 45)
    max_age = random.randint(min_age, 85)
    
    # Select 1 to 3 random languages
    languages = random.sample(LANGUAGES_POOL, k=random.randint(1, 3))
    
    # Generate a random story
    template = random.choice(STORY_TEMPLATES)
    interests = random.sample(INTERESTS, k=3)
    wants = random.choice(WANTS_POOL)
    story = template.format(interest_1=interests[0], interest_2=interests[1], interest_3=interests[2], wants=wants)
    
    return {
        "profile": {
            "first_name": first_name,
            "last_name": last_name,
            "age": age,
            "avatar_index": avatar_index,
            "avatar_emoji": avatar_emoji
        },
        "demographics": {
            "my_gender": my_gender,
            "target_gender": target_gender,
            "age_range": {"min": min_age, "max": max_age},
            "languages": languages
        },
        "matching_data": {
            "story": story
        }
    }

def send_single_request(request_id: int) -> float:
    """Sends a single POST request and returns the latency in seconds."""
    payload = generate_random_payload(request_id)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        SUBMIT_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    start_time = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            response.read()
            latency = time.perf_counter() - start_time
            return latency
    except urllib.error.URLError as e:
        latency = time.perf_counter() - start_time
        print(f"[Request {request_id}] Failed: {e}")
        return -1.0

def run_benchmark():
    print("==================================================")
    print(f"[*] Starting benchmark targeting {SUBMIT_URL}")
    print(f"Total Requests: {TOTAL_REQUESTS} | Concurrency: {CONCURRENT_WORKERS}")
    print("==================================================")
    
    # Clear the database before starting the benchmark to ensure a clean state
    reset_url = f"http://{TARGET_IP}:{TARGET_PORT}/admin/reset"
    try:
        req = urllib.request.Request(reset_url, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            response.read()
            print("[*] Database successfully cleared before starting benchmark.")
    except Exception as e:
        print(f"[*] Warning: Could not clear database: {e}")
    print("==================================================")
    
    latencies = []
    failed_requests = 0
    
    start_test = time.perf_counter()
    
    # Send requests concurrently using a thread pool
    with ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as executor:
        futures = {executor.submit(send_single_request, i): i for i in range(TOTAL_REQUESTS)}
        
        for future in as_completed(futures):
            result = future.result()
            if result < 0:
                failed_requests += 1
            else:
                latencies.append(result)
                
    end_test = time.perf_counter()
    total_time = end_test - start_test
    successful_requests = len(latencies)
    
    # Calculate statistics
    if successful_requests > 0:
        avg_latency = sum(latencies) / successful_requests * 1000  # in ms
        qps = successful_requests / total_time
    else:
        avg_latency = 0.0
        qps = 0.0
        
    print("\n================ Results ================")
    print(f"Total time taken:      {total_time:.2f} seconds")
    print(f"Successful requests:   {successful_requests}")
    print(f"Failed requests:       {failed_requests}")
    print(f"Throughput (QPS):      {qps:.2f} requests/sec")
    print(f"Avg Response Latency:  {avg_latency:.2f} ms")
    print("=========================================")

if __name__ == "__main__":
    run_benchmark()
