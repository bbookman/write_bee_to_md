import requests
from config import BEE_API_KEY, BEE_API_ENDPOINT, TARGET_DIR
from datetime import datetime
from pathlib import Path

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
        
        # Check if we have transcriptions
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
    
    Args:
        text (str): Text to clean
    Returns:
        str: Cleaned text
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

def generate_markdown(conversation, conversation_detail):
    """
    Generate markdown content from a conversation and its details.
    """
    content = []
    
    # Add short summary as header
    content.append(f"# {conversation['short_summary']}\n")
    
    # Add conversation ID
    content.append(f"Conversation ID: {conversation['id']}\n")
    
    # Add address if available
    if conversation.get('primary_location') and conversation['primary_location'].get('address'):
        content.append(f"Location: {conversation['primary_location']['address']}\n")
    
    # Add conversation transcript right after location
    conversation_data = conversation_detail.get('conversation', {})
    transcriptions = conversation_data.get('transcriptions', [])
    if transcriptions and transcriptions[0].get('utterances'):
        content.append("\n## Transcript\n")
        for utterance in transcriptions[0]['utterances']:
            if utterance.get('text') and utterance.get('speaker'):
                content.append(f"**Speaker {utterance['speaker']}**: {utterance['text']}\n")
    
    # Add summary as last section
    if conversation.get('summary'):
        summary_text = clean_bee_text(conversation['summary'])
        content.append(f"\n## Summary\n{summary_text}\n")
    
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
    Only process 5 days maximum.
    """
    # Create target directory if it doesn't exist
    target_path = Path(TARGET_DIR)
    target_path.mkdir(parents=True, exist_ok=True)
    
    print(f"DEBUG: Writing files to {target_path}")
    
    page = 1
    daily_conversations = {}
    days_processed = 0
    max_days = 5  # Limit to 5 days
    
    while True and days_processed < max_days:
        response = get_bee_conversations(page)
        
        if not response.get('conversations'):
            break
            
        for conversation in response['conversations']:
            # Get detailed conversation data
            conversation_detail = get_conversation_detail(conversation['id'])
            
            # Convert start_time to date string
            start_date = datetime.fromisoformat(conversation['start_time'].replace('Z', '+00:00'))
            date_str = start_date.strftime('%Y-%m-%d')
            
            # Skip if we've already processed this date
            if date_str in daily_conversations:
                continue
                
            # Skip if file already exists
            output_file = target_path / f"{date_str}.md"
            if output_file.exists():
                print(f"Skipping existing file: {output_file}")
                continue
            
            # Add conversation and its details to daily collection
            if date_str not in daily_conversations:
                daily_conversations[date_str] = []
                days_processed += 1
                if days_processed >= max_days:
                    break
                    
            daily_conversations[date_str].append((conversation, conversation_detail))
        
        # Check if we've hit our day limit
        if days_processed >= max_days:
            print(f"Reached maximum of {max_days} days")
            break
            
        # Move to next page
        if page >= response.get('totalPages', 0):
            break
            
        page += 1
    
    # Write all conversations for each date to their respective files
    for date_str, conversations in daily_conversations.items():
        # Sort conversations by start_time
        conversations.sort(key=lambda x: x[0]['start_time'])
        
        # Generate markdown for all conversations
        markdown_content = []
        for conversation, detail in conversations:
            markdown_content.append(generate_markdown(conversation, detail))
        
        # Write markdown file to target directory
        output_file = target_path / f"{date_str}.md"
        print(f"Writing to: {output_file}")
        output_file.write_text("\n\n---\n\n".join(markdown_content), encoding='utf-8')
        
        print(f"Created markdown file: {output_file}")

if __name__ == "__main__":
    try:
        process_conversations()
    except Exception as e:
        print(f"Failed to process conversations: {e}")