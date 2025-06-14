# Notion AI Agent with Mem0AI

A powerful AI agent that combines Notion's capabilities with Mem0AI, built using Gemini Flash 2.0. This project creates an intelligent assistant that can interact with Notion databases and pages while leveraging Mem0AI's memory capabilities.

## Applications

### Knowledge Management
- Automatically organize and categorize information in Notion databases
- Create and maintain knowledge bases with AI-powered suggestions
- Smart search and retrieval of information across multiple Notion pages

### Task Management
- AI-assisted task creation and organization
- Intelligent task prioritization and scheduling
- Automated task status updates and progress tracking

### Content Creation
- Generate and format content for Notion pages
- Create structured documentation with AI assistance
- Maintain consistent formatting and style across documents

### Data Analysis
- Process and analyze data stored in Notion databases
- Generate insights and reports from Notion content
- Create visualizations and summaries of database information

## Detailed Setup Instructions

### Prerequisites
- Python 3.8 or higher
- A Notion account with API access
- Groq API key
- Mem0AI account

### Step 1: Clone the Repository
```bash
git clone https://github.com/yourusername/notion_ai_agent_mem0.git
cd notion_ai_agent_mem0
```

### Step 2: Create and Activate Virtual Environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Environment Configuration
1. Create a `.env` file in the project root:
```bash
touch .env
```

2. Add the following environment variables to `.env`:
```
NOTION_API_KEY=your_notion_api_key
GROQ_API_KEY=your_groq_api_key
MEM0AI_API_KEY=your_mem0ai_api_key
```

### Step 5: Notion Integration Setup
1. Go to https://www.notion.so/my-integrations
2. Create a new integration
3. Copy the integration token to your `.env` file
4. Share your Notion pages/databases with the integration

### Step 6: Run the Application
```bash
streamlit run streamlit_notion_chatbot.py
```

### Step 7: Access the Application
- Open your web browser
- Navigate to http://localhost:8501
- The application interface will be available

## Troubleshooting

### Common Issues
1. API Key Errors
   - Verify all API keys are correctly set in `.env`
   - Ensure keys have proper permissions

2. Notion Access Issues
   - Check if the integration has been shared with required pages
   - Verify page/database permissions

3. Memory Management
   - Clear Mem0AI cache if experiencing memory issues
   - Monitor system resources during heavy operations

## Project Structure

- `streamlit_notion_chatbot.py`: Main Streamlit application
- `notion_databases.py`: Notion database operations
- `notion_pages.py`: Notion page management
- `mainv2.py`: Core application logic
- `memoai.ipynb`: Development and testing notebooks

## License

MIT License
