import streamlit as st
import speech_recognition as sr
from moviepy.editor import VideoFileClip, AudioFileClip
import cv2
import tempfile
import os


# Function to transcribe audio with accurate timestamps
def transcribe_audio_with_timestamps(video_path):
    recognizer = sr.Recognizer()
    video = VideoFileClip(video_path)
    audio_path = "temp_audio.wav"
    video.audio.write_audiofile(audio_path)

    timestamps = []
    with sr.AudioFile(audio_path) as source:
        recognizer.adjust_for_ambient_noise(source)
        try:
            # Divide audio into 2-second chunks for better accuracy
            audio_duration = video.duration
            segment_duration = 2  # seconds
            for i in range(0, int(audio_duration), segment_duration):
                audio_segment = recognizer.record(source, duration=segment_duration)
                try:
                    transcription = recognizer.recognize_google(audio_segment)
                    timestamps.append({
                        "text": transcription,
                        "start_time": i,
                        "end_time": min(i + segment_duration, audio_duration)
                    })
                except sr.UnknownValueError:
                    # Handle cases of silence or unrecognizable audio
                    continue
        except sr.RequestError:
            timestamps.append({"text": "Error in recognition service.", "start_time": 0, "end_time": audio_duration})

    os.remove(audio_path)  # Cleanup
    return timestamps, video.duration


# Function to overlay dynamic captions with audio
def add_dynamic_captions_with_audio(video_path, timestamps):
    cap = cv2.VideoCapture(video_path)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Temp file for output
    video_output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    out = cv2.VideoWriter(video_output_path, fourcc, fps, (width, height))

    frame_count = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        current_time = frame_count / fps
        frame_count += 1

        # Find the text to display for the current frame
        text_to_display = ""
        for t in timestamps:
            if t["start_time"] <= current_time <= t["end_time"]:
                text_to_display = t["text"]
                break

        # Add text overlay
        if text_to_display:
            font = cv2.FONT_HERSHEY_DUPLEX
            font_scale = 1
            font_thickness = 2
            text_color = (255, 255, 255)  # White
            bg_color = (0, 0, 0)  # Black background (semi-transparent)

            text_size = cv2.getTextSize(text_to_display, font, font_scale, font_thickness)[0]
            text_x = (frame.shape[1] - text_size[0]) // 2
            text_y = frame.shape[0] - 50

            # Draw semi-transparent background for text
            overlay = frame.copy()
            cv2.rectangle(
                overlay,
                (text_x - 20, text_y - text_size[1] - 20),
                (text_x + text_size[0] + 20, text_y + 20),
                bg_color,
                -1,
            )
            cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

            # Draw text
            cv2.putText(frame, text_to_display, (text_x, text_y), font, font_scale, text_color, font_thickness)

        out.write(frame)

    cap.release()
    out.release()

    # Combine audio with the processed video
    output_with_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    video = VideoFileClip(video_output_path)
    original_audio = AudioFileClip(video_path)
    final_video = video.set_audio(original_audio)
    final_video.write_videofile(output_with_audio_path, codec="libx264", audio_codec="aac")

    # Cleanup intermediate video
    os.remove(video_output_path)
    return output_with_audio_path


# Streamlit Application
st.title("Improved Video Captions with Audio")
st.write("Upload a video to transcribe audio, dynamically display captions, and play/download the final video.")

# File uploader
uploaded_file = st.file_uploader("Upload your video", type=["mp4", "mov", "avi", "mkv"])

if uploaded_file is not None:
    # Save uploaded file to temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video_file:
        temp_video_file.write(uploaded_file.read())
        video_path = temp_video_file.name

    # Display uploaded video
    st.subheader("Uploaded Video")
    st.video(video_path)

    # Transcribe audio
    st.write("Transcribing audio. Please wait...")
    timestamps, duration = transcribe_audio_with_timestamps(video_path)
    st.write("Audio transcription complete.")

    # Add captions
    st.write("Processing video with accurate captions...")
    output_path = add_dynamic_captions_with_audio(video_path, timestamps)

    # Display processed video
    st.subheader("Processed Video with Captions and Audio")
    st.video(output_path)

    # Provide download link for processed video
    with open(output_path, "rb") as file:
        st.download_button(
            label="Download Video with Captions and Audio",
            data=file,
            file_name="video_with_captions_and_audio.mp4",
            mime="video/mp4",
        )

    # Clean up temporary files
    os.remove(video_path)
    os.remove(output_path)
