import streamlit as st
# Import the *new* main function from your utility file
from tts_logic import generate_long_form_audio_edge 

# --- Page Configuration ---
st.set_page_config(
    page_title="Edge Long-Form TTS",
    page_icon="🔉"
)

st.title("🔉 Edge Long-Form Text-to-Speech")
st.caption("A web app to generate audio from long-form text using Edge TTS and Pydub.")

# --- Text Input ---
text_input = st.text_area("Enter your long-form text to convert to speech:", 
                          value="""Here is the first paragraph. This demonstrates a short text.

And here is a second paragraph, separated by a line break. The app should process these and stitch them together seamlessly.
""",
                          height=250)

# --- Generate Button ---
if st.button("Generate Long-Form Audio"):
    if not text_input:
        st.warning("Please enter some text to generate audio.")
    
    # NOTE: We no longer need the API key check!
    # Edge TTS is free and doesn't require a key.
    
    else:
        # Call the new function. All the logic is hidden in tts_logic.py
        wav_data = generate_long_form_audio_edge(text_input)
        
        if wav_data:
            # Display the final, stitched audio player
            st.audio(wav_data, format="audio/wav")
            
            # Add a download button for the final file
            st.download_button(
                label="Download Full WAV",
                data=wav_data,
                file_name="generated_long_audio.wav",
                mime="audio/wav"
            )
