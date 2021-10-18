# Simple Voice Activated Dialogue System
A very simple voice activated dialogue system. At its heart, it's just a sequence to sequence transformer model, 
either BlenderBot or DialogueGPT. This was one of my pandemic projects and was mostly 
an exercise to learn how to use PyZMQ to set up a software system
with multiple processes communicating by zmq messages. 
That said, it can be used as the backbone for voice activated AIs by replacing BlenderBot with more complicated NLP or 
dialogue systems. 

This was developed in Linux. Ubuntu 18.04 to be specific. It *think* it will run on a mac if you use the appropriate Vosk installation and also
replace picotts with a mac based text to speech solution. I haven't tried this though. Windows ... you're on your own :-)

There are basically four open source technologies used:

1. Speech to Text.  I used Vosk https://alphacephei.com/vosk/ for this because it's free, runs locally and is
   reasonably accurate if you speak clearly and at a regular cadence. At least it seems that way by my ad-hoc 
   experimentation. ~~I used the vosk-model-en-us-aspire-0.2 model which takes 1.4G of space.~~ **Update 10/18/21:**
   there is now 
   a newer and much improved model vosk-model-en-us-0.22 which takes 1.8G of space. There is also a much smaller
   model, vosk-model-small-en-us-0.15 at 40M, if you want to try it.
   

2. Text to Speech. I ended up using picotts because I was developing this on my Linux box. This can be installed
   with the command "sudo apt-get install libttspico-utils" and you can choose between American and British English 
   voices. Yes, this is rather dated, but the free options on Linux are limited, and mostly even more dated (and 
   bad sounding.) So I settled on this until I found something better. 
   

3. Huggingface Transformer library. https://huggingface.co/transformers/ This is *the* library to use 
   for transformer based language models, at least if you're using PyTorch, which I was. I ended up 
   using a pretrained 400 Million parameter distillation of Facebook's 3 Billion Parameter BlenderBot.
   The model choice was basically dictated by the 8GB memory of my RTX 2070 Super GPU. I did play with a
   1B distilled version as well which (barely) fit but decided to reserve some GPU room until I can 
   get my hands on a RTX 3090. I used top-p (nucleus) decoding and not much else because after reading a bunch of papers it seems
   that top-p is a good balance of simple and effective for producing engaging dialogue. 
   
   I did experiment with Microsoft's DialogueGPT and you can use that if you like ... but the 
   pretrained model's output heavily reflected the fact that the training data was reddit and had 
   lots of emojis and ungrammatical language. To be fair, I did no fine-tuning whatsoever, so that's 
   not at all surprising and not a knock on DialogueGPT as it's not intended to be used without 
   fine-tuning. It's also occurred to me that since DialogueGPT (can) uses a truncated multi-turn 
   conversation history that there's a bit of a multi-turn memory there ... which the BART type, sequence-to-sequence
   BlenderBot doesn't naturally have. In any case, you get what you pay for, and both models are 
   surprisingly good for vanilla seq-to-seq.  
   

4. ZMQ. https://zeromq.org/ This is an amazing library for messaging between multiple processes 
   (and threads) without worrying about threadsafety or any of the other craziness that one usually 
   deals with when doing parallel processing. You can spin up multiple processes (or threads) with the
   Python multiprocessing module and then send messages between them. This library took me a little time
   to get my head around, but the documentation https://zguide.zeromq.org/ is fantastic (and 
   engaging in a way I never before saw documentation being). It did take me multiple reads and a lot
   of experimentation, but I'm glad I put the effort into learning this. 
   

# Installation

First, you'll need a microphone and a speaker. I got a simple generic $30ish usb microphone array that worked fine.
You'll need to make sure you have all the linux drivers installed to run pyaudio. That's beyond the scope of
this readme. Check the pyaudio documentation. After you have all this installed, check that your microphone and 
speaker work. It's easiest to use the ALSA commands aplay and arecord from the command line for this, although 
you can also use the sound settings gui in whatever brand of Linux you are using. 


Now clone the repo to wherever you like in your file system.


Next make a new virtual environment with your favorite python virtual environment manager. (I use virtualenvwrapper
https://virtualenvwrapper.readthedocs.io/en/latest/ but to each their own).  Note you'll need to use 
python 3.5-3.8 on Linux to run Vosk. I seem to have used Python 3.6.9. (check the Vosk site for other OSs). 


Now you need to install the following packages.


1. Vosk. Go here https://alphacephei.com/vosk/ and follow the instructions for pip installation. Then download the  
vosk-model-en-us-aspire-0.2 model and put it in the /models directory. Run the test script. If it doesn't work, 
   look at the instructions again. Vosk is fussy about exact python versions and the like.
   

2. picotts.  On linux use the command "sudo apt-get install libttspico-utils."  This is a linux command line 
   utility (not limited to your virtual environment) that allows you can write text to a .wav file using the 
   command 'pico2wave -w filename.wav -l en-GB "This is the text that I want to speak."' That's basically it
   although you can swap to an American English style voice by replacing en-GB with en-US.  There are German,
   Spanish, French and Italian voices too. It's pretty self-explanatory but here's a video that goes into a
   lot of detail https://www.youtube.com/watch?v=BijKHsvOvxc. You can easily find more by googling.
   

3. Now pip install the following python packages into your virtual environment.
   
   pyaudio  https://pypi.org/project/PyAudio/
   
   simpleaudio  https://pypi.org/project/simpleaudio/
   
   pyzmq https://pypi.org/project/pyzmq/
   
   torch  https://pytorch.org/
   
   transformers  https://huggingface.co/transformers/
   
   Everything else should be in the standard library.


That should do it.


# Running Simple Dialogue System

Assuming everything is installed correctly you should now be able to go into the src directory and type the
following in the command line:
python3 run_simple_dialogue_system.py


The system will go through an initialization process where you see a lot of output related to Vosk and transformers.
Interspersed you'll see messages that such and such module has connected all sockets and is ready to go. Eventually
it should speak to you, and you can speak to it.  If you go into the dialogue_control.py file you can manually change
the startup message, shutoff message and shutoff commands. This should be a config, but I haven't gotten around to that
yet. I did put a TODO in the code.

And that's basically it. Enjoy!  Feel free to reach out with comments and/or questions.