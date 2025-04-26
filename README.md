# Bee to Markdown Converter

This application converts Bee conversations into organized markdown files. It processes conversations from the Bee API and creates daily markdown summaries, making them suitable for personal knowledge management systems.

## Features

- Converts Bee conversations into structured markdown files
- Organizes conversations by date
- Includes conversation summaries, locations, and transcripts
- Extracts facts from the Bee API and adds them to relevant markdown files
- Processes only historical data (up to yesterday)
- Smart pagination to minimize API calls
- Avoids overwriting existing files
- Comprehensive error handling

## Requirements

- Python 3.6+
- `requests` library
- Access to Bee API (API key required)

## Configuration

1. Create a `config.py` file with the following:

```python
BEE_API_KEY = "YOUR_BEE_API_KEY"  # Optional - can be entered at runtime
BEE_API_ENDPOINT = "https://api.bee.computer/v1"
TARGET_DIR = "/path/to/output/directory"
```

2. If you don't provide a `BEE_API_KEY` in the config file, the application will prompt you for it at runtime.

## File Structure

Generated markdown files follow this format:

```markdown
# Daily Summary

[main summary content]

## Atmosphere

[atmosphere content]

## Key Takeaways

[key takeaways content]

## Action Items

[action items content]

### Facts

- [fact 1]
- [fact 2]
- ...

## Conversations

Conversation 1 (ID: [id])
Location: [address]
[conversation summary]

Transcript:
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

- Prompt for your Bee API key if not found in config.py
- Process all historical conversations up to yesterday
- Create markdown files for each day
- Add facts to each day's markdown file
- Skip processing for dates that already have files
- Continue processing until all needed files are created

## Usage Notes

- Files are created in the specified TARGET_DIR
- Only processes conversations from completed days (up to yesterday)
- Existing files will not be overwritten
- Early termination when all needed files are processed
- Logs all API responses to a `return_json.txt` file for debugging
