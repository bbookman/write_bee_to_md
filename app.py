import requests
from config import BEE_API_KEY, BEE_API_ENDPOINT, TARGET_DIR
from datetime import datetime
from pathlib import Path

def get_bee_conversations(page=1):
    """
    Send a request to the Bee API to get conversations with paging.
    
    Args:
        page (int): Page number to retrieve
    Returns:
        dict: The JSON response from the API
    Raises:
        requests.RequestException: If the request fails
    """
    headers = {
        "accept": "application/json",
        "x-api-key": BEE_API_KEY
    }
    
    endpoint = f"{BEE_API_ENDPOINT}/me/conversations"
    params = {"page": page}
    
    try:
        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error making API request: {e}")
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

def generate_markdown(conversation):
    """
    Generate markdown content from a conversation.
    """
    content = []
    
    # Add short summary as header
    content.append(f"# {conversation['short_summary']}\n")
    
    # Add conversation ID
    content.append(f"Conversation ID: {conversation['id']}\n")
    
    # Add address if available
    if conversation.get('primary_location') and conversation['primary_location'].get('address'):
        content.append(f"Location: {conversation['primary_location']['address']}\n")
    
    # Add summary as subheading, cleaning up the text
    if conversation.get('summary'):
        summary_text = clean_bee_text(conversation['summary'])
        content.append(f"\n## Summary\n{summary_text}\n")
    
    return "\n".join(content)

def process_conversations():
    """
    Process all conversations and create markdown files in TARGET_DIR.
    Append multiple conversations from the same day to the same file.
    """
    # Create target directory if it doesn't exist
    target_path = Path(TARGET_DIR)
    target_path.mkdir(parents=True, exist_ok=True)
    
    page = 1
    daily_conversations = {}  # Store conversations by date
    
    while True:
        response = get_bee_conversations(page)
        
        if not response.get('conversations'):
            break
            
        for conversation in response['conversations']:
            # Convert start_time to date string
            start_date = datetime.fromisoformat(conversation['start_time'].replace('Z', '+00:00'))
            date_str = start_date.strftime('%Y-%m-%d')
            
            # Add conversation to daily collection
            if date_str not in daily_conversations:
                daily_conversations[date_str] = []
            daily_conversations[date_str].append(conversation)
        
        # Move to next page
        if page >= response.get('totalPages', 0):
            break
            
        page += 1
    
    # Write all conversations for each date to their respective files
    for date_str, conversations in daily_conversations.items():
        # Sort conversations by start_time
        conversations.sort(key=lambda x: x['start_time'])
        
        # Generate markdown for all conversations
        markdown_content = []
        for conversation in conversations:
            markdown_content.append(generate_markdown(conversation))
        
        # Write markdown file to target directory
        output_file = target_path / f"{date_str}.md"
        output_file.write_text("\n\n".join(markdown_content), encoding='utf-8')
        
        print(f"Created markdown file: {output_file}")

if __name__ == "__main__":
    try:
        process_conversations()
    except Exception as e:
        print(f"Failed to process conversations: {e}")