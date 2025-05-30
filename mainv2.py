import os
from groq import Groq
from mem0 import MemoryClient
import json
from dotenv import load_dotenv
import sys
import traceback

# Import with error handling
# checking it databases and pages are present in our notion integration
try:
    from notion_databases import get_all_databases_content
    NOTION_DB_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  notion_databases module not available: {e}")
    NOTION_DB_AVAILABLE = False

try:
    from notion_pages import get_accessible_pages, get_page_content
    NOTION_PAGES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  notion_pages module not available: {e}")
    NOTION_PAGES_AVAILABLE = False

# creating a chat bot for notion with groq
class NotionGroqChatbot:
    def __init__(self, groq_api_key, mem0_api_key):
        """
        Initialize the Groq chatbot with Mem0 cloud memory and Notion integration
        
        Args:
            groq_api_key (str): Your Groq API key
            mem0_api_key (str): Your Mem0 API key for cloud storage
        """
        print(" Initializing chatbot components...")
        
        # Initialize Groq client
        try:
            self.groq_client = Groq(api_key=groq_api_key)
            print("✅ Groq client initialized")
        except Exception as e:
            print(f"❌ Error initializing Groq client: {e}")
            raise
        
        # Initialize Mem0 cloud client
        try:
            print(" Initializing cloud memory system...")
            self.memory = MemoryClient(api_key=mem0_api_key)
            print(" Cloud memory system initialized")
        except Exception as e:
            print(f" Error initializing cloud memory: {e}")
            raise
        
        self.user_id = None  # Will be set after getting user name
        self.notion_content = ""  # Will store loaded Notion content
        self.notion_loaded = False
        
        print(" Chatbot initialization complete")
        
    def get_user_info(self):
        """Get user name for personalized memory management"""
        print(" Welcome to Notion AI Chatbot!")
        print("=" * 50)
        
        while True:
            try:
                user_name = input("\n Please enter your name: ").strip()
                if user_name:
                    self.user_id = f"user_{user_name.lower().replace(' ', '_')}"
                    print(f"\n Hello {user_name}! Your conversations will be saved under ID: {self.user_id}")
                    break
                else:
                    print(" Please enter a valid name.")
            except KeyboardInterrupt:
                print("\n Goodbye!")
                sys.exit(0)
            except Exception as e:
                print(f" Error getting user input: {e}")
                return

    def select_notion_content(self):
        """Let user select which Notion databases and pages to load"""
        if not NOTION_DB_AVAILABLE and not NOTION_PAGES_AVAILABLE:
            print("  Notion modules not available. Skipping Notion content selection.")
            return [], []
            
        print("\n Notion Content Selection")
        print("=" * 50)
        
        selected_databases = []
        selected_pages = []
        
        try:
            # Ask about databases
            if NOTION_DB_AVAILABLE:
                load_databases = input("\n Do you want to load database content? (y/n): ").strip().lower()
                if load_databases in ['y', 'yes']:
                    selected_databases = ['all']  # For now, load all databases
                    print(" Will load all accessible databases")
            
            # Get available pages
            if NOTION_PAGES_AVAILABLE:
                print("\n Checking available pages...")
                try:
                    pages = get_accessible_pages()
                except Exception as e:
                    print(f" Error getting pages: {e}")
                    pages = []
                
                if pages:
                    print(f"\n Found {len(pages)} accessible pages:")
                    print("-" * 40)
                    
                    for i, page in enumerate(pages, 1):
                        title = page.get('title', 'Untitled')
                        print(f"{i:2d}. {title[:50]}")
                    
                    print("\n Page Selection Options:")
                    print("  • Enter page numbers (e.g., 1,3,5 or 1-5)")
                    print("  • Type 'all' to load all pages")
                    print("  • Type 'none' to skip pages")
                    print("  • Press Enter to skip pages")
                    
                    page_selection = input("\n Select pages to load: ").strip()
                    
                    if page_selection.lower() == 'all':
                        selected_pages = pages
                        print(f" Will load all {len(pages)} pages")
                    elif page_selection.lower() in ['none', '']:
                        selected_pages = []
                        print("  Skipping pages")
                    else:
                        # Parse selection (e.g., "1,3,5" or "1-5")
                        selected_pages = self.parse_page_selection(page_selection, pages)
                        if selected_pages:
                            print(f" Will load {len(selected_pages)} selected pages:")
                            for page in selected_pages:
                                print(f"   • {page.get('title', 'Untitled')}")
                        else:
                            print("  No valid pages selected")
                else:
                    print("  No accessible pages found")
        
        except KeyboardInterrupt:
            print("\n⏭  Skipping Notion content selection...")
            return [], []
        except Exception as e:
            print(f" Error during content selection: {e}")
            print("  Will continue without Notion content...")
            return [], []
        
        return selected_databases, selected_pages

    def parse_page_selection(self, selection, pages):
        """Parse user's page selection input"""
        selected_pages = []
        
        try:
            # Split by comma for multiple selections
            parts = [part.strip() for part in selection.split(',')]
            
            for part in parts:
                if '-' in part:
                    # Handle range (e.g., "1-5")
                    start, end = part.split('-', 1)
                    start_idx = int(start.strip()) - 1
                    end_idx = int(end.strip()) - 1
                    
                    if 0 <= start_idx < len(pages) and 0 <= end_idx < len(pages):
                        for i in range(start_idx, min(end_idx + 1, len(pages))):
                            if pages[i] not in selected_pages:
                                selected_pages.append(pages[i])
                else:
                    # Handle single number
                    page_num = int(part) - 1
                    if 0 <= page_num < len(pages):
                        if pages[page_num] not in selected_pages:
                            selected_pages.append(pages[page_num])
        
        except (ValueError, IndexError) as e:
            print(f"  Invalid selection format: {e}")
            return []
        
        return selected_pages

    def load_notion_content(self):
        """Load selected content from Notion databases and pages"""
        print("\n📚 Loading Notion content...")
        
        # Check if Notion modules are available
        if not NOTION_DB_AVAILABLE and not NOTION_PAGES_AVAILABLE:
            print("  Notion integration modules not available. Skipping Notion content loading.")
            return
        
        # Let user select content first
        try:
            selected_databases, selected_pages = self.select_notion_content()
        except Exception as e:
            print(f" Error in content selection: {e}")
            return
        
        if not selected_databases and not selected_pages:
            print("  No Notion content selected. Continuing without Notion integration.")
            return
        
        print("\n Processing selected content...")
        print("=" * 50)
        
        try:
            database_content = ""
            page_content = ""
            
            # Load selected database content
            if selected_databases and NOTION_DB_AVAILABLE:
                print("🗃️  Loading selected databases...")
                try:
                    database_content = get_all_databases_content()
                    if database_content:
                        print(" Database content loaded successfully")
                    else:
                        print("  No database content found")
                except Exception as e:
                    print(f" Error loading databases: {e}")
            
            # Load selected page content
            if selected_pages and NOTION_PAGES_AVAILABLE:
                print(f" Loading {len(selected_pages)} selected pages...")
                
                for i, page in enumerate(selected_pages, 1):
                    page_title = page.get('title', 'Untitled')
                    print(f"   Processing page {i}/{len(selected_pages)}: {page_title}")
                    
                    try:
                        content_data = get_page_content(page['id'])
                        if content_data:
                            page_content += f"\n{'='*80}\n"
                            page_content += f"PAGE: {content_data['title']}\n"
                            page_content += f"{'='*80}\n"
                            page_content += content_data['content'] + "\n\n"
                            print(f"Loaded successfully")
                        else:
                            print(f"No content found")
                    except Exception as e:
                        print(f"Error loading page: {e}")
            
            # Combine all selected content
            self.notion_content = ""
            if database_content:
                self.notion_content += "NOTION DATABASES:\n" + "="*80 + "\n" + database_content + "\n\n"
            if page_content:
                self.notion_content += "NOTION PAGES:\n" + "="*80 + "\n" + page_content
            
            # Store Notion content in cloud memory
            if self.notion_content:
                try:
                    messages = [{"role": "system", "content": f"Notion Knowledge Base Content:\n{self.notion_content}"}]
                    self.memory.add(messages, user_id=self.user_id)
                    print(f"\n Successfully loaded {len(self.notion_content)} characters from Notion to cloud memory")
                    print(f"   - Databases: {'✅' if database_content else '❌'}")
                    print(f"   - Pages: {'✅' if page_content else '❌'} ({len(selected_pages)} pages)")
                    self.notion_loaded = True
                    
                    # Show summary of loaded content
                    print(f"\n Content Summary:")
                    if selected_databases:
                        print(f"Databases: Loaded")
                    if selected_pages:
                        print(f"Pages loaded:")
                        for page in selected_pages:
                            print(f"      • {page.get('title', 'Untitled')}")
                except Exception as e:
                    print(f" Error storing content in cloud memory: {e}")
            else:
                print("  No content was loaded. Make sure pages/databases are shared with your integration.")
                
        except Exception as e:
            print(f" Error loading Notion content: {e}")
            print("  Continuing without Notion content...")

    def show_loaded_content(self):
        """Show what Notion content is currently loaded"""
        if not self.notion_loaded or not self.notion_content:
            print(" No Notion content is currently loaded.")
            return
        
        print(f"\n Currently Loaded Notion Content:")
        print("=" * 50)
        
        # Count databases and pages
        db_count = 1 if "NOTION DATABASES:" in self.notion_content else 0
        page_count = self.notion_content.count("PAGE: ") if "NOTION PAGES:" in self.notion_content else 0
        
        print(f" Summary:")
        print(f"Databases: {db_count}")
        print(f"Pages: {page_count}")
        print(f"Total characters: {len(self.notion_content):,}")
        
        if page_count > 0:
            print(f"\Loaded Pages:")
            # Extract page titles
            lines = self.notion_content.split('\n')
            for line in lines:
                if line.startswith("PAGE: "):
                    page_title = line.replace("PAGE: ", "").strip()
                    print(f"   • {page_title}")
    
    def get_relevant_memories(self, query, limit=5):
        """
        Retrieve relevant memories from cloud memory based on the current query
        """
        try:
            memories = self.memory.search(query, user_id=self.user_id, version="v2", limit=limit)
            memory_texts = []
            # Handle the list of memory dictionaries directly
            for memory in memories:
                try:
                    # Ensure memory is for the current user
                    if memory.get("user_id") == self.user_id:
                        memory_text = memory.get("memory", str(memory))
                        if memory_text:
                            memory_texts.append(memory_text)
                except Exception as inner_e:
                    print(f" Error processing memory: {inner_e}")
                    continue
            if not memory_texts:
                print(f"ℹ No relevant memories found for query: {query}")
            return memory_texts
        except Exception as e:
            print(f" Error retrieving memories: {e}")
            try:
                # Log the API response for debugging
                import requests
                response = requests.post(
                    "https://api.mem0.ai/v1/memories/search",
                    headers={"Authorization": f"Bearer {os.getenv('MEM0_API_KEY')}"},
                    json={"query": query, "user_id": self.user_id, "version": "v2", "limit": limit}
                )
                print(f"DEBUG: API response: {response.text}")
            except Exception as debug_e:
                print(f" Error debugging API response: {debug_e}")
            return []
    
    def add_to_memory(self, message, response):
        """
        Add the conversation to cloud memory
        """
        try:
            # Format conversation as a list of message dictionaries
            conversation = [
                {"role": "user", "content": message},
                {"role": "assistant", "content": response}
            ]
            self.memory.add(conversation, user_id=self.user_id)
            print(f" Added conversation to cloud memory for user: {self.user_id}")
        except Exception as e:
            print(f" Error adding to cloud memory: {e}")
    
    def generate_response(self, user_message, model="llama3-8b-8192"):
        """
        Generate a response using Groq with context from cloud memory and Notion content
        """
        try:
            # Get relevant memories (excluding the Notion knowledge base)
            relevant_memories = self.get_relevant_memories(user_message)
            
            # Filter out the large Notion knowledge base from memories for context
            filtered_memories = []
            for mem in relevant_memories:
                if isinstance(mem, str) and not mem.startswith("Notion Knowledge Base Content:"):
                    filtered_memories.append(mem)
                elif not isinstance(mem, str):
                    mem_str = str(mem)
                    if not mem_str.startswith("Notion Knowledge Base Content:"):
                        filtered_memories.append(mem_str)
            
            # Build context from memories
            context = ""
            if filtered_memories:
                context = "Previous conversation context:\n" + "\n".join(filtered_memories[:3]) + "\n\n"
            
            # Add Notion content context if available
            notion_context = ""
            if self.notion_loaded and self.notion_content:
                # Use a smaller subset of Notion content to avoid token limits
                notion_preview = self.notion_content[:3000] + "..." if len(self.notion_content) > 3000 else self.notion_content
                notion_context = f"Notion Knowledge Base (use this to answer questions about the user's Notion content):\n{notion_preview}\n\n"
            
            # Create the system prompt
            system_prompt = f"""You are a helpful AI assistant with access to the user's Notion workspace content. Use the following information to provide relevant and personalized responses.

{notion_context}{context}Instructions:
- Answer questions using information from the Notion content when relevant
- Reference specific pages, databases, or entries when applicable
- If asked about something not in the Notion content, use your general knowledge
- Be conversational and helpful
- Remember previous conversations for context

Current conversation:"""
            
            # Generate response using Groq
            chat_completion = self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                model=model,
                temperature=0.7,
                max_tokens=1024
            )
            
            response = chat_completion.choices[0].message.content
            
            # Add this conversation to cloud memory
            self.add_to_memory(user_message, response)
            
            return response
            
        except Exception as e:
            return f" Error generating response: {e}"
    
    def show_memories(self):
        """Show user's conversation memories from cloud storage"""
        try:
            # Get all memories for the user from cloud
            memories = self.memory.get_all(user_id=self.user_id, version="v2")
            print(f"DEBUG: Raw memories (count: {len(memories)}): {memories}")  # Debug print
            
            if memories and len(memories) > 0:
                print(f"\n Your conversation memories ({len(memories)} total):")
                print("-" * 60)
                
                displayed_count = 0
                # Filter memories by user_id and reverse to show most recent first
                user_memories = [m for m in memories if m.get("user_id") == self.user_id]
                recent_memories = list(reversed(user_memories))[:10]
                
                for i, memory in enumerate(recent_memories, 1):
                    try:
                        memory_text = memory.get("memory", str(memory))
                        # Skip the large Notion knowledge base content
                        if memory_text and not memory_text.startswith("Notion Knowledge Base Content:"):
                            displayed_count += 1
                            preview = memory_text[:150] + "..." if len(memory_text) > 150 else memory_text
                            print(f"{displayed_count}. {preview}")
                            
                            if displayed_count >= 5:  # Limit to 5 displayed memories
                                break
                        
                    except Exception as inner_e:
                        print(f" Error processing memory {i}: {inner_e}")
                        continue
                
                if displayed_count == 0:
                    print("No conversation memories found for your user ID.")
                
                print("-" * 60)
            else:
                print("\n No memories found for your user ID in cloud storage.")
            
        except Exception as e:
            print(f" Error retrieving memories: {e}")
            print(" This might be due to a network issue or invalid API key. Check your MEM0_API_KEY and try again.")

    def clear_memory(self):
        """
        Clear all memories for the current user from cloud storage
        """
        try:
            self.memory.delete_all(user_id=self.user_id)
            print("  Cloud memory cleared successfully!")
            # Reload Notion content after clearing
            if NOTION_DB_AVAILABLE or NOTION_PAGES_AVAILABLE:
                self.load_notion_content()
        except Exception as e:
            print(f" Error clearing cloud memory: {e}")
            print(" Check your MEM0_API_KEY and network connection.")

    def chat(self):
        """
        Start an interactive chat session
        """
        try:
            # Get user information
            self.get_user_info()
            
            # Load Notion content with selection
            self.load_notion_content()
            
            print(f"\n Notion AI Chatbot ready! (User: {self.user_id})")
            print(" I can answer questions about your loaded Notion content and remember our conversations in the cloud")
            print(" Available commands:")
            print("   • 'quit' - Exit the chatbot")
            print("   • 'memory' - Show conversation memories")
            print("   • 'clear' - Clear all memories")
            print("   • 'reload' - Reload Notion content")
            print("   • 'content' - Show currently loaded content")
            print("=" * 80)
            
            while True:
                try:
                    user_input = input(f"\n{self.user_id.replace('user_', '').title()}: ").strip()
                    
                    if user_input.lower() in ['quit', 'exit', 'bye']:
                        print("👋 Goodbye! Your memories have been saved in the cloud.")
                        break
                    
                    if user_input.lower() == 'memory':
                        self.show_memories()
                        continue
                        
                    if user_input.lower() == 'clear':
                        self.clear_memory()
                        continue
                        
                    if user_input.lower() == 'reload':
                        self.load_notion_content()
                        continue
                        
                    if user_input.lower() == 'content':
                        self.show_loaded_content()
                        continue
                    
                    if not user_input:
                        continue
                        
                    print(" Assistant: ", end="", flush=True)
                    response = self.generate_response(user_input)
                    print(response)
                    
                except KeyboardInterrupt:
                    print("\n Goodbye!")
                    break
                except Exception as e:
                    print(f"\n Error in chat loop: {e}")
                    continue
                    
        except Exception as e:
            print(f" Error in chat session: {e}")
            traceback.print_exc()


def main():
    print("🔧 Starting Notion Groq Chatbot...")
    
    try:
        load_dotenv()
        print(" Environment variables loaded")
    except Exception as e:
        print(f"  Could not load .env file: {e}")
    
    # Configuration
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    MEM0_API_KEY = os.getenv("MEM0_API_KEY")
    
    if not GROQ_API_KEY:
        print(" Please set your GROQ_API_KEY environment variable")
        print(" You can get your API key from: https://console.groq.com/keys")
        print(" Add it to your .env file: GROQ_API_KEY=your_key_here")
        return
    
    if not MEM0_API_KEY:
        print(" Please set your MEM0_API_KEY environment variable")
        print(" Sign up at https://app.mem0.ai/ to get your API key")
        print(" Add it to your .env file: MEM0_API_KEY=your_key_here")
        return
    
    # Check if Notion token is set
    NOTION_TOKEN = os.getenv("NOTION_TOKEN")
    if not NOTION_TOKEN:
        print("  NOTION_TOKEN not found. Notion integration will be limited.")
        print(" Set NOTION_TOKEN in your .env file to enable full Notion features.")
        # Initialize and start the chatbot
    try:
        print(" Initializing chatbot...")
        chatbot = NotionGroqChatbot(GROQ_API_KEY, MEM0_API_KEY)
        chatbot.chat()
    except KeyboardInterrupt:
        print("\n Goodbye!")
    except Exception as e:
        print(f" Error initializing chatbot: {e}")
        print("\n Full error details:")
        traceback.print_exc()
        print("\n Make sure you have installed the required packages:")
        print("pip install groq mem0ai notion-client python-dotenv")


if __name__ == "__main__":
    main()