from django.shortcuts import render
from django.contrib.auth import authenticate , login , logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
# Create your views here.
from django.shortcuts import render
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import SRTFormatter
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
from groq import Groq
from dotenv import load_dotenv
import os
import whisper
from django.views.decorators.csrf import csrf_exempt
from pytubefix import YouTube
from pytubefix.cli import on_progress
        

load_dotenv()
import re

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY environment variable is not set")


groq = Groq(api_key=api_key)

@login_required
def index(request):
    return render(request, 'index.html')

def login_view(request):
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')
        print(email , password)
        user = authenticate(username=email,password=password)
        if user is not None:

            login(request, user)
            return render(request, 'index.html')
        else:
            messages.error(request, 'Invalid credentials')
            return render(request, 'login.html' )    

    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return render(request, 'login.html')

def signup_view(request):
    if request.method ==  "POST":
        username  = request.POST.get('username')
        password = request.POST.get('password')
        email = request.POST.get('email')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'signup.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email Aready Exists.')
            return render(request, 'signup.html', {'error : "Email Already Exists" '})

        try:
            user =User.objects.create_user(username=username, password=password, email=email)
            user.save() 


            user = authenticate( username=username, password=password)
            login(request, user)

            return render(request, 'index.html')
        except:
            messages.error(request, 'Can Make user ')
            
    return render(request, 'signup.html')

def get_youtube_transcript(youtube_url):
    video_id = get_video_id(youtube_url)
    if not video_id:
        return "Invalid YouTube URL"
    print(video_id)
    try:
        # Fetch the transcript
        
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)


        # language_code = 'en'  # English language code
        # transcript = YouTubeTranscriptApi.get_transcript(video_id , languages=[language_code])
        # # Combine all transcript parts into a single string
        # transcript_text = "\n".join([entry['text'] for entry in transcript])
        # return transcript_text
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Select a transcript in the preferred languages (e.g., English, Urdu)
        preferred_languages = ['en', 'ur']
        transcript = transcript_list.find_transcript(preferred_languages)

        # Fetch the transcript
        transcript_data = transcript.fetch()
        combined_text = " ".join([entry['text'] for entry in transcript_data])

        print(combined_text)
        return combined_text
    except Exception as e:
        print( f"EXCCCCCCCCCCCCCCCCCCCCCCCCCCCAn error occurred: {e}")

        model = whisper.load_model("base")
        
        
        yt = YouTube(youtube_url, on_progress_callback = on_progress)
        print(yt.title)

        ys = yt.streams.get_audio_only()
        ys.download(filename="1" , mp3=True)
        result = model.transcribe("1.mp3")
        os.remove("1.mp3")
        print(result['text'])
        return result['text']

def get_video_id(youtube_url):
    parsed_url = urlparse(youtube_url)
    
    if 'youtu.be' in parsed_url.netloc:
        path_parts = parsed_url.path.split('/')
        return path_parts[1] if len(path_parts) > 1 else None

    # Handle full YouTube URLs (youtube.com)
    if 'youtube.com' in parsed_url.netloc:
        video_id = parse_qs(parsed_url.query).get('v')
        return video_id[0] if video_id else None

def split_transcript(transcript: str, max_length: int):
    """Splits the transcript into chunks based on the max_length."""
    words = transcript.split()
    chunks = []
    current_chunk = []

    for word in words:
        if len(" ".join(current_chunk + [word])) > max_length:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
        else:
            current_chunk.append(word)
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks

def generate_article_from_transcript(transcript: str, max_tokens: int = 5000):
    transcript_chunks = split_transcript(transcript, max_tokens)
    full_article = ""

    for chunk in transcript_chunks:
        chat_completion = groq.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI assistant designed to generate comprehensive articles based on transcripts. The articles should be well-structured, "
                        "informative, and should maintain a consistent tone. Use the provided transcript to craft an article, ensuring that it includes "
                        "an introduction, key points from the transcript, and a conclusion. Summarize and organize the content to make it engaging and coherent."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Here is a part of a transcript of a YouTube video. Please write an Summarized article based on this transcript :\n\n{chunk}",
                },
            ],
            model="mixtral-8x7b-32768",
            stream=False,
        )
        full_article += chat_completion.choices[0].message.content + "\n\n"

    return full_article    


@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            youtube_url = request.POST.get('youtube_link')
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid data sent'}, status=400)

        
        
        # youtube_url = request.POST.get('youtube_link')
        print("xxxxxxxxxxxx" ,youtube_url)

        video_id = get_video_id(youtube_url)
        print(video_id)
        if not video_id:
            return render(request, 'index.html', {'error': 'Invalid YouTube URL'})

        try:
            # Fetch the transcript
            transcript = get_youtube_transcript(youtube_url)            
            article_content = generate_article_from_transcript(transcript)
            clean_transcript = process_transcript(article_content)
            return render(request, 'article.html', {'article': clean_transcript})

        except Exception as e:
            
            print(str(e))
            return render(request, 'index.html', {'error': str(e)})

    return render(request, 'index.html')

def process_transcript(transcript):
    """
    Process and clean the transcript to generate article content.
    """
    # Remove timestamps and additional formatting
    cleaned_transcript = re.sub(r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n', '', transcript)
    cleaned_transcript = re.sub(r'\n+', '\n', cleaned_transcript)
    cleaned_transcript = cleaned_transcript.strip()

    # You can further enhance processing here if needed
    return cleaned_transcript
