
"""
Streamlit Web Interface for Iota Chat Bot
"""

import streamlit as st
from datetime import datetime
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()


try:
    PUBLIC_NAME = os.getenv("PUBLIC_NAME", st.secrets.get("PUBLIC_NAME", "iota"))
except Exception:
    PUBLIC_NAME = os.getenv("PUBLIC_NAME", "iota")

# Import bot components
try:
    from workflow import respond_like_iota
    from retreival_topK import retrieve_topk, connect_pinecone
    from cache import response_cache
    from logging_config import logger
    
    # Try to connect to Pinecone
    index = connect_pinecone()
    
except ImportError as e:
    st.error(f"Failed to import bot components: {e}")
    st.stop()

# Page configuration
st.set_page_config(
    page_title=f"{PUBLIC_NAME} Chat Bot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .chat-message.user {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
    }
    .chat-message.bot {
        background-color: #f3e5f5;
        border-left: 4px solid #9c27b0;
    }
    .chat-message .message-content {
        font-size: 1rem;
        line-height: 1.5;
    }
    .chat-message .timestamp {
        font-size: 0.8rem;
        color: #666;
        margin-top: 0.5rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #dee2e6;
    }
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """Initialize session state variables"""
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'conversation_start' not in st.session_state:
        st.session_state.conversation_start = datetime.now()
    if 'total_messages' not in st.session_state:
        st.session_state.total_messages = 0
    if 'cache_stats' not in st.session_state:
        st.session_state.cache_stats = response_cache.get_stats()

def display_header():
    """Display the main header"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.title("🤖 Iota Chat Bot")
        st.markdown("**Your AI friend that chats just like My freind Iota!**")
        st.markdown("---")

def display_sidebar():
    """Display sidebar with controls and metrics"""
    with st.sidebar:
        st.header("🎛️ Controls")

        
        # Clear conversation button
        if st.button("🗑️ Clear Conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.conversation_start = datetime.now()
            st.session_state.total_messages = 0
            st.rerun()
        
        # Cache management
        st.subheader("💾 Cache Management")
        if st.button("🔄 Refresh Cache Stats", use_container_width=True):
            st.session_state.cache_stats = response_cache.get_stats()
            st.rerun()
        
        if st.button("🗑️ Clear Cache", use_container_width=True):
            response_cache.clear_cache()
            st.session_state.cache_stats = response_cache.get_stats()
            st.success("Cache cleared!")
            st.rerun()


        

        
        # Export cache stats
        if st.button("📊 Export Cache Stats", use_container_width=True):
            filename = f"cache_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            response_cache.export_cache_stats(filename)
            st.success(f"Stats exported to {filename}")
        
        st.markdown("---")
        
        # Performance metrics
        st.subheader("📈 Performance Metrics")
        
        # Cache stats
        cache_stats = st.session_state.cache_stats
        st.metric("Cache Entries", cache_stats.get("total_entries", 0))
        st.metric("Cache Hits", cache_stats.get("cache_hits", 0))
        st.metric("Cache Misses", cache_stats.get("cache_misses", 0))
        st.metric("Hit Rate", f"{cache_stats.get('hit_rate', 0):.1%}")
        
        # Conversation stats
        st.markdown("---")
        st.subheader("💬 Conversation Stats")
        duration = datetime.now() - st.session_state.conversation_start
        st.metric("Session Duration", f"{duration.total_seconds()/60:.1f} min")
        st.metric("Total Messages", st.session_state.total_messages)
        
        # API Status
        st.markdown("---")
        st.subheader("🔌 API Status")
        
        # Check Pinecone connection
        pinecone_status = "🟢 Connected" if index else "🔴 Disconnected"
        st.markdown(f"**Pinecone:** {pinecone_status}")
        
        # Check environment variables
        env_vars = {
    "Google API (Gemini)": os.getenv("GOOGLE_API_KEY", "Not set"),
    "HuggingFace API": os.getenv("HF_API_KEY", "Not set"),
    "Pinecone API": os.getenv("PINECONE_API_KEY", "Not set"),
    "Gemini Model": os.getenv("GEMINI_MODEL", "gemini-2.5-pro")  # display only
}

        
        for name, value in env_vars.items():
            status = "🟢 Set" if value != "Not set" else "🔴 Not set"
            st.markdown(f"**{name}:** {status}")

def display_chat_interface():
    """Display the main chat interface"""
    st.subheader("💬 Chat with Iota")
    
    # Chat input
    user_input = st.chat_input("Type your message here...")
    
    if user_input:
        # Add user message to chat
        st.session_state.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now()
        })
        st.session_state.total_messages += 1
        
        # Get bot response
        with st.spinner("Typing..."):
            try:
                # Retrieve relevant context from Pinecone
                retrieved_data = []
                if index:
                    try:
                        retrieved_docs = retrieve_topk(user_input, index, k=3)
                        retrieved_data = [
                            {
                                "score": doc.score,
                                "context": doc.context,
                                "response": doc.response
                            }
                            for doc in retrieved_docs
                        ]
                    except Exception as e:
                        st.warning(f"⚠️ Retrieval failed: {e}")
                        # Use mock data if retrieval fails
                        retrieved_data = [
                            {"score": 0.81, "context": "print ho gaya?", "response": "Haan, ho gaya. Spiral binding hi karwani hai na? ✨"},
                            {"score": 0.76, "context": "paise kitne hue?", "response": "Don't change the topic haan 😏  kal ice-cream done?"}
                        ]
                else:
                    # Use mock data if Pinecone is not available
                    retrieved_data = [
                        {"score": 0.81, "context": "print ho gaya?", "response": "Haan, ho gaya. Spiral binding hi karwani hai na? ✨"},
                        {"score": 0.76, "context": "paise kitne hue?", "response": "Don't change the topic haan 😏  kal ice-cream done?"}
                    ]

                #strip timestamp so it’s JSON-serializable and minimal
                safe_history = [{"role": m["role"], "content": m["content"]}
                        for m in st.session_state.messages]
                
                # Get bot response
                bot_response = respond_like_iota(
                    user_input,
                    safe_history,
                    retrieved_data,
                    index
                )
                
                # Add bot response to chat
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": bot_response,
                    "timestamp": datetime.now()
                })
                
                # Update cache stats
                st.session_state.cache_stats = response_cache.get_stats()
                
            except Exception as e:
                st.error(f"❌ Error: {e}")
                bot_response = "Sorry, something went wrong. Can you try again?"
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": bot_response,
                    "timestamp": datetime.now()
                })
        
        st.rerun()
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            st.caption(f"🕐 {message['timestamp'].strftime('%H:%M:%S')}")

def display_analytics():
    """Display analytics and insights"""
    st.subheader("📊 Analytics & Insights")
    
    if not st.session_state.messages:
        st.info("Start a conversation to see analytics!")
        return
    
    # Create tabs for different analytics
    tab1, tab2, tab3 = st.tabs(["📈 Message Trends", "🔍 Response Analysis", "💾 Cache Performance"])
    
    with tab1:
        # Message trends over time
        if len(st.session_state.messages) > 1:
            df = pd.DataFrame([
                {
                    'timestamp': msg['timestamp'],
                    'role': msg['role'],
                    'message_length': len(msg['content'])
                }
                for msg in st.session_state.messages
            ])
            
            # Message count by role
            role_counts = df['role'].value_counts()
            fig1 = px.pie(values=role_counts.values, names=role_counts.index, title="Message Distribution by Role")
            st.plotly_chart(fig1, use_container_width=True)
            
            # Message length over time
            fig2 = px.line(df, x='timestamp', y='message_length', color='role', 
                          title="Message Length Over Time")
            st.plotly_chart(fig2, use_container_width=True)
    
    with tab2:
        # Response analysis
        if len(st.session_state.messages) > 1:
            bot_messages = [msg for msg in st.session_state.messages if msg['role'] == 'assistant']
            
            if bot_messages:
                # Average response length
                avg_length = sum(len(msg['content']) for msg in bot_messages) / len(bot_messages)
                st.metric("Average Response Length", f"{avg_length:.1f} characters")
                
                # Response time analysis (if we had timing data)
                st.info("Response timing data would be available with enhanced logging")
                
                # Emoji usage analysis
                emoji_count = sum(1 for msg in bot_messages for char in msg['content'] if ord(char) > 127)
                st.metric("Total Emojis Used", emoji_count)
    
    with tab3:
        # Cache performance
        cache_stats = st.session_state.cache_stats
        
        # Cache hit rate chart
        fig3 = px.bar(
            x=['Cache Hits', 'Cache Misses'],
            y=[cache_stats.get('cache_hits', 0), cache_stats.get('cache_misses', 0)],
            title="Cache Performance",
            color=['Cache Hits', 'Cache Misses'],
            color_discrete_map={'Cache Hits': '#28a745', 'Cache Misses': '#dc3545'}
        )
        st.plotly_chart(fig3, use_container_width=True)
        
        # Cache efficiency
        hit_rate = cache_stats.get('hit_rate', 0)
        efficiency_color = "🟢" if hit_rate > 0.7 else "🟡" if hit_rate > 0.4 else "🔴"
        st.metric("Cache Efficiency", f"{efficiency_color} {hit_rate:.1%}")

def main():
    """Main function to run the Streamlit app"""
    initialize_session_state()
    display_header()
    
    # Create columns for layout
    col1, col2 = st.columns([3, 1])
    
    with col1:
        display_chat_interface()
        display_analytics()
    
    with col2:
        display_sidebar()

if __name__ == "__main__":
    main()
