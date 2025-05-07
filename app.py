import requests
from config import BEE_API_ENDPOINT, TARGET_DIR, FACTS_FILE_PATH
from datetime import datetime, timedelta
from pathlib import Path
import re
import getpass

# Ensure target directory exists
Path(TARGET_DIR).mkdir(parents=True, exist_ok=True)
# Ensure parent directory of facts file exists
Path(FACTS_FILE_PATH).parent.mkdir(parents=True, exist_ok=True)

def get_api_key(max_attempts=3):
    """
    Get the Bee API key from config.py if present, or prompt the user.
    
    Args:
        max_attempts: Maximum number of attempts to get a valid key from user
        
    Returns:
        str: The Bee API key
    """
    # First try to get the key from config.py
    try:
        from config import BEE_API_KEY
        if BEE_API_KEY and BEE_API_KEY != "YOUR_BEE_API_KEY":
            print("Using API key from config.py")
            return BEE_API_KEY
    except (ImportError, AttributeError):
        # If import fails or the attribute doesn't exist, continue to prompt
        pass
    
    print("\n=== Bee API Access ===")
    print("Please enter your Bee API key.")
    print("The key will not be displayed as you type for security reasons.")
    
    attempts = 0
    api_key = getpass.getpass("Bee API Key: ")
    
    while not api_key:
        attempts += 1
        if attempts >= max_attempts:
            raise ValueError("Maximum attempts reached. Exiting.")
        
        print("API key cannot be empty.")
        api_key = getpass.getpass("Bee API Key: ")
    
    return api_key

# Global variable for API key
BEE_API_KEY = None

class ApiClient:
    def __init__(self, api_key):
        self.api_key = api_key
        
    def get_conversations(self, page=1):
        """
        Send a request to the Bee API to get conversations with paging.
        """
        headers = {
            "accept": "application/json",
            "x-api-key": self.api_key
        }
        
        endpoint = f"{BEE_API_ENDPOINT}/me/conversations"
        params = {"page": page}
        ''''''
        print(f"\nDEBUG: Making request to {endpoint}")
        print(f"DEBUG: Headers: {headers}")
        print(f"DEBUG: Params: {params}")
        ''''''

        try:
            response = requests.get(endpoint, headers=headers, params=params)
            ''''''
            print(f"DEBUG: Response status: {response.status_code}")
            print(f"DEBUG: Response URL: {response.url}")
            ''''''
            response.raise_for_status()
            data = response.json()
            ''''''
            print(f"DEBUG: Got {len(data.get('conversations', []))} conversations")
            ''''''
        except requests.RequestException as e:
            print(f"ERROR: API request failed: {e}")
            print(f"DEBUG: Response content: {getattr(e.response, 'text', 'No response content')}")
            raise

def get_bee_conversations(page=1):
    global BEE_API_KEY
    
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
    
    Args:
        conversation_id: The ID of the specific conversation to fetch
        
    Returns:
        dict: Conversation details or an empty structure if request fails
    """
    global BEE_API_KEY
    
    headers = {
        "accept": "application/json",
        "x-api-key": BEE_API_KEY
    }
    
    endpoint = f"{BEE_API_ENDPOINT}/me/conversations/{conversation_id}"
    
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
        # Return empty dict instead of None to avoid NoneType errors
        return {"conversation": {}}
    except ValueError as e:
        print(f"ERROR: Failed to parse JSON response: {e}")
        return {"conversation": {}}
    except Exception as e:
        print(f"ERROR: Unexpected error in get_conversation_detail: {e}")
        return {"conversation": {}}

def clean_bee_text(text):
    """
    Clean text from Bee API responses by removing redundant headers and formatting.
    Also removes bullet points at the beginning of the text.
    """
    replacements = [
        ('## Summary\n', ''),
        ('##Summary\n', ''),
        ('Summary:\n', ''),
        ('## Bruce\'s Memory Summary\n', ''),
        ('**Summary:**', ''),
        ('Summary:', ''),
    ]
    
    for old, new in replacements:
        text = text.replace(old, new)
    
    # Remove bullet points at the beginning of the text
    text = re.sub(r'^[\s\-\*•]+', '', text.strip())
    
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
    Extract a section from the summary text based on markdown headers or specific text patterns.
    Handles various header formats and non-header formats.
    
    Args:
        text (str): The text to search for sections
        section_name (str): The name of the section to extract
        
    Returns:
        str: The extracted section content or empty string if not found
    """
    # First check for None or empty text
    if text is None or not text.strip():
        return ""
        
    # Special case for Atmosphere with more flexible matching
    if section_name.lower() == "atmosphere":
        # Try to find any mention of atmosphere with content following it
        patterns = [
            r"(?:^|\n)(?:#{1,3}\s*)?Atmosphere:?\s*(.*?)(?=\n\s*(?:#{1,3}\s*)?[A-Z]|$)",
            r"Atmosphere:?\s*(.*?)(?=\n\s*[A-Z]|$)",
            r"(?:^|\n)The atmosphere\s*(?:was|is)?\s*(.*?)(?=\n\s*(?:#{1,3}\s*)?[A-Z]|$)",
            r"(?:^|\n)(?:The\s*)?mood\s*(?:was|is)?\s*(.*?)(?=\n\s*(?:#{1,3}\s*)?[A-Z]|$)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match and match.group(1):  # Add check for None
                return match.group(1).strip()
    
    # Special case for Key Takeaways with various spellings
    if section_name.lower() == "key takeaways":
        # Try broader patterns for key takeaways
        variations = ["Key Takeaways", "Key Take Aways", "Key Take aways", "Takeaways", "Take Aways", "Key Points"]
        
        for variation in variations:
            # Try with different formats
            patterns = [
                f"(?:^|\n)(?:#{1,3}\s*)?{variation}:?\s*(.*?)(?=\n\s*(?:#{1,3}\s*)?[A-Z]|$)",
                f"{variation}:?\s*(.*?)(?=\n\s*[A-Z]|$)",
                f"(?:^|\n)(?:The\s*)?{variation}\s*(?:were|are|included)?\s*(.*?)(?=\n\s*(?:#{1,3}\s*)?[A-Z]|$)"
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                if match and match.group(1):  # Add check for None
                    return match.group(1).strip()
                    
        # If we get here, check for bullet points that might be takeaways
        bullet_list = re.findall(r'(?:^|\n)\s*[-*•]\s+(.*?)(?=\n\s*[-*•]|\n\s*\n|$)', text, re.DOTALL)
        if bullet_list:
            return '\n'.join([f"- {item.strip()}" for item in bullet_list])
    
    # Check for the most direct pattern first: "SectionName: content"
    pattern = f"{section_name}:\\s*(.*?)(?=\\s*[A-Za-z]+:|$)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match and match.group(1):  # Add check for None
        return match.group(1).strip()
    
    # Try with markdown headers at different levels
    for header_level in range(3, 0, -1):
        pattern = f"{'#' * header_level}\\s*{section_name}\\s*\n(.*?)(?=\\s*#{1,3}\\s*[A-Za-z]|$)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match and match.group(1):  # Add check for None
            return match.group(1).strip()
    
    # Special case for Action Items
    if section_name.lower() == "action items":
        # Look for "Action Items:" followed by a bullet point list
        pattern = r"Action\s*Items:?\s*((?:\s*[-*•]\s+.*\n?)+)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match and match.group(1):  # Add check for None
            return match.group(1).strip()
    
    return ""

def generate_markdown(conversations_for_day):
    """Generate markdown content for all conversations in a day."""
    if not conversations_for_day:
        return ""
        
    content = []
    # Convert UTC time to local time before getting the date string
    utc_time = datetime.fromisoformat(conversations_for_day[0][0]['start_time'].replace('Z', '+00:00'))
    local_time = utc_time.astimezone() # Convert to local timezone
    date_str = local_time.strftime('%Y-%m-%d')
    
    # Add the "Daily Summary" heading at the beginning
    content.append("# Daily Summary")
    content.append("")
    
    # Extract sections and add the summary content
    if conversations_for_day[0][0].get('summary'):
        summary_text = conversations_for_day[0][0]['summary']
        
        # Clean up the summary text (removing sections we'll add separately)
        summary_text = re.sub(r'(?:#{1,3}\s*)?Atmosphere\s*\n[\s\S]*?(?=\n\s*(?:#{1,3}\s*)?[A-Z]|$)', '', summary_text, flags=re.MULTILINE)
        summary_text = re.sub(r'(?:#{1,3}\s*)?Key\s*Take?\s*[aA]ways\s*\n[\s\S]*?(?=\n\s*(?:#{1,3}\s*)?[A-Z]|$)', '', summary_text, flags=re.MULTILINE | re.IGNORECASE)
        summary_text = re.sub(r'(?:#{1,3}\s*)?Action\s*Items\s*\n[\s\S]*?(?=\n\s*(?:#{1,3}\s*)?[A-Z]|$)', '', summary_text, flags=re.MULTILINE)
        
        # Remove any "Summary:" prefix that might be in the text
        summary_text = re.sub(r'^Summary:\s*', '', summary_text, flags=re.MULTILINE)
        
        # Clean up remaining headers
        summary_text = re.sub(r'^#{1,3}\s*Summary\s*\n', '', summary_text, flags=re.MULTILINE)
        summary_text = re.sub(r'^#{1,3}\s*', '', summary_text, flags=re.MULTILINE)
        
        # Remove any bullet point lists in the main summary
        summary_text = re.sub(r'^\s*[-*•]\s+.*$', '', summary_text, flags=re.MULTILINE)
        summary_text = re.sub(r'\n{3,}', '\n\n', summary_text)
        
        # Add the cleaned summary content directly (without "Summary:" prefix)
        content.append(summary_text.strip())
        content.append("")
        
        # Extract atmosphere section
        atmosphere = extract_section(conversations_for_day[0][0]['summary'], 'Atmosphere')
        if atmosphere:
            content.append("## Atmosphere")
            # Clean up any leading bullet points
            if atmosphere.startswith('-') or atmosphere.startswith('*') or atmosphere.startswith('•'):
                atmosphere = re.sub(r'^[\s\-\*•]+', '', atmosphere.strip())
            content.append(atmosphere)
            content.append("")
        
        # Extract key takeaways section
        key_takeaways = extract_section(conversations_for_day[0][0]['summary'], 'Key Takeaways')
        if key_takeaways and key_takeaways.strip():
            content.append("## Key Takeaways")
            
            # Process key takeaways to ensure proper bullet point formatting
            formatted_lines = []
            lines = key_takeaways.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Remove any asterisks or bullet points at the beginning and clean up
                if line.startswith('-') or line.startswith('*') or line.startswith('•'):
                    # Already has bullet point, just standardize it
                    line = re.sub(r'^[\s\-\*•]+\s*', '- ', line)
                else:
                    # Add bullet point if missing
                    line = f"- {line}"
                
                formatted_lines.append(line)
            
            # Add the formatted key takeaways
            content.append('\n'.join(formatted_lines))
            content.append("")
        
        # Extract action items section
        action_items = extract_section(conversations_for_day[0][0]['summary'], 'Action Items')
        if action_items:
            content.append("## Action Items")
            
            # Process action items to ensure proper bullet point formatting
            formatted_lines = []
            lines = action_items.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Remove any asterisks or bullet points at the beginning and clean up
                if line.startswith('-') or line.startswith('*') or line.startswith('•'):
                    # Already has bullet point, just standardize it
                    line = re.sub(r'^[\s\-\*•]+\s*', '- ', line)
                else:
                    # Add bullet point if missing
                    line = f"- {line}"
                
                formatted_lines.append(line)
            
            # Add the formatted action items
            content.append('\n'.join(formatted_lines))
            content.append("")
    
    # Process ALL conversations for this day
    content.append("## Conversations")
    content.append("")
    
    for i, (conversation, conversation_detail) in enumerate(conversations_for_day):
            
        content.append(f"Conversation {i+1} (ID: {conversation['id']})")
        
        if conversation.get('primary_location') and conversation['primary_location'].get('address'):
            content.append(f"Location: {conversation['primary_location']['address']}\n")
        
        # Add short_summary if available
        if conversation.get('short_summary'):
            content.append(f"{clean_bee_text(conversation['short_summary'])}\n")
        
        # Add transcript
        conversation_data = conversation_detail.get('conversation', {})
        transcriptions = conversation_data.get('transcriptions', [])
        if transcriptions and transcriptions[0].get('utterances'):
            content.append("#### Transcript")
            for utterance in transcriptions[0]['utterances']:
                if utterance.get('text') and utterance.get('speaker'):
                    content.append(f"Speaker {utterance['speaker']}: {utterance['text']}")
    
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
    
    # Fix headers with bullet points (e.g., "## - Bullet point")
    markdown_content = re.sub(r'(^|\n)(#{1,3})\s+[-*•]\s+', r'\1\2 ', markdown_content)
    
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
            
            # Remove any bullet points at the start of headers
            if header_text.startswith('-') or header_text.startswith('*') or header_text.startswith('•'):
                header_text = re.sub(r'^[\s\-\*•]+', '', header_text)
                current_line = f"{level} {header_text}"
            
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
    Skip dates that already have files.
    Organize files in month folders (e.g., "04-April").
    """
    target_path = Path(TARGET_DIR)
    target_path.mkdir(parents=True, exist_ok=True)
    
    print(f"DEBUG: Writing files to {target_path}")
    
    # Get all existing date files across all month directories
    existing_dates = set()
    month_dirs = list(target_path.glob("*-*"))
    
    for month_dir in month_dirs:
        if not month_dir.is_dir():
            continue
            
        for file_path in month_dir.glob('*.md'):
            date_str = file_path.stem
            if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
                existing_dates.add(date_str)
    
    print(f"DEBUG: Found {len(existing_dates)} existing date files")
    
    # Track which dates we've seen in the API responses
    seen_dates = set()
    daily_conversations = {}
    page = 1
    all_needed_files_written = False
    
    # Process pages until we've reached the end
    while True:
        response = get_bee_conversations(page)
        
        if not response.get('conversations'):
            print(f"DEBUG: No conversations found on page {page}")
            break
        
        print(f"DEBUG: Processing page {page} of {response.get('totalPages', 1)}")
        
        # Process conversations on this page
        conversations_processed = 0
        
        # First pass - just collect all date strings to determine range
        for conversation in response['conversations']:
            # Convert UTC time to local time to get the correct date
            utc_time = datetime.fromisoformat(conversation['start_time'].replace('Z', '+00:00'))
            local_time = utc_time.astimezone()  # Convert to local timezone
            date_str = local_time.strftime('%Y-%m-%d')
            
            seen_dates.add(date_str)
            
            # Skip if we already have a file for this date
            if date_str in existing_dates:
                continue
                
            conversations_processed += 1
            
            # Get conversation details and add to daily collection
            conversation_detail = get_conversation_detail(conversation['id'])
            
            if date_str not in daily_conversations:
                daily_conversations[date_str] = []
            
            daily_conversations[date_str].append((conversation, conversation_detail))
            print(f"DEBUG: Added conversation {conversation['id']} for {date_str}")
        
        print(f"DEBUG: Processed {conversations_processed} conversations on page {page}")
        
        # Check if we've processed all pages
        if page >= response.get('totalPages', 1):
            print(f"DEBUG: Reached the last page ({page})")
            break
            
        # Increment page counter
        page += 1
    
    # Process collected conversations
    files_written = 0
    for date_str, conversations in daily_conversations.items():
        # Create the month directory (format: MM-Month)
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        month_name = date_obj.strftime('%B')
        month_num = date_obj.strftime('%m')
        month_dir = target_path / f"{month_num}-{month_name}"
        month_dir.mkdir(exist_ok=True)
        
        output_file = month_dir / f"{date_str}.md"
        
        # Skip if file already exists (double-check to be safe)
        if output_file.exists():
            print(f"DEBUG: File already exists for {date_str}, skipping")
            continue
            
        print(f"DEBUG: Writing {len(conversations)} conversations for {date_str}")
        conversations.sort(key=lambda x: x[0]['start_time'])
        markdown_content = generate_markdown(conversations)
        markdown_content = clean_markdown_content(markdown_content)
        
        output_file.write_text(markdown_content, encoding='utf-8')
        print(f"Created markdown file: {output_file}")
        files_written += 1
    
    print(f"DEBUG: Wrote {files_written} new markdown files")
    return files_written > 0  # Return True if we wrote any files

def get_bee_facts(page=1):
    """
    Send a request to the Bee API to get confirmed facts with paging.
    
    Args:
        page (int): The page number to request
        
    Returns:
        dict: JSON response containing facts or empty structure if request fails
    """
    global BEE_API_KEY
    
    headers = {
        "accept": "application/json",
        "x-api-key": BEE_API_KEY
    }
    
    endpoint = f"{BEE_API_ENDPOINT}/me/facts?confirmed=confirmed"
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
        
        print(f"DEBUG: Got {len(data.get('facts', []))} facts")
        return data
    except requests.RequestException as e:
        print(f"ERROR: API request failed: {e}")
        print(f"DEBUG: Response content: {getattr(e.response, 'text', 'No response content')}")
        return {"facts": []}
    except ValueError as e:
        print(f"ERROR: Failed to parse JSON response: {e}")
        return {"facts": []}
    except Exception as e:
        print(f"ERROR: Unexpected error in get_bee_facts: {e}")
        return {"facts": []}

def process_facts():
    """
    Process facts from the Bee API and insert them into the appropriate markdown files.
    Facts are grouped by date and inserted after the "## Action Items" section.
    Files are organized in monthly directories (MM-MonthName).
    Only facts created on a specific day are added to that day's markdown file.
    Additionally, all facts are appended to a single file at FACTS_FILE_PATH as a simple list.
    
    Returns:
        int: Number of files updated with facts
    """
    target_path = Path(TARGET_DIR)
    facts_by_date = {}
    page = 1
    files_updated = 0
    new_facts = []  # Store new facts to append to the single file
    
    try:
        while True:
            response = get_bee_facts(page)
            
            if not response.get('facts'):
                print("DEBUG: No facts found")
                break
                
            print(f"DEBUG: Processing {len(response['facts'])} facts from page {page}")
            
            # Add all facts to our collection for the single file
            new_facts.extend(response.get('facts', []))
            
            # Group facts by their creation date
            for fact in response['facts']:
                created_at = fact.get('created_at')
                if not created_at:
                    continue
                    
                try:
                    # Handle potential date format issues
                    # Extract just the date portion (YYYY-MM-DD) from the timestamp
                    fact_date_str = datetime.fromisoformat(created_at.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                    
                    if fact_date_str not in facts_by_date:
                        facts_by_date[fact_date_str] = []
                        
                    facts_by_date[fact_date_str].append(fact)
                    print(f"DEBUG: Added fact {fact.get('id')} created on {fact_date_str}")
                except ValueError as e:
                    print(f"ERROR: Invalid date format in fact {fact.get('id')}: {e}")
                    continue
            
            # Check if we've processed all pages
            if page >= response.get('totalPages', 0):
                break
                
            page += 1
        
        # Append new facts to the single file
        if new_facts:
            try:
                # Create the facts file if it doesn't exist
                facts_file = Path(FACTS_FILE_PATH)
                
                # Check if the file exists and read its content
                if facts_file.exists():
                    existing_content = facts_file.read_text(encoding='utf-8')
                else:
                    # Create a new file with a simple header
                    existing_content = "# Facts\n\n"
                
                # Append new facts to the existing content
                new_content = existing_content
                for fact in new_facts:
                    new_content += f"* {fact['text']}\n"
                
                # Write to the facts file
                facts_file.write_text(new_content, encoding='utf-8')
                print(f"DEBUG: Appended {len(new_facts)} facts to {FACTS_FILE_PATH}")
            except Exception as e:
                print(f"ERROR: Failed to write facts to single file: {e}")
        
        # Insert facts into matching markdown files - ONLY if the dates match exactly
        for date_str, facts in facts_by_date.items():
            # Find the file in the monthly directory
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            month_name = date_obj.strftime('%B')
            month_num = date_obj.strftime('%m')
            month_dir = target_path / f"{month_num}-{month_name}"
            
            if not month_dir.exists():
                print(f"DEBUG: Month directory not found for {date_str}: {month_dir}")
                continue
                
            file_path = month_dir / f"{date_str}.md"
            
            if not file_path.exists():
                print(f"DEBUG: No markdown file for {date_str}")
                continue
                
            try:
                # Read the file content
                content = file_path.read_text(encoding='utf-8')
                
                # Check if we've already added facts
                if "### Facts" in content:
                    print(f"DEBUG: Facts already added to {file_path}")
                    continue
                
                # Create facts section
                facts_section = "\n### Facts\n"
                for fact in facts:
                    facts_section += f"* {fact['text']}\n"
                
                # Find the appropriate insertion point (after Action Items or at the end)
                action_items_pattern = r"## Action Items\n[\s\S]*?(?=\n## |\n\nConversation|\Z)"
                match = re.search(action_items_pattern, content)
                
                if match:
                    # Insert after Action Items
                    insertion_point = match.end()
                    updated_content = content[:insertion_point] + facts_section + content[insertion_point:]
                else:
                    # No Action Items section, insert before the first conversation
                    conversation_pattern = r"\n## Conversations"
                    match = re.search(conversation_pattern, content)
                    if match:
                        insertion_point = match.start()
                        updated_content = content[:insertion_point] + facts_section + content[insertion_point:]
                    else:
                        # Just append at the end
                        updated_content = content + "\n" + facts_section
                
                # Write the updated content back to the file
                file_path.write_text(updated_content, encoding='utf-8')
                print(f"DEBUG: Added {len(facts)} facts to {file_path} for {date_str}")
                files_updated += 1
            except Exception as e:
                print(f"ERROR: Failed to update file {file_path}: {e}")
                continue
                
        return files_updated
                
    except Exception as e:
        print(f"ERROR: Unexpected error in process_facts: {e}")
        return files_updated

if __name__ == "__main__":
    try:
        print(f"\nDEBUG: Starting processing at {datetime.now()}")
        
        # Get API key securely from user
        try:
            BEE_API_KEY = get_api_key()
            print("API key received. Beginning processing...")
        except ValueError as e:
            print(f"ERROR: {e}")
            print("Exiting due to API key issue.")
            exit(1)
        
        # Process conversations first
        print(f"\nDEBUG: Starting conversation processing at {datetime.now()}")
        new_conversations_processed = process_conversations()
        
        # Then process facts, but only if we found new conversations or specifically requested
        if new_conversations_processed:
            print(f"\nDEBUG: Starting facts processing at {datetime.now()}")
            files_updated = process_facts()
            print(f"DEBUG: Updated {files_updated} files with facts")
        else:
            print(f"\nDEBUG: No new conversation files created, skipping facts processing")
        
        print(f"\nDEBUG: All processing completed at {datetime.now()}")
        
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: API request failed: {e}")
        print(f"Check your internet connection and API endpoint configuration.")
    except Exception as e:
        print(f"Failed to process: {e}")
        # In a production environment, you might want to log the full traceback
        import traceback
        traceback.print_exc()