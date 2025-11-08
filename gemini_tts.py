import streamlit as st
from google import genai
from google.genai import types
import struct
from pydub import AudioSegment
import io # NEW: Needed to handle audio data in memory

# --- Constants ---
# SET THE API'S PER-REQUEST CHARACTER LIMIT HERE
# We'll set it to 4000 as a safe guess. You can adjust this if you find the real limit.
CHUNK_CHARACTER_LIMIT = 4000

# (Your convert_to_wav and parse_audio_mime_type functions remain the same)
# ...
def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Generates a WAV file header for the given audio data and parameters."""
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", chunk_size, b"WAVE", b"fmt ",
        16, 1, num_channels, sample_rate,
        byte_rate, block_align, bits_per_sample,
        b"data", data_size
    )
    return header + audio_data

def parse_audio_mime_type(mime_type: str) -> dict[str, int | None]:
    """Parses bits per sample and rate from an audio MIME type string."""
    bits_per_sample = 16
    rate = 24000
    parts = mime_type.split(";")
    for param in parts:
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate_str = param.split("=", 1)[1]
                rate = int(rate_str)
            except (ValueError, IndexError):
                pass
        elif param.startswith("audio/L"):
            try:
                bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError):
                pass
    return {"bits_per_sample": bits_per_sample, "rate": rate}
# ...


# --- NEW: Text Chunker Function ---
def smart_text_chunker(text: str, max_length: int):
    """
    Splits text into chunks at the last paragraph or sentence break 
    before the max_length.
    """
    chunks = []
    current_chunk = ""
    
    # First, split by paragraphs (our most preferred break)
    paragraphs = text.split('\n\n')
    
    for i, paragraph in enumerate(paragraphs):
        # If adding the next paragraph (plus a newline) exceeds the limit
        if len(current_chunk) + len(paragraph) + 2 > max_length:
            # If the current chunk is not empty, add it to the list
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            
            # Now, handle the paragraph that was too long
            # If the paragraph *itself* is too long, split it by sentences
            if len(paragraph) > max_length:
                sentences = re.split(r'(?<=[.!?])\s+', paragraph)
                sentence_chunk = ""
                for sentence in sentences:
                    if len(sentence_chunk) + len(sentence) + 1 > max_length:
                        if sentence_chunk.strip():
                            chunks.append(sentence_chunk.strip())
                        sentence_chunk = sentence # Start new chunk with this sentence
                    else:
                        sentence_chunk += sentence + " "
                
                # Add the last sentence chunk
                if sentence_chunk.strip():
                    chunks.append(sentence_chunk.strip())
            
            # Otherwise, the paragraph was just too big to *add*
            # so it becomes the start of the *next* chunk.
            else:
                current_chunk = paragraph
        
        # Otherwise, add the paragraph to the current chunk
        else:
            current_chunk += paragraph + "\n\n"
            
        # Add a newline between paragraphs, but not after the last one
        # if i < len(paragraphs) - 1:
        #     current_chunk += "\n\n"

    # Add the last remaining chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
        
    return chunks


# --- NEW: Helper for a *Single* API Call ---
def _generate_audio_chunk(text_chunk: str, client: genai.Client) -> bytes | None:
    """
    Calls the Gemini API for a single chunk of text and returns raw WAV data.
    """
    model = "gemini-2.5-pro-preview-tts"
    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=text_chunk)],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        response_modalities=["audio"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Enceladus"
                )
            )
        ),
    )

    try:
        # We only need the first audio chunk from the stream
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            if (chunk.candidates and chunk.candidates[0].content and 
                chunk.candidates[0].content.parts and 
                chunk.candidates[0].content.parts[0].inline_data and 
                chunk.candidates[0].content.parts[0].inline_data.data):
                
                inline_data = chunk.candidates[0].content.parts[0].inline_data
                # Convert the raw audio data to a valid WAV
                wav_data = convert_to_wav(inline_data.data, inline_data.mime_type)
                return wav_data
            
    except Exception as e:
        st.error(f"Error generating audio for chunk: {e}")
        return None
    
    return None


# --- NEW: Main Function to Handle Long Text ---
def generate_long_form_audio(input_text: str):
    """
    Generates audio from long text by chunking, generating, and stitching.
    Returns final audio as WAV data bytes.
    """
    try:
        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    except Exception as e:
        st.error(f"Error initializing Gemini client: {e}")
        return None

    # 1. Chunk the text
    st.info("Step 1/3: Chunking long text...")
    text_chunks = smart_text_chunker(input_text, CHUNK_CHARACTER_LIMIT)
    st.write(f"Input text was split into {len(text_chunks)} chunks.")
    
    # 2. Loop and Generate Audio for each chunk
    st.info("Step 2/3: Generating audio for each chunk... (This may take a while)")
    audio_chunks = []
    
    # Use st.progress to show detailed progress
    progress_bar = st.progress(0)
    
    for i, chunk in enumerate(text_chunks):
        st.write(f"Generating chunk {i+1}/{len(text_chunks)}...")
        wav_data = _generate_audio_chunk(chunk, client)
        
        if wav_data:
            # Load the WAV data into pydub from memory
            audio_segment = AudioSegment.from_file(io.BytesIO(wav_data), format="wav")
            audio_chunks.append(audio_segment)
        else:
            st.warning(f"Skipping chunk {i+1} as audio generation failed.")
        
        # Update progress bar
        progress_bar.progress((i + 1) / len(text_chunks))

    # 3. Stitch the audio
    if not audio_chunks:
        st.error("No audio was generated. Please check your text or API key.")
        return None

    st.info("Step 3/3: Stitching audio chunks together...")
    
    # Start with the first chunk
    final_audio = audio_chunks[0]
    
    # Add the rest of the chunks
    for audio_segment in audio_chunks[1:]:
        final_audio += audio_segment

    # Export the final audio to a bytes buffer in WAV format
    final_audio_buffer = io.BytesIO()
    final_audio.export(final_audio_buffer, format="wav")
    
    st.success("Audio processing complete!")
    
    return final_audio_buffer.getvalue()
