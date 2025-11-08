import streamlit as st
# Import the *new* main function from your utility file
from gemini_tts import generate_long_form_audio 

# --- Page Configuration ---
st.set_page_config(
    page_title="Gemini Long-Form TTS",
    page_icon="🔉"
)

st.title("🔉 Gemini Long-Form Text-to-Speech")
st.caption("A web app to generate audio from long-form text using Gemini and Pydub.")

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
    elif "GEMINI_API_KEY" not in st.secrets:
        st.error("GEMINI_API_KEY not found. Please add it to your Streamlit secrets.")
    else:
        # Call the new function. All the logic is hidden in gemini_tts.py
        wav_data = generate_long_form_audio(text_input)
        
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
