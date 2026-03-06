import sounddevice as sd
import numpy as np
import time
from collections import deque

samplerate = 44100
blocksize = 1024

above_ms = 30
below_ms = 2000

isRecording = False
aboveStart = None
belowStart = None
recordBuffer = []

rms_window = deque(maxlen=4)

print("Measuring initial noise floor...")
noise_samples = sd.rec(int(samplerate * 1), samplerate=samplerate, channels=1, dtype='float32')
sd.wait()
noise_floor = float(np.sqrt(np.mean(noise_samples**2)))

# Initial thresholds
trigger_start = noise_floor * 2.5
trigger_stop  = noise_floor * 1.6

print(f"Initial noise floor: {noise_floor:.5f}")
print(f"Initial start threshold: {trigger_start:.5f}")
print(f"Initial stop threshold:  {trigger_stop:.5f}")
print("Listening...")

def audio_callback(indata, frames, time_info, status):
    global isRecording, aboveStart, belowStart, recordBuffer
    global noise_floor, trigger_start, trigger_stop

    rms = float(np.sqrt(np.mean(indata**2)))

    rms_window.append(rms)
    smooth_rms = sum(rms_window) / len(rms_window)

    # ============================
    # UPDATE NOISE FLOOR (only when not recording)
    # ============================
    if not isRecording and smooth_rms < trigger_start:
        noise_floor = noise_floor * 0.99 + smooth_rms * 0.01
        trigger_start = noise_floor * 2.5
        trigger_stop  = noise_floor * 1.6

    # ============================
    # FAST START DETECTION
    # ============================
    if rms >= trigger_start:
        belowStart = None

        if aboveStart is None:
            aboveStart = time.time()

        if not isRecording and (time.time() - aboveStart) * 1000 >= above_ms:
            print(">>> START RECORDING")
            isRecording = True
            recordBuffer = []

        if isRecording:
            recordBuffer.append(indata.copy())
        return

    # ============================
    # SLOW STOP DETECTION
    # ============================
    if isRecording:
        if smooth_rms <= trigger_stop:
            if belowStart is None:
                belowStart = time.time()

            if (time.time() - belowStart) * 1000 >= below_ms:
                print(">>> STOP RECORDING")
                isRecording = False

                if recordBuffer:
                    data = np.concatenate(recordBuffer, axis=0)
                    print(f">>> PLAYBACK ({len(data)/samplerate:.2f} seconds)")
                    sd.play(data, samplerate)
                    sd.wait()

                recordBuffer = []
                belowStart = None
        else:
            belowStart = None
            recordBuffer.append(indata.copy())
        return

    # ============================
    # NOT RECORDING AND NOT STARTING
    # ============================
    aboveStart = None
    belowStart = None


with sd.InputStream(callback=audio_callback,
                    channels=1,
                    samplerate=samplerate,
                    blocksize=blocksize):
    while True:
        time.sleep(0.1)
