import requests
from config import BEE_API_ENDPOINT, TARGET_DIR  # Removed BEE_API_KEY
from datetime import datetime, timedelta
from pathlib import Path
import re
import time
import getpass  # Added for secure password input
import json  # Added for JSON handling

def write_json_to_file(data, prefix=''):
    """
    Write the JSON data to a text file.
    
    Args:
        data: The JSON data to write
        prefix: Optional prefix to add to the line for identifying different API calls
    """
    file_path = Path("return_json.txt")
    
    # Create or append to the file
    mode = "a" if file_path.exists() else "w"
    
    with open(file_path, mode, encoding='utf-8') as f:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"\n\n--- {prefix} Response at {timestamp} ---\n")
        f.write(json.dumps(data, indent=2))
        f.write("\n")
    
    print(f"DEBUG: Wrote {prefix} JSON data to {file_path}")

def get_api_key(max_attempts=3):
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
        
        # Write JSON response to file
        write_json_to_file(data, f"Conversations_Page_{page}")
        
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
    global BEE_API_KEY
    
    headers = {
        "accept": "application/json",
        "x-api-key": BEE_API_KEY
    }
    
    endpoint = f"{BEE_API_ENDPOINT}/me/conversations/{conversation_id}"
    
    # print(f"\nDEBUG: Getting conversation detail from {endpoint}")
    
    try:
        response = requests.get(endpoint, headers=headers)
        print(f"DEBUG: Detail response status: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        
        # Write JSON response to file
        write_json_to_file(data, f"Conversation_Detail_{conversation_id}")
        
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
        ('Summary:', ''),

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
        
        # Add sections with proper markdown headers
        atmosphere = extract_section(conversations_for_day[0][0]['summary'], 'Atmosphere')
        if atmosphere:
            content.append("## Atmosphere")
            content.append(atmosphere + "\n")
        
        key_takeaways = extract_section(conversations_for_day[0][0]['summary'], 'Key Takeaways')
        if key_takeaways and key_takeaways.strip():
            content.append("## Key Takeaways")
            content.append(key_takeaways.strip())
            content.append("\n")
        
        action_items = extract_section(conversations_for_day[0][0]['summary'], 'Action Items')
        if action_items:
            content.append("## Action Items")
            content.append(action_items + "\n")
    
    # Process ALL conversations for this day
    ''''''
    content.append("## Conversations")
    content.append("")
    ''''''
    
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
                    content.append(f"**Speaker {utterance['speaker']}**: {utterance['text']}")
    
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
    
    print(f"DEBUG: Found {len(existing_dates)} existing date files")
    
    # Track which dates we've seen in the API responses
    seen_dates = set()
    daily_conversations = {}
    page = 1
    all_needed_files_written = False
    
    # Process pages until we've found all missing dates or reached the end
    while not all_needed_files_written:
        response = get_bee_conversations(page)
        
        if not response.get('conversations'):
            print(f"DEBUG: No conversations found on page {page}")
            break
        
        print(f"DEBUG: Processing page {page} of {response.get('totalPages', 1)}")
        
        # Track which dates we need to write files for on this page
        new_dates_on_this_page = set()
        
        # First pass - just collect all date strings to determine range
        for conversation in response['conversations']:
            start_date = datetime.fromisoformat(conversation['start_time'].replace('Z', '+00:00'))
            date_str = start_date.strftime('%Y-%m-%d')
            seen_dates.add(date_str)
            
            # Skip if it's today or we already have a file
            if start_date.date() >= datetime.now().date() or date_str in existing_dates:
                continue
                
            # Track that we found a new date on this page
            new_dates_on_this_page.add(date_str)
                
            # Get conversation details and add to daily collection
            conversation_detail = get_conversation_detail(conversation['id'])
            
            if date_str not in daily_conversations:
                daily_conversations[date_str] = []
            
            daily_conversations[date_str].append((conversation, conversation_detail))
            print(f"DEBUG: Added conversation {conversation['id']} for {date_str}")
        
        # If we didn't find any new dates on this page, check if we need to continue
        if not new_dates_on_this_page:
            print(f"DEBUG: No new dates found on page {page}")
            
            # If we've reached the last page or we've processed everything up to yesterday
            if page >= response.get('totalPages', 1):
                print(f"DEBUG: Reached the last page ({page})")
                all_needed_files_written = True
                break
        
        # Check if we've processed all pages
        if page >= response.get('totalPages', 1):
            print(f"DEBUG: Reached the last page ({page})")
            all_needed_files_written = True
            break
            
        # Increment page counter
        page += 1
    
    # Process collected conversations
    files_written = 0
    for date_str, conversations in daily_conversations.items():
        output_file = target_path / f"{date_str}.md"
        
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
        
        # Write JSON response to file
        write_json_to_file(data, f"Facts_Page_{page}")
        
        print(f"DEBUG: Got {len(data.get('facts', []))} facts")
        return data
    except requests.RequestException as e:
        print(f"ERROR: API request failed: {e}")
        print(f"DEBUG: Response content: {getattr(e.response, 'text', 'No response content')}")
        return {"facts": []}

def process_facts():
    """
    Process facts from the Bee API and insert them into the appropriate markdown files.
    Facts are grouped by date and inserted after the "## Action Items" section.
    """
    target_path = Path(TARGET_DIR)
    facts_by_date = {}
    page = 1
    
    while True:
        response = get_bee_facts(page)
        
        if not response.get('facts'):
            print("DEBUG: No facts found")
            break
            
        print(f"DEBUG: Processing {len(response['facts'])} facts from page {page}")
        
        # Group facts by date
        for fact in response['facts']:
            created_at = fact.get('created_at')
            if not created_at:
                continue
                
            date_str = datetime.fromisoformat(created_at.replace('Z', '+00:00')).strftime('%Y-%m-%d')
            
            if date_str not in facts_by_date:
                facts_by_date[date_str] = []
                
            facts_by_date[date_str].append(fact)
        
        # Check if we've processed all pages
        if page >= response.get('totalPages', 0):
            break
            
        page += 1
    
    # Insert facts into matching markdown files
    for date_str, facts in facts_by_date.items():
        file_path = target_path / f"{date_str}.md"
        
        if not file_path.exists():
            print(f"DEBUG: No markdown file for {date_str}")
            continue
            
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
        print(f"DEBUG: Added {len(facts)} facts to {file_path}")

if __name__ == "__main__":
    try:
        # Delete the return_json.txt file if it exists
        json_file = Path("return_json.txt")
        if json_file.exists():
            json_file.unlink()
            print(f"DEBUG: Deleted existing {json_file}")
        
        print(f"\nDEBUG: Starting conversation processing at {datetime.now()}")
        BEE_API_KEY = get_api_key()  # Get API key from user
        print("API key received. Beginning processing...")
        
        # Process conversations first
        process_conversations()
        
        # Then process facts
        print(f"\nDEBUG: Starting facts processing at {datetime.now()}")
        process_facts()
        
        print(f"\nDEBUG: All processing completed at {datetime.now()}")
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        print(f"Failed to process: {e}")