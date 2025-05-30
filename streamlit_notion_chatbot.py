import streamlit as st
import os
from groq import Groq
from mem0 import MemoryClient
import json
from dotenv import load_dotenv
import traceback

# Import with error handling
try:
    from notion_databases import get_all_databases_content
    NOTION_DB_AVAILABLE = True
except ImportError as e:
    st.warning(f"⚠️ notion_databases module not available: {e}")
    NOTION_DB_AVAILABLE = False

try:
    from notion_pages import get_accessible_pages, get_page_content
    NOTION_PAGES_AVAILABLE = True
except ImportError as e:
    st.warning(f"⚠️ notion_pages module not available: {e}")
    NOTION_PAGES_AVAILABLE = False

# Load environment variables
load_dotenv()

class StreamlitNotionChatbot:
    def __init__(self, groq_api_key, mem0_api_key):
        """Initialize the chatbot with API keys"""
        try:
            self.groq_client = Groq(api_key=groq_api_key)
            self.memory = MemoryClient(api_key=mem0_api_key)
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

def load_notion_content(selected_databases, selected_pages):
    """Load content from selected Notion databases and pages"""
    content = ""
    
    try:
        # Load database content
        if selected_databases and NOTION_DB_AVAILABLE:
            with st.spinner("🗃️ Loading database content..."):
                database_content = get_all_databases_content()
                if database_content:
                    content += "NOTION DATABASES:\n" + "="*80 + "\n" + database_content + "\n\n"
        
        # Load page content
        if selected_pages and NOTION_PAGES_AVAILABLE:
            with st.spinner(f"📄 Loading {len(selected_pages)} pages..."):
                page_content = ""
                for page in selected_pages:
                    try:
                        content_data = get_page_content(page['id'])
                        if content_data:
                            page_content += f"\n{'='*80}\n"
                            page_content += f"PAGE: {content_data['title']}\n"
                            page_content += f"{'='*80}\n"
                            page_content += content_data['content'] + "\n\n"
                    except Exception as e:
                        st.error(f"Error loading page {page.get('title', 'Unknown')}: {e}")
                
                if page_content:
                    content += "NOTION PAGES:\n" + "="*80 + "\n" + page_content
    
    except Exception as e:
        st.error(f"❌ Error loading Notion content: {e}")
    
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
    
    # Sidebar for configuration
    with st.sidebar:
        # Get API keys from environment
        groq_api_key = os.getenv("GROQ_API_KEY", "")
        mem0_api_key = os.getenv("MEM0_API_KEY", "")
        notion_token = os.getenv("NOTION_TOKEN", "")
        
        # Check if all required API keys are provided
        all_apis_configured = bool(groq_api_key and mem0_api_key)
        
        # Show configuration section only if APIs are not configured or user wants to see it
        if not all_apis_configured or st.checkbox("⚙️ Show API Configuration", value=not all_apis_configured):
            st.header("⚙️ Configuration")
            
            # API Keys
            groq_api_key = st.text_input("🔑 Groq API Key", 
                                       value=groq_api_key, 
                                       type="password",
                                       help="Get your API key from https://console.groq.com/keys")
            
            mem0_api_key = st.text_input("🧠 Mem0 API Key", 
                                       value=mem0_api_key, 
                                       type="password",
                                       help="Get your API key from https://app.mem0.ai/")
            
            notion_token = st.text_input("📝 Notion Token", 
                                       value=notion_token, 
                                       type="password",
                                       help="Your Notion integration token")
            
            st.divider()
        else:
            # Show compact status when APIs are configured
            st.success("✅ APIs Configured")
        
        # User ID - always show
        user_name = st.text_input("👤 Your Name", value="", help="Used for personalized memory management")
        
        if user_name:
            user_id = f"user_{user_name.lower().replace(' ', '_')}"
            st.success(f"✅ User ID: {user_id}")
        else:
            user_id = None
            st.warning("⚠️ Please enter your name to enable memory features")
        
        # Model selection - always show
        model = st.selectbox("🧠 AI Model", 
                           ["llama3-8b-8192", "llama3-70b-8192", "mixtral-8x7b-32768"],
                           help="Choose the AI model for responses")
        
        st.divider()
        
        # Notion Content Selection
        st.header("📚 Notion Content")
        
        notion_content = ""
        selected_databases = []
        selected_pages = []
        
        if notion_token and NOTION_PAGES_AVAILABLE:
            # Set the token temporarily for this session
            os.environ["NOTION_TOKEN"] = notion_token
            
            try:
                # Database selection
                if NOTION_DB_AVAILABLE:
                    load_databases = st.checkbox("📊 Load Database Content", help="Load all accessible databases")
                    if load_databases:
                        selected_databases = ['all']
                
                # Page selection
                with st.spinner("🔍 Fetching accessible pages..."):
                    pages = get_accessible_pages()
                
                if pages:
                    st.success(f"✅ Found {len(pages)} accessible pages")
                    
                    # Page selection options
                    page_selection_mode = st.radio("📄 Page Selection", 
                                                 ["None", "Select Specific Pages", "All Pages"])
                    
                    if page_selection_mode == "Select Specific Pages":
                        st.write("**Available Pages:**")
                        selected_page_indices = []
                        for i, page in enumerate(pages):
                            if st.checkbox(f"📄 {page['title'][:50]}", key=f"page_{i}"):
                                selected_page_indices.append(i)
                        
                        selected_pages = [pages[i] for i in selected_page_indices]
                    
                    elif page_selection_mode == "All Pages":
                        selected_pages = pages
                        st.info(f"📄 All {len(pages)} pages will be loaded")
            
            except Exception as e:
                st.error(f"❌ Error accessing Notion: {e}")
        
        elif not notion_token:
            st.warning("⚠️ Enter Notion token to load content")
        
        # Load content button
        if st.button("🔄 Load Notion Content", disabled=not (selected_databases or selected_pages)):
            notion_content = load_notion_content(selected_databases, selected_pages)
            if notion_content:
                st.session_state['notion_content'] = notion_content
                st.success("✅ Notion content loaded successfully!")
                
                # Show content summary
                db_count = 1 if "NOTION DATABASES:" in notion_content else 0
                page_count = notion_content.count("PAGE: ") if "NOTION PAGES:" in notion_content else 0
                
                st.info(f"📊 Loaded: {db_count} databases, {page_count} pages ({len(notion_content):,} characters)")
            else:
                st.warning("⚠️ No content was loaded")
        
        st.divider()
        
        # Memory & Utils section moved to sidebar
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
                memories = st.session_state['chatbot'].get_all_memories(user_id)
                
                if memories:
                    st.write(f"**Found {len(memories)} memories:**")
                    
                    # Filter and display recent memories with full content
                    displayed_count = 0
                    for i, memory in enumerate(reversed(memories)):
                        try:
                            memory_text = memory.get("memory", str(memory))
                            if memory_text and not memory_text.startswith("Notion Knowledge Base Content:"):
                                displayed_count += 1
                                
                                # Create expandable section for each memory
                                with st.expander(f"Memory {displayed_count} (Most Recent First)", expanded=False):
                                    st.text_area(
                                        label="Content", 
                                        value=memory_text, 
                                        height=150, 
                                        disabled=True,
                                        key=f"memory_{i}_{displayed_count}"
                                    )
                                
                                if displayed_count >= 10:  # Show more memories
                                    break
                        except Exception:
                            continue
                    
                    if displayed_count == 0:
                        st.info("No conversation memories found.")
                else:
                    st.info("No memories found.")
            
            # Clear memories
            if st.button("🗑️ Clear Memories", type="secondary"):
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
    
    # Main chat interface - now in main area
    if not groq_api_key or not mem0_api_key:
        st.warning("⚠️ Please provide both Groq and Mem0 API keys in the sidebar to start chatting.")
        return
    
    if not user_id:
        st.warning("⚠️ Please enter your name in the sidebar to enable memory features.")
        return
    
    # Initialize chatbot
    if 'chatbot' not in st.session_state:
        try:
            st.session_state['chatbot'] = StreamlitNotionChatbot(groq_api_key, mem0_api_key)
            st.success("✅ Chatbot initialized successfully!")
        except Exception as e:
            st.error(f"❌ Failed to initialize chatbot: {e}")
            return
    
    # Chat interface header
    st.header("💬 Chat")
    
    # Chat input at the top
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