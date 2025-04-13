import requests
from config import BEE_API_KEY, BEE_API_ENDPOINT, TARGET_DIR
from datetime import datetime
from pathlib import Path
import re

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
    """
    Generate markdown content for all conversations in a day.
    """
    if not conversations_for_day:
        return ""
        
    content = []
    date_str = datetime.fromisoformat(conversations_for_day[0][0]['start_time'].replace('Z', '+00:00')).strftime('%Y-%m-%d')
    
    content.append(f"# {date_str}")
    
    if conversations_for_day[0][0].get('short_summary'):
        content.append("## " + clean_bee_text(conversations_for_day[0][0]['short_summary']))
        content.append("\n")
        
        if conversations_for_day[0][0].get('summary'):
            atmosphere = extract_section(conversations_for_day[0][0]['summary'], 'Atmosphere')
            if atmosphere:
                content.append("### Atmosphere")
                content.append(atmosphere + "\n")
                
            takeaways = extract_section(conversations_for_day[0][0]['summary'], 'Key Takeaways')
            if takeaways:
                content.append("### Key Takeaways")
                content.append(takeaways + "\n")  # Add single newline after key takeaways content
    
    for conversation, conversation_detail in conversations_for_day:
        content.append("Conversation ID: " + str(conversation['id']))
        if conversation.get('primary_location') and conversation['primary_location'].get('address'):
            content.append("Location: " + conversation['primary_location']['address'] + "\n")
        
        conversation_data = conversation_detail.get('conversation', {})
        transcriptions = conversation_data.get('transcriptions', [])
        if transcriptions and transcriptions[0].get('utterances'):
            content.append("### Transcript")
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
    Only process 1 day maximum.
    """
    target_path = Path(TARGET_DIR)
    target_path.mkdir(parents=True, exist_ok=True)
    
    print(f"DEBUG: Writing files to {target_path}")
    
    page = 1
    daily_conversations = {}
    days_processed = 0
    max_days = 1
    
    while True and days_processed < max_days:
        response = get_bee_conversations(page)
        
        if not response.get('conversations'):
            print("DEBUG: No conversations found in response")
            break
            
        print(f"DEBUG: Found {len(response['conversations'])} conversations")
        
        for conversation in response['conversations']:
            conversation_detail = get_conversation_detail(conversation['id'])
            
            start_date = datetime.fromisoformat(conversation['start_time'].replace('Z', '+00:00'))
            date_str = start_date.strftime('%Y-%m-%d')
            print(f"DEBUG: Processing conversation for date {date_str}")
            
            if date_str not in daily_conversations:
                daily_conversations[date_str] = []
                days_processed += 1
                print(f"DEBUG: Starting new day {date_str}")
                if days_processed > max_days:
                    break
            
            daily_conversations[date_str].append((conversation, conversation_detail))
            print(f"DEBUG: Added conversation {conversation['id']} to {date_str}")
            
        if days_processed >= max_days:
            break
        
        page += 1
    
    # Process collected conversations after the loop
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
    try:
        process_conversations()
    except Exception as e:
        print(f"Failed to process conversations: {e}")