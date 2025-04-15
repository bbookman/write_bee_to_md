import requests
from config import BEE_API_KEY, BEE_API_ENDPOINT, TARGET_DIR, PAGES_TO_GET
from datetime import datetime, timedelta
from pathlib import Path
import re
import time

def get_bee_conversations(page=1):
    """
    Send a request to the Bee API to get conversations with paging.
    """
    headers = {
        "accept": "application/json",
        "x-api-key": BEE_API_KEY
    }
    
    endpoint = f"{BEE_API_ENDPOINT}/me/conversations"
    params = {"page": page}
    
    print(f"\nDEBUG: Making request to {endpoint}")
    print(f"DEBUG: Headers: {headers}")
    print(f"DEBUG: Params: {params}")
    
    try:
        response = requests.get(endpoint, headers=headers, params=params)
        print(f"DEBUG: Response status: {response.status_code}")
        print(f"DEBUG: Response URL: {response.url}")
        response.raise_for_status()
        data = response.json()
        print(f"DEBUG: Got {len(data.get('conversations', []))} conversations")
        return data
    except requests.RequestException as e:
        print(f"ERROR: API request failed: {e}")
        print(f"DEBUG: Response content: {getattr(e.response, 'text', 'No response content')}")
        raise

def get_conversation_detail(conversation_id):
    """
    Get detailed conversation data including text and speaker information.
    """
    headers = {
        "accept": "application/json",
        "x-api-key": BEE_API_KEY
    }
    
    endpoint = f"{BEE_API_ENDPOINT}/me/conversations/{conversation_id}"
    
    print(f"\nDEBUG: Getting conversation detail from {endpoint}")
    
    try:
        response = requests.get(endpoint, headers=headers)
        print(f"DEBUG: Detail response status: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        
        transcriptions = data.get('conversation', {}).get('transcriptions', [])
        if transcriptions:
            utterances = transcriptions[0].get('utterances', [])
            print(f"DEBUG: Got transcript with {len(utterances)} utterances")
        else:
            print("DEBUG: No transcriptions found")
            
        return data
    except requests.RequestException as e:
        print(f"ERROR: Failed to get conversation detail: {e}")
        print(f"DEBUG: Response content: {getattr(e.response, 'text', 'No response content')}")
        raise

def clean_bee_text(text):
    """
    Clean text from Bee API responses by removing redundant headers and formatting.
    """
    replacements = [
        ('## Summary\n', ''),
        ('##Summary\n', ''),
        ('Summary:\n', ''),
        ('## Bruce\'s Memory Summary\n', ''),
        ('**Summary:**', ''),
        ('**Summary:** ', '')
    ]
    
    for old, new in replacements:
        text = text.replace(old, new)
    
    return text.strip()

def clean_summary(text):
    """Strip all markdown formatting and headers from summary text."""
    # First remove all ### Summary or # Summary headers
    text = re.sub(r'^#{1,3}\s*Summary\n', '', text, flags=re.MULTILINE)
    
    # Then remove any remaining markdown headers
    text = re.sub(r'^#{1,3}\s*', '', text, flags=re.MULTILINE)
    
    # Remove any Summary: text variations
    text = re.sub(r'Summary:?\s*\n?', '', text)
    
    # Clean up any extra whitespace
    return text.strip()

def extract_section(text, section_name):
    """
    Extract a section from the summary text based on markdown headers.
    Handles both ### and # format, as well as non-markdown format.
    """
    pattern = f"### {section_name}\n(.*?)(?=###|$)"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        pattern = f"# {section_name}\n(.*?)(?=#|$)"
        match = re.search(pattern, text, re.DOTALL)
    if not match:
        pattern = f"{section_name}\n(.*?)(?=\n\n|$)"
        match = re.search(pattern, text, re.DOTALL)
    
    return match.group(1).strip() if match else ""

def generate_markdown(conversations_for_day):
    """Generate markdown content for all conversations in a day."""
    if not conversations_for_day:
        return ""
        
    content = []
    date_str = datetime.fromisoformat(conversations_for_day[0][0]['start_time'].replace('Z', '+00:00')).strftime('%Y-%m-%d')
    
    content.append(f"# {date_str}")
    
    # Main summary - strip all markdown and add only ##
    if conversations_for_day[0][0].get('summary'):
        summary_text = conversations_for_day[0][0]['summary']
        # Remove existing Summary header
        summary_text = re.sub(r'^#{1,3}\s*Summary\n', '', summary_text, flags=re.MULTILINE)
        summary_text = re.sub(r'^#{1,3}\s*', '', summary_text, flags=re.MULTILINE)
        content.append(f"## {summary_text.strip()}")
        content.append("\n")
        
        # Extract and add Atmosphere section
        atmosphere = extract_section(conversations_for_day[0][0]['summary'], 'Atmosphere')
        if atmosphere:
            content.append("### Atmosphere")
            content.append(atmosphere + "\n")
        
        # Extract and add Key Takeaways section
        takeaways = extract_section(conversations_for_day[0][0]['summary'], 'Key Takeaways')
        if takeaways:
            content.append("### Key Takeaways")
            content.append(takeaways)
    
    # Process each conversation
    for conversation, conversation_detail in conversations_for_day:
        content.append("\nConversation ID: " + str(conversation['id']))
        if conversation.get('primary_location') and conversation['primary_location'].get('address'):
            content.append("Location: " + conversation['primary_location']['address'] + "\n")
            
        if conversation.get('short_summary'):
            content.append(f"{clean_summary(conversation['short_summary'])}\n")
        
        conversation_data = conversation_detail.get('conversation', {})
        transcriptions = conversation_data.get('transcriptions', [])
        if transcriptions and transcriptions[0].get('utterances'):
            content.append("### Transcript\n")
            for utterance in transcriptions[0]['utterances']:
                if utterance.get('text') and utterance.get('speaker'):
                    content.append("Speaker " + str(utterance['speaker']) + ": " + utterance['text'])
    
    return "\n".join(content)

def file_exists(target_path: Path, date_str: str) -> bool:
    """
    Check if a markdown file already exists for the given date.
    
    Args:
        target_path (Path): Directory path where files are stored
        date_str (str): Date string in YYYY-MM-DD format
    Returns:
        bool: True if file exists, False otherwise
    """
    file_path = target_path / f"{date_str}.md"
    return file_path.exists()

def process_conversations():
    """
    Process all conversations and create markdown files in TARGET_DIR.
    Skip writing files for today's conversations.
    Only process the number of pages specified in PAGES_TO_GET.
    """
    target_path = Path(TARGET_DIR)
    target_path.mkdir(parents=True, exist_ok=True)
    
    print(f"DEBUG: Writing files to {target_path}")
    
    page = 1
    daily_conversations = {}
    today = datetime.now().date()
    
    while page <= PAGES_TO_GET:  # Only get specified number of pages
        response = get_bee_conversations(page)
        print(f"DEBUG: Processing page {page} of {PAGES_TO_GET}")
        
        if not response.get('conversations'):
            print("DEBUG: No conversations found in response")
            break
        
        print(f"DEBUG: Found {len(response['conversations'])} conversations")
        
        for conversation in response['conversations']:
            conversation_detail = get_conversation_detail(conversation['id'])
            
            start_date = datetime.fromisoformat(conversation['start_time'].replace('Z', '+00:00'))
            conversation_date = start_date.date()
            
            # Skip if conversation is from today
            if conversation_date >= today:
                print(f"DEBUG: Skipping today's conversation from {conversation_date}")
                continue
                
            date_str = start_date.strftime('%Y-%m-%d')
            print(f"DEBUG: Processing conversation for date {date_str}")
            
            if date_str not in daily_conversations:
                daily_conversations[date_str] = []
            
            daily_conversations[date_str].append((conversation, conversation_detail))
            print(f"DEBUG: Added conversation {conversation['id']} to {date_str}")
            
        # Stop if we've reached the total pages or our PAGES_TO_GET limit
        if page >= response.get('totalPages', 0) or page >= PAGES_TO_GET:
            print(f"DEBUG: Reached page limit ({page}/{PAGES_TO_GET})")
            break
            
        page += 1
    
    # Process collected conversations
    for date_str, conversations in daily_conversations.items():
        print(f"DEBUG: Writing {len(conversations)} conversations for {date_str}")
        conversations.sort(key=lambda x: x[0]['start_time'])
        markdown_content = generate_markdown(conversations)
        
        if not markdown_content:
            print(f"DEBUG: No markdown content generated for {date_str}")
            continue
            
        output_file = target_path / f"{date_str}.md"
        print(f"Writing to: {output_file}")
        output_file.write_text(markdown_content, encoding='utf-8')
        print(f"Created markdown file: {output_file}")

if __name__ == "__main__":
    INTERVAL = 6 * 60 * 60  # 6 hours in seconds
    
    while True:
        try:
            print(f"\nDEBUG: Starting conversation processing at {datetime.now()}")
            process_conversations()
            
            next_run = datetime.now() + timedelta(seconds=INTERVAL)
            print(f"DEBUG: Next run scheduled for {next_run}")
            
            time.sleep(INTERVAL)
            
        except KeyboardInterrupt:
            print("\nShutting down gracefully...")
            break
        except Exception as e:
            print(f"Failed to process conversations: {e}")
            # Wait 5 minutes before retrying on error
            time.sleep(300)