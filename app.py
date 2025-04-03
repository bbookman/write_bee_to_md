import requests
from config import BEE_API_KEY, BEE_API_ENDPOINT

def get_bee_conversations():
    """
    Send a request to the Bee API to get conversations.
    
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
    
    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error making API request: {e}")
        raise

if __name__ == "__main__":
    try:
        conversations = get_bee_conversations()
        print(conversations)
    except Exception as e:
        print(f"Failed to get conversations: {e}")