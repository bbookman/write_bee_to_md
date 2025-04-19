import requests
from config import BEE_API_KEY, BEE_API_ENDPOINT, TARGET_DIR
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
    Handles various header formats and non-header formats.
    """
    # Standardize section name handling for all variations of Key Takeaways
    variations = [section_name]
    if section_name.lower() == "key takeaways":
        variations = ["Key Takeaways", "Key Take Aways", "Key Take aways", "Key Takeaways"]
    
    # Try all variations with different header levels
    for variation in variations:
        for header_level in range(3, 0, -1):
            pattern = f"{'#' * header_level}\\s*{variation}\\s*\n(.*?)(?=\\s*#{1,3}\\s*[A-Za-z]|$)"
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
    
    # Try without any markdown headers
    for variation in variations:
        pattern = f"{variation}[:\\s]*\n(.*?)(?=\\s*[A-Za-z][A-Za-z\\s]*:\\s*$|\\n\\n|$)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Try bullet-point style lists for Key Takeaways
    if section_name.lower() == "key takeaways":
        pattern = r"(?:^|\n)(?:\*|\-|\d+\.)\s+(.+(?:\n(?:\*|\-|\d+\.)\s+.+)*)"
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            return match.group(1).strip()
    
    return ""

def generate_markdown(conversations_for_day):
    """Generate markdown content for all conversations in a day."""
    if not conversations_for_day:
        return ""
        
    content = []
    date_str = datetime.fromisoformat(conversations_for_day[0][0]['start_time'].replace('Z', '+00:00')).strftime('%Y-%m-%d')
    
    # Function to safely extract content, handling None
    def safe_extract(text, section_name):
        extracted = extract_section(text, section_name)
        return extracted if extracted else None
    
    # Extract main summary and clean it
    main_summary = conversations_for_day[0][0].get('summary')
    if main_summary:
        # Remove any existing section headers to avoid duplicates
        main_summary = re.sub(r'(?:#{1,3}\s*)?(Atmosphere|Key\s*Take\s*[aA]ways|Action\s*Items)\s*\n[\s\S]*?(?=\n\s*(?:#{1,3}\s*)?[A-Z]|$)', '', main_summary, flags=re.MULTILINE | re.IGNORECASE)
        main_summary = re.sub(r'^\s*[-*•]\s+.*$', '', main_summary, flags=re.MULTILINE)
        main_summary = re.sub(r'\n{3,}', '\n\n', main_summary)
        content.append(f"# {main_summary.strip()}")
        content.append("\n")
    
    # Extract and add Atmosphere section
    atmosphere = safe_extract(conversations_for_day[0][0]['summary'], 'Atmosphere')
    if atmosphere:
        content.append("## Atmosphere")
        content.append(atmosphere + "\n")
    
    # Extract and add Key Takeaways section
    key_takeaways = safe_extract(conversations_for_day[0][0]['summary'], 'Key Takeaways')
    if key_takeaways and key_takeaways.strip():
        content.append("## Key Takeaways")
        content.append(key_takeaways.strip())
        content.append("\n")
    
    # Extract and add Action Items section
    action_items = safe_extract(conversations_for_day[0][0]['summary'], 'Action Items')
    if action_items:
        content.append("### Action Items")
        content.append(action_items + "\n")
    
    # Process each conversation
    for conversation, conversation_detail in conversations_for_day:
        content.append("\nConversation ID: " + str(conversation['id']))
        if conversation.get('primary_location') and conversation['primary_location'].get('address'):
            content.append("Location: " + conversation['primary_location']['address'] + "\n")
        
        # Add ### header to short_summary
        short_summary = conversation.get('short_summary')
        if short_summary:
            content.append(f"### {clean_bee_text(short_summary)}")
        
        conversation_data = conversation_detail.get('conversation', {})
        transcriptions = conversation_data.get('transcriptions', [])
        if transcriptions and transcriptions[0].get('utterances'):
            content.append("### Transcript")
            for utterance in transcriptions[0]['utterances']:
                if utterance.get('text') and utterance.get('speaker'):
                    content.append("Speaker " + str(utterance['speaker']) + ": " + utterance['text'])
    
    return "\n".join(content)

def clean_markdown_content(markdown_content):
    """
    Process markdown content to remove duplicate sections and empty headings.
    Normalizes section headers to handle variations in spelling.
    
    Args:
        markdown_content (str): The original markdown content
        
    Returns:
        str: Cleaned markdown content with duplicates and empty headings removed
    """
    # First pass: Handle inline section labels that aren't proper markdown headers
    markdown_content = re.sub(r'(?<!\n#)Key\s*Take\s*[aA]ways:?\s*', '', markdown_content)
    markdown_content = re.sub(r'(?<!\n#)Atmosphere:?\s*', '', markdown_content)
    markdown_content = re.sub(r'(?<!\n#)Action\s*Items:?\s*', '', markdown_content)
    
    lines = markdown_content.split('\n')
    cleaned_lines = []
    seen_headers = set()
    i = 0
    
    while i < len(lines):
        current_line = lines[i]
        
        # Check if this is a heading
        header_match = re.match(r'^(#{1,3})\s+(.*?)$', current_line)
        if header_match:
            level, header_text = header_match.groups()
            
            # Normalize header text for comparison (standardize Key Takeaways variants)
            normalized_header = header_text.lower().replace(" ", "")
            if "keytake" in normalized_header and "ways" in normalized_header:
                # Standardize to "Key Takeaways"
                header_text = "Key Takeaways"
                current_line = f"{level} {header_text}"
                normalized_header = "keytakeaways"
            elif "atmosphere" in normalized_header:
                header_text = "Atmosphere"
                current_line = f"{level} {header_text}"
                normalized_header = "atmosphere"
            elif "actionitems" in normalized_header:
                header_text = "Action Items"
                current_line = f"{level} {header_text}"
                normalized_header = "actionitems"
            
            header_key = level + " " + normalized_header
            
            # Skip this header if we've seen it before
            if header_key in seen_headers:
                i += 1
                # Skip any content under this duplicate header until next header or end
                while i < len(lines) and not re.match(r'^#{1,3}\s+', lines[i]):
                    i += 1
                continue
                
            # Look ahead to see if this heading has content
            has_content = False
            j = i + 1
            
            while j < len(lines) and not re.match(r'^#{1,3}\s+', lines[j]):
                # Check if there's actual content (not just empty lines)
                if lines[j].strip() and not lines[j].startswith('Conversation ID:'):
                    has_content = True
                    break
                j += 1
            
            # Only add this heading if it has content following it
            if has_content:
                cleaned_lines.append(current_line)
                seen_headers.add(header_key)
            # Special case for main heading (level 1) - always keep it
            elif level == '#':
                cleaned_lines.append(current_line)
                seen_headers.add(header_key)
        else:
            # Check for inline section headers like "Key Take Aways:" and remove them
            if not re.match(r'^(Key\s*Take\s*[aA]ways|Atmosphere|Action\s*Items):?\s*$', current_line.strip()):
                # Not a heading or inline section header, so add the line
                cleaned_lines.append(current_line)
        
        i += 1
    
    return '\n'.join(cleaned_lines)

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
    Process all conversations and create markdown files for missing dates.
    Skip today's conversations and only process dates that don't have files.
    """
    target_path = Path(TARGET_DIR)
    target_path.mkdir(parents=True, exist_ok=True)
    
    print(f"DEBUG: Writing files to {target_path}")
    
    # Get all existing date files
    existing_dates = set()
    for file_path in target_path.glob('*.md'):
        date_str = file_path.stem
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            existing_dates.add(date_str)
    
    # Get conversations to find date range
    response = get_bee_conversations(1)
    if not response.get('conversations'):
        print("DEBUG: No conversations found")
        return
    
    # Calculate missing dates (all dates from earliest in API to yesterday)
    yesterday = (datetime.now() - timedelta(days=1)).date()
    missing_dates = set()
    
    # Track which dates we've seen in the API responses
    seen_dates = set()
    daily_conversations = {}
    page = 1
    
    # Process pages until we've found all missing dates or reached the end
    while True:
        response = get_bee_conversations(page)
        
        if not response.get('conversations'):
            print(f"DEBUG: No conversations found on page {page}")
            break
        
        print(f"DEBUG: Processing page {page} of {response.get('totalPages', 1)}")
        
        # First pass - just collect all date strings to determine range
        for conversation in response['conversations']:
            start_date = datetime.fromisoformat(conversation['start_time'].replace('Z', '+00:00'))
            date_str = start_date.strftime('%Y-%m-%d')
            seen_dates.add(date_str)
            
            # Skip if it's today or we already have a file
            if start_date.date() >= datetime.now().date() or date_str in existing_dates:
                continue
                
            # Get conversation details and add to daily collection
            conversation_detail = get_conversation_detail(conversation['id'])
            
            if date_str not in daily_conversations:
                daily_conversations[date_str] = []
            
            daily_conversations[date_str].append((conversation, conversation_detail))
            print(f"DEBUG: Added conversation {conversation['id']} for {date_str}")
        
        # If we've processed all pages, stop
        if page >= response.get('totalPages', 1):
            print(f"DEBUG: Reached the last page ({page})")
            break
            
        page += 1
    
    # Process collected conversations
    for date_str, conversations in daily_conversations.items():
        print(f"DEBUG: Writing {len(conversations)} conversations for {date_str}")
        conversations.sort(key=lambda x: x[0]['start_time'])
        markdown_content = generate_markdown(conversations)
        markdown_content = clean_markdown_content(markdown_content)
        
        output_file = target_path / f"{date_str}.md"
        output_file.write_text(markdown_content, encoding='utf-8')
        print(f"Created markdown file: {output_file}")
    
    # Report any dates that were never seen in API responses
    for date_str in missing_dates - seen_dates:
        print(f"DEBUG: No data found for {date_str}")

if __name__ == "__main__":
    try:
        print(f"\nDEBUG: Starting conversation processing at {datetime.now()}")
        process_conversations()
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        print(f"Failed to process conversations: {e}")