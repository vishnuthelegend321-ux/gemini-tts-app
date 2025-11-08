import streamlit as st
import struct
import re
import io
import asyncio  # NEW: Required for edge-tts
from pydub import AudioSegment
import edge_tts  # NEW: The Edge TTS library

# --- Constants ---
# We can use a slightly larger chunk limit for Edge TTS
CHUNK_CHARACTER_LIMIT = 7000
# We must specify a voice. You can find more at `edge-tts --list-voices`
VOICE = "en-US-EricNeural"

# --- Your original text chunker function (UNMODIFIED) ---
def smart_text_chunker(text: str, max_length: int):
    chunks = []
    current_chunk = ""
    paragraphs = text.split('\n\n')
    
    for i, paragraph in enumerate(paragraphs):
        if len(current_chunk) + len(paragraph) + 2 > max_length:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            
            if len(paragraph) > max_length:
                sentences = re.split(r'(?<=[.!?])\s+', paragraph)
                sentence_chunk = ""
                for sentence in sentences:
                    if len(sentence_chunk) + len(sentence) + 1 > max_length:
                        if sentence_chunk.strip():
                            chunks.append(sentence_chunk.strip())
                        sentence_chunk = sentence
                    else:
                        sentence_chunk += sentence + " "
                
                if sentence_chunk.strip():
                    chunks.append(sentence_chunk.strip())
            
            else:
                current_chunk = paragraph
        
        else:
            current_chunk += paragraph + "\n\n"

    if current_chunk.strip():
        chunks.append(current_chunk.strip())
        
    return chunks

# --- NEW: Helper for a *Single* Edge TTS API Call ---
async def _generate_audio_chunk_edge(text_chunk: str) -> bytes | None:
    """
    Calls the Edge TTS API for a single chunk of text and returns MP3 data.
    """
    try:
        communicate = edge_tts.Communicate(text_chunk, VOICE)
        audio_buffer = io.BytesIO()
        
        # This streams the MP3 data into our in-memory buffer
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])
        
        audio_buffer.seek(0)
        return audio_buffer.getvalue()
        
    except Exception as e:
        st.error(f"Error generating audio for chunk: {e}")
        return None

# --- NEW: Main Function to Handle Long Text (for Edge TTS) ---
def generate_long_form_audio_edge(input_text: str):
    """
    Generates audio from long text by chunking, generating, and stitching.
    Returns final audio as WAV data bytes.
    """
    
    st.info("Step 1/3: Chunking long text...")
    text_chunks = smart_text_chunker(input_text, CHUNK_CHARACTER_LIMIT)
    st.write(f"Input text was split into {len(text_chunks)} chunks.")
    
    st.info("Step 2/3: Generating audio for each chunk... (This may take a while)")
    audio_chunks = []
    
    progress_bar = st.progress(0)
    
    for i, chunk in enumerate(text_chunks):
        st.write(f"Generating chunk {i+1}/{len(text_chunks)}...")
        
        # We must use asyncio.run() to call the async function
        mp3_data = asyncio.run(_generate_audio_chunk_edge(chunk))
        
        if mp3_data:
            # Load the MP3 data from memory into pydub
            audio_segment = AudioSegment.from_file(io.BytesIO(mp3_data), format="mp3")
            audio_chunks.append(audio_segment)
        else:
            st.warning(f"Skipping chunk {i+1} as audio generation failed.")
        
        progress_bar.progress((i + 1) / len(text_chunks))

    if not audio_chunks:
        st.error("No audio was generated. Please check your text.")
        return None

    st.info("Step 3/3: Stitching audio chunks together...")
    
    final_audio = audio_chunks[0]
    for audio_segment in audio_chunks[1:]:
        final_audio += audio_segment

    # Export as WAV (st.audio works best with WAV)
    final_audio_buffer = io.BytesIO()
    final_audio.export(final_audio_buffer, format="wav")
    
    st.success("Audio processing complete!")
    
    return final_audio_buffer.getvalue()
