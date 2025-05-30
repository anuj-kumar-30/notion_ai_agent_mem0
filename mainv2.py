import streamlit as st
import os
from groq import Groq
from mem0 import MemoryClient
import json
from dotenv import load_dotenv
import traceback
import sys

# Import with error handling and better debugging
try:
    from notion_databases import get_all_databases_content
    NOTION_DB_AVAILABLE = True
except ImportError as e:
    st.error(f"⚠️ notion_databases module not available: {e}")
    NOTION_DB_AVAILABLE = False

try:
    from notion_pages import get_accessible_pages, get_page_content
    NOTION_PAGES_AVAILABLE = True
except ImportError as e:
    st.error(f"⚠️ notion_pages module not available: {e}")
    NOTION_PAGES_AVAILABLE = False

# Load environment variables - handle deployment scenarios
try:
    load_dotenv()
except Exception as e:
    st.warning(f"Could not load .env file: {e}")

class StreamlitNotionChatbot:
    def __init__(self, groq_api_key, mem0_api_key):
        """Initialize the chatbot with API keys"""
        try:
            self.groq_client = Groq(api_key=groq_api_key)
            self.memory = MemoryClient(api_key=mem0_api_key)
            st.success("✅ Chatbot initialized successfully!")
        except Exception as e:
            st.error(f"❌ Error initializing chatbot: {e}")
            st.stop()
    
    def get_relevant_memories(self, query, user_id, limit=5):
        """Retrieve relevant memories from cloud memory"""
        try:
            memories = self.memory.search(query, user_id=user_id, version="v2", limit=limit)
            memory_texts = []
            for memory in memories:
                try:
                    if memory.get("user_id") == user_id:
                        memory_text = memory.get("memory", str(memory))
                        if memory_text:
                            memory_texts.append(memory_text)
                except Exception:
                    continue
            return memory_texts
        except Exception as e:
            st.error(f"❌ Error retrieving memories: {e}")
            return []
    
    def add_to_memory(self, message, response, user_id):
        """Add conversation to cloud memory"""
        try:
            conversation = [
                {"role": "user", "content": message},
                {"role": "assistant", "content": response}
            ]
            self.memory.add(conversation, user_id=user_id)
        except Exception as e:
            st.error(f"❌ Error adding to memory: {e}")
    
    def generate_response(self, user_message, user_id, notion_content="", model="llama3-8b-8192"):
        """Generate response using Groq with context"""
        try:
            # Get relevant memories
            relevant_memories = self.get_relevant_memories(user_message, user_id)
            
            # Filter out large Notion knowledge base from memories
            filtered_memories = []
            for mem in relevant_memories:
                if isinstance(mem, str) and not mem.startswith("Notion Knowledge Base Content:"):
                    filtered_memories.append(mem)
            
            # Build context
            context = ""
            if filtered_memories:
                context = "Previous conversation context:\n" + "\n".join(filtered_memories[:3]) + "\n\n"
            
            # Add Notion context
            notion_context = ""
            if notion_content:
                notion_preview = notion_content[:3000] + "..." if len(notion_content) > 3000 else notion_content
                notion_context = f"Notion Knowledge Base (use this to answer questions about the user's Notion content):\n{notion_preview}\n\n"
            
            # Create system prompt
            system_prompt = f"""You are a helpful AI assistant with access to the user's Notion workspace content. Use the following information to provide relevant and personalized responses.

{notion_context}{context}Instructions:
- Answer questions using information from the Notion content when relevant
- Reference specific pages, databases, or entries when applicable
- If asked about something not in the Notion content, use your general knowledge
- Be conversational and helpful
- Remember previous conversations for context

Current conversation:"""
            
            # Generate response
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
            
            # Add to memory
            self.add_to_memory(user_message, response, user_id)
            
            return response
            
        except Exception as e:
            return f"❌ Error generating response: {e}"
    
    def get_all_memories(self, user_id):
        """Get all memories for a user"""
        try:
            memories = self.memory.get_all(user_id=user_id, version="v2")
            user_memories = [m for m in memories if m.get("user_id") == user_id]
            return user_memories
        except Exception as e:
            st.error(f"❌ Error retrieving memories: {e}")
            return []
    
    def clear_memory(self, user_id):
        """Clear all memories for a user"""
        try:
            self.memory.delete_all(user_id=user_id)
            return True
        except Exception as e:
            st.error(f"❌ Error clearing memory: {e}")
            return False

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_notion_pages_cached(notion_token):
    """Get Notion pages with caching to avoid repeated API calls"""
    try:
        # Temporarily set the token
        original_token = os.environ.get("NOTION_TOKEN")
        os.environ["NOTION_TOKEN"] = notion_token
        
        # Import here to use the updated token
        import importlib
        if 'notion_pages' in sys.modules:
            importlib.reload(sys.modules['notion_pages'])
        
        from notion_pages import get_accessible_pages
        pages = get_accessible_pages()
        
        # Restore original token
        if original_token:
            os.environ["NOTION_TOKEN"] = original_token
        elif "NOTION_TOKEN" in os.environ:
            del os.environ["NOTION_TOKEN"]
        
        return pages, None
    
    except Exception as e:
        error_msg = f"Error fetching pages: {str(e)}"
        st.error(error_msg)
        return [], error_msg

def load_notion_content(selected_databases, selected_pages, notion_token):
    """Load content from selected Notion databases and pages"""
    content = ""
    
    try:
        # Set the notion token temporarily
        original_token = os.environ.get("NOTION_TOKEN")
        os.environ["NOTION_TOKEN"] = notion_token
        
        # Load database content
        if selected_databases and NOTION_DB_AVAILABLE:
            with st.spinner("🗃️ Loading database content..."):
                try:
                    database_content = get_all_databases_content()
                    if database_content:
                        content += "NOTION DATABASES:\n" + "="*80 + "\n" + database_content + "\n\n"
                        st.success("✅ Database content loaded")
                    else:
                        st.warning("⚠️ No database content found")
                except Exception as e:
                    st.error(f"❌ Error loading databases: {e}")
        
        # Load page content
        if selected_pages and NOTION_PAGES_AVAILABLE:
            with st.spinner(f"📄 Loading {len(selected_pages)} pages..."):
                page_content = ""
                success_count = 0
                
                for i, page in enumerate(selected_pages):
                    try:
                        st.write(f"Loading page {i+1}/{len(selected_pages)}: {page.get('title', 'Unknown')}")
                        content_data = get_page_content(page['id'])
                        if content_data:
                            page_content += f"\n{'='*80}\n"
                            page_content += f"PAGE: {content_data['title']}\n"
                            page_content += f"{'='*80}\n"
                            page_content += content_data['content'] + "\n\n"
                            success_count += 1
                        else:
                            st.warning(f"⚠️ No content found for page: {page.get('title', 'Unknown')}")
                    except Exception as e:
                        st.error(f"❌ Error loading page {page.get('title', 'Unknown')}: {e}")
                
                if page_content:
                    content += "NOTION PAGES:\n" + "="*80 + "\n" + page_content
                    st.success(f"✅ Successfully loaded {success_count}/{len(selected_pages)} pages")
                else:
                    st.warning("⚠️ No page content was loaded")
        
        # Restore original token
        if original_token:
            os.environ["NOTION_TOKEN"] = original_token
        elif "NOTION_TOKEN" in os.environ:
            del os.environ["NOTION_TOKEN"]
    
    except Exception as e:
        st.error(f"❌ Error loading Notion content: {e}")
        st.write("**Debug info:**")
        st.write(f"- Selected databases: {len(selected_databases) if selected_databases else 0}")
        st.write(f"- Selected pages: {len(selected_pages) if selected_pages else 0}")
        st.write(f"- NOTION_DB_AVAILABLE: {NOTION_DB_AVAILABLE}")
        st.write(f"- NOTION_PAGES_AVAILABLE: {NOTION_PAGES_AVAILABLE}")
        st.write(f"- Error: {str(e)}")
    
    return content

def main():
    st.set_page_config(
        page_title="Notion AI Chatbot",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🤖 Notion AI Chatbot")
    st.markdown("*Chat with your Notion content using AI with persistent memory*")
    
    # Debug section (can be removed in production)
    with st.expander("🔧 Debug Info", expanded=False):
        st.write("**Environment Status:**")
        st.write(f"- Python version: {sys.version}")
        st.write(f"- NOTION_DB_AVAILABLE: {NOTION_DB_AVAILABLE}")
        st.write(f"- NOTION_PAGES_AVAILABLE: {NOTION_PAGES_AVAILABLE}")
        st.write(f"- Current working directory: {os.getcwd()}")
        st.write(f"- Available environment variables: {[k for k in os.environ.keys() if 'API' in k or 'TOKEN' in k]}")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Get API keys from environment or user input
        groq_api_key = st.text_input(
            "🔑 Groq API Key", 
            value=os.getenv("GROQ_API_KEY", ""), 
            type="password",
            help="Get your API key from https://console.groq.com/keys"
        )
        
        mem0_api_key = st.text_input(
            "🧠 Mem0 API Key", 
            value=os.getenv("MEM0_API_KEY", ""), 
            type="password",
            help="Get your API key from https://app.mem0.ai/"
        )
        
        notion_token = st.text_input(
            "📝 Notion Token", 
            value=os.getenv("NOTION_TOKEN", ""), 
            type="password",
            help="Your Notion integration token"
        )
        
        st.divider()
        
        # User ID
        user_name = st.text_input("👤 Your Name", value="", help="Used for personalized memory management")
        
        if user_name:
            user_id = f"user_{user_name.lower().replace(' ', '_')}"
            st.success(f"✅ User ID: {user_id}")
        else:
            user_id = None
            st.warning("⚠️ Please enter your name to enable memory features")
        
        # Model selection
        model = st.selectbox("🧠 AI Model", 
                           ["llama3-8b-8192", "llama3-70b-8192", "mixtral-8x7b-32768"],
                           help="Choose the AI model for responses")
        
        st.divider()
        
        # Notion Content Selection
        st.header("📚 Notion Content")
        
        notion_content = ""
        selected_databases = []
        selected_pages = []
        
        if notion_token:
            # Test connection button
            if st.button("🧪 Test Notion Connection"):
                with st.spinner("Testing connection..."):
                    try:
                        pages, error = get_notion_pages_cached(notion_token)
                        if error:
                            st.error(f"❌ Connection failed: {error}")
                        else:
                            st.success(f"✅ Connection successful! Found {len(pages)} pages")
                    except Exception as e:
                        st.error(f"❌ Connection test failed: {e}")
            
            # Database selection
            if NOTION_DB_AVAILABLE:
                load_databases = st.checkbox("📊 Load Database Content", help="Load all accessible databases")
                if load_databases:
                    selected_databases = ['all']
            
            # Page selection with better error handling
            try:
                with st.spinner("🔍 Fetching accessible pages..."):
                    pages, error = get_notion_pages_cached(notion_token)
                
                if error:
                    st.error(f"❌ Failed to fetch pages: {error}")
                    st.write("**Troubleshooting tips:**")
                    st.write("1. Check if your Notion token is correct")
                    st.write("2. Ensure your integration has access to the pages")
                    st.write("3. Try refreshing the page")
                elif pages:
                    st.success(f"✅ Found {len(pages)} accessible pages")
                    
                    # Page selection options
                    page_selection_mode = st.radio("📄 Page Selection", 
                                                 ["None", "Select Specific Pages", "All Pages"])
                    
                    if page_selection_mode == "Select Specific Pages":
                        st.write("**Available Pages:**")
                        selected_page_indices = []
                        for i, page in enumerate(pages):
                            page_title = page.get('title', 'Untitled')[:50]
                            if st.checkbox(f"📄 {page_title}", key=f"page_{i}"):
                                selected_page_indices.append(i)
                        
                        selected_pages = [pages[i] for i in selected_page_indices]
                        
                        if selected_pages:
                            st.info(f"Selected {len(selected_pages)} pages")
                    
                    elif page_selection_mode == "All Pages":
                        selected_pages = pages
                        st.info(f"📄 All {len(pages)} pages will be loaded")
                else:
                    st.warning("⚠️ No accessible pages found. Make sure to share pages with your Notion integration.")
            
            except Exception as e:
                st.error(f"❌ Error accessing Notion: {e}")
                st.write("**Full error details:**")
                st.code(str(e))
        
        elif not notion_token:
            st.warning("⚠️ Enter Notion token to load content")
        
        # Load content button
        load_button_disabled = not (selected_databases or selected_pages) or not notion_token
        
        if st.button("🔄 Load Notion Content", disabled=load_button_disabled):
            if notion_token and (selected_databases or selected_pages):
                notion_content = load_notion_content(selected_databases, selected_pages, notion_token)
                if notion_content:
                    st.session_state['notion_content'] = notion_content
                    st.success("✅ Notion content loaded successfully!")
                    
                    # Show content summary
                    db_count = 1 if "NOTION DATABASES:" in notion_content else 0
                    page_count = notion_content.count("PAGE: ") if "NOTION PAGES:" in notion_content else 0
                    
                    st.info(f"📊 Loaded: {db_count} databases, {page_count} pages ({len(notion_content):,} characters)")
                else:
                    st.warning("⚠️ No content was loaded. Check the debug info above.")
            else:
                st.error("❌ Please provide Notion token and select content to load")
        
        st.divider()
        
        # Memory & Utils section
        st.header("🧠 Memory & Utils")
        
        if groq_api_key and mem0_api_key and user_id:
            # Initialize chatbot if not already done
            if 'chatbot' not in st.session_state:
                try:
                    st.session_state['chatbot'] = StreamlitNotionChatbot(groq_api_key, mem0_api_key)
                except Exception as e:
                    st.error(f"❌ Failed to initialize chatbot: {e}")
            
            # Show memories
            if st.button("📋 Show Memories"):
                with st.spinner("Fetching memories..."):
                    memories = st.session_state['chatbot'].get_all_memories(user_id)
                    
                    if memories:
                        st.write(f"**Found {len(memories)} memories:**")
                        
                        # Filter and display recent memories
                        displayed_count = 0
                        for i, memory in enumerate(reversed(memories)):
                            try:
                                memory_text = memory.get("memory", str(memory))
                                if memory_text and not memory_text.startswith("Notion Knowledge Base Content:"):
                                    displayed_count += 1
                                    
                                    # Create expandable section for each memory
                                    with st.expander(f"Memory {displayed_count} (Recent)", expanded=False):
                                        st.text_area(
                                            label="Content", 
                                            value=memory_text, 
                                            height=150, 
                                            disabled=True,
                                            key=f"memory_{i}_{displayed_count}"
                                        )
                                    
                                    if displayed_count >= 10:
                                        break
                            except Exception:
                                continue
                        
                        if displayed_count == 0:
                            st.info("No conversation memories found.")
                    else:
                        st.info("No memories found.")
            
            # Clear memories
            if st.button("🗑️ Clear Memories", type="secondary"):
                with st.spinner("Clearing memories..."):
                    if st.session_state['chatbot'].clear_memory(user_id):
                        st.success("✅ Memories cleared successfully!")
                        # Reload notion content to memory if available
                        if 'notion_content' in st.session_state:
                            notion_content = st.session_state['notion_content']
                            if notion_content:
                                try:
                                    messages = [{"role": "system", "content": f"Notion Knowledge Base Content:\n{notion_content}"}]
                                    st.session_state['chatbot'].memory.add(messages, user_id=user_id)
                                    st.info("🔄 Notion content reloaded to memory")
                                except Exception as e:
                                    st.error(f"Error reloading Notion content: {e}")
            
            # Clear chat
            if st.button("🔄 Clear Chat", type="secondary"):
                st.session_state.messages = []
                st.rerun()
        
        # Show loaded content summary
        if 'notion_content' in st.session_state and st.session_state['notion_content']:
            st.divider()
            st.subheader("📚 Loaded Content")
            
            content = st.session_state['notion_content']
            db_count = 1 if "NOTION DATABASES:" in content else 0
            page_count = content.count("PAGE: ") if "NOTION PAGES:" in content else 0
            
            st.metric("🗃️ Databases", db_count)
            st.metric("📄 Pages", page_count)
            st.metric("📝 Characters", f"{len(content):,}")
            
            # Show page titles
            if page_count > 0:
                with st.expander("📄 Loaded Pages"):
                    lines = content.split('\n')
                    for line in lines:
                        if line.startswith("PAGE: "):
                            page_title = line.replace("PAGE: ", "").strip()
                            st.write(f"• {page_title}")
    
    # Main chat interface
    if not groq_api_key or not mem0_api_key:
        st.warning("⚠️ Please provide both Groq and Mem0 API keys in the sidebar to start chatting.")
        return
    
    if not user_id:
        st.warning("⚠️ Please enter your name in the sidebar to enable memory features.")
        return
    
    # Initialize chatbot
    if 'chatbot' not in st.session_state:
        try:
            with st.spinner("Initializing chatbot..."):
                st.session_state['chatbot'] = StreamlitNotionChatbot(groq_api_key, mem0_api_key)
        except Exception as e:
            st.error(f"❌ Failed to initialize chatbot: {e}")
            return
    
    # Chat interface header
    st.header("💬 Chat")
    
    # Chat input
    if prompt := st.chat_input("Ask me anything about your Notion content..."):
        # Initialize chat history if not exists
        if 'messages' not in st.session_state:
            st.session_state.messages = []
        
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Generate response
        with st.spinner("🤔 Thinking..."):
            notion_content = st.session_state.get('notion_content', '')
            response = st.session_state['chatbot'].generate_response(
                prompt, user_id, notion_content, model
            )
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Display chat messages
    if 'messages' in st.session_state:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

if __name__ == "__main__":
    main()