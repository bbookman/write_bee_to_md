# Bee to Markdown Converter

This application converts Bee conversations into organized markdown files. It processes conversations from the Bee API and creates daily markdown summaries, making them suitable for personal knowledge management systems.

## Features

- Converts Bee conversations into structured markdown files
- Organizes conversations by date
- Includes conversation summaries, locations, and transcripts
- Automatically runs every 6 hours
- Skips processing of current day's conversations
- Avoids overwriting existing files

## Requirements

- Python 3.6+
- `requests` library
- Access to Bee API (API key required)

## Configuration

1. Copy the example configuration:

```python
BEE_API_KEY = "YOUR_BEE_API_KEY"
BEE_API_ENDPOINT = "https://api.bee.computer/v1"
TARGET_DIR = "/path/to/output/directory"
```

2. Update `config.py` with your:
   - Bee API key
   - Target directory for markdown files

## File Structure

Generated markdown files follow this format:

```markdown
# YYYY-MM-DD

## [Daily Summary]

### Atmosphere

[atmosphere content]

### Key Takeaways

[key takeaways content]

### Action Items

[action items content]

Conversation ID: [id]
Location: [address]
[conversation summary]

### Transcript

Speaker 1: [text]
Speaker 2: [text]
...
```

## Running the Application

1. Install dependencies:

```bash
pip3 install requests
```

2. Run the script:

```bash
python3 app.py
```

The application will:

- Run immediately upon starting
- Process all historical conversations
- Create markdown files for each day
- Skip today's conversations
- Run automatically every 6 hours
- Continue running until stopped with Ctrl+C

## Notes

- Files are created in the specified TARGET_DIR
- Only processes conversations from completed days
- Existing files will not be overwritten
- Runs continuously with 6-hour intervals
- Uses the Bee API v1 endpoint
