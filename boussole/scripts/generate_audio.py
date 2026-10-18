#!/usr/bin/env python3
"""Generate WAV audio files for Boussole game.
Creates BGM tracks (cozy ambient loops) and SFX (short sound effects)."""

import wave
import struct
import math
import os

SAMPLE_RATE = 22050  # Hz
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "audio")

def write_wav(filename, samples):
    """Write a list of float samples (-1.0 to 1.0) to a WAV file."""
    path = os.path.join(OUTPUT_DIR, filename)
    with wave.open(path, 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(SAMPLE_RATE)
        data = bytearray()
        for s in samples:
            s = max(-1.0, min(1.0, s))
            data += struct.pack('<h', int(s * 32767))
        w.writeframes(bytes(data))
    print(f"  Generated {filename} ({len(samples)} samples)")

def note_freq(note_name):
    """Convert note name (e.g. 'C4', 'A#3') to frequency."""
    notes = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5,
             'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}
    if len(note_name) == 2:
        pitch, octave = note_name[0], int(note_name[1])
    else:
        pitch, octave = note_name[:2], int(note_name[2])
    midi = (octave + 1) * 12 + notes[pitch]
    return 440.0 * (2 ** ((midi - 69) / 12.0))

def sine(freq, duration, volume=0.3):
    """Generate a sine wave."""
    n = int(SAMPLE_RATE * duration)
    return [math.sin(2 * math.pi * freq * i / SAMPLE_RATE) * volume for i in range(n)]

def envelope(samples, attack=0.01, release=0.1):
    """Apply ADSR-like envelope to samples."""
    n = len(samples)
    a = int(attack * SAMPLE_RATE)
    r = int(release * SAMPLE_RATE)
    result = []
    for i in range(n):
        s = samples[i]
        if i < a:
            s *= i / max(a, 1)
        if i > n - r:
            s *= (n - i) / max(r, 1)
        result.append(s)
    return result

def generate_bgm(filename, root_note, scale_notes, bpm=80, duration_sec=12.0, mood='happy'):
    """Generate a simple looping BGM track."""
    beat = 60.0 / bpm
    total_samples = int(SAMPLE_RATE * duration_sec)
    samples = [0.0] * total_samples

    # Bass drone (root note, two octaves down)
    bass_freq = note_freq(root_note + "2")
    for i in range(total_samples):
        samples[i] += math.sin(2 * math.pi * bass_freq * i / SAMPLE_RATE) * 0.08

    # Melody — arpeggio pattern
    note_duration = beat * 0.5  # eighth notes
    melody_notes = []
    for bar in range(int(duration_sec / (beat * 4)) + 1):
        for j, scale_note in enumerate(scale_notes[:4]):
            melody_notes.append((scale_note, note_duration))
            if j == 3:
                melody_notes.append((scale_notes[0], note_duration))  # resolve back

    pos = 0
    for note_name, dur in melody_notes:
        if pos >= duration_sec:
            break
        freq = note_freq(note_name)
        n = int(SAMPLE_RATE * dur)
        for i in range(n):
            idx = int(pos * SAMPLE_RATE + i)
            if idx >= total_samples:
                break
            # Add slight vibrato
            vibrato = 1 + 0.003 * math.sin(2 * math.pi * 5 * i / SAMPLE_RATE)
            vol = 0.12
            if mood == 'calm':
                vol = 0.08
            elif mood == 'upbeat':
                vol = 0.15
            samples[idx] += math.sin(2 * math.pi * freq * vibrato * i / SAMPLE_RATE) * vol
        pos += dur

    # Add a soft pad (third harmonic)
    for i in range(total_samples):
        pad_freq = note_freq(root_note + "3")
        lfo = 0.5 + 0.5 * math.sin(2 * math.pi * 0.3 * i / SAMPLE_RATE)
        samples[i] += math.sin(2 * math.pi * pad_freq * i / SAMPLE_RATE) * 0.04 * lfo

    # Soft limiting
    for i in range(len(samples)):
        samples[i] = max(-0.6, min(0.6, samples[i]))

    write_wav(filename, samples)

def generate_sfx_click():
    """Short blip for UI clicks."""
    s = sine(880, 0.05, 0.3)
    s = envelope(s, 0.005, 0.04)
    write_wav("sfx_click.wav", s)

def generate_sfx_notify():
    """Rising two-tone for notifications."""
    s1 = sine(660, 0.08, 0.25)
    s2 = sine(880, 0.12, 0.25)
    s = envelope(s1, 0.01, 0.05) + envelope(s2, 0.01, 0.08)
    write_wav("sfx_notify.wav", s)

def generate_sfx_quest():
    """Triumphant chord for quest completion."""
    n = int(SAMPLE_RATE * 0.5)
    s = []
    for i in range(n):
        t = i / SAMPLE_RATE
        vol = 0.15 * math.exp(-t * 3)  # exponential decay
        s.append(vol * (
            math.sin(2 * math.pi * 523 * t) +  # C5
            math.sin(2 * math.pi * 659 * t) +  # E5
            math.sin(2 * math.pi * 784 * t)    # G5
        ))
    write_wav("sfx_quest.wav", s)

def generate_sfx_buy():
    """Coin sound for purchases."""
    s1 = sine(988, 0.06, 0.25)
    s2 = sine(1319, 0.1, 0.2)
    s = envelope(s1, 0.005, 0.05) + envelope(s2, 0.005, 0.08)
    write_wav("sfx_buy.wav", s)

def generate_sfx_levelup():
    """Ascending arpeggio for level up."""
    notes = ['C5', 'E5', 'G5', 'C6']
    s = []
    for note in notes:
        freq = note_freq(note)
        ns = envelope(sine(freq, 0.1, 0.25), 0.005, 0.07)
        s += ns
    write_wav("sfx_levelup.wav", s)

def generate_sfx_door():
    """Low thud for door transitions."""
    n = int(SAMPLE_RATE * 0.25)
    s = []
    for i in range(n):
        t = i / SAMPLE_RATE
        vol = 0.3 * math.exp(-t * 8)
        s.append(vol * math.sin(2 * math.pi * 120 * t) * (1 + 0.5 * math.sin(2 * math.pi * 50 * t)))
    write_wav("sfx_door.wav", s)

def generate_sfx_sleep():
    """Soft descending tone for sleep."""
    n = int(SAMPLE_RATE * 1.0)
    s = []
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = 440 - 200 * t  # pitch slides down
        vol = 0.15 * math.exp(-t * 2)
        s.append(vol * math.sin(2 * math.pi * freq * t))
    write_wav("sfx_sleep.wav", s)

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("Generating BGM tracks...")

    # Town — bright, walking-around feel (C major, upbeat)
    generate_bgm("bgm_town.wav", "C", ["C4", "E4", "G4", "B4"], bpm=100, mood='upbeat')

    # Home — warm, cozy (F major, calm)
    generate_bgm("bgm_home.wav", "F", ["F4", "A4", "C5", "E5"], bpm=70, mood='calm')

    # Tech Studio — slightly faster, modern (A minor)
    generate_bgm("bgm_tech.wav", "A", ["A4", "C5", "E5", "G5"], bpm=90, mood='happy')

    # Library — very calm, contemplative (D minor)
    generate_bgm("bgm_library.wav", "D", ["D4", "F4", "A4", "C5"], bpm=60, mood='calm')

    # Café — warm, jazzy (E flat major)
    generate_bgm("bgm_cafe.wav", "D#", ["D#4", "G4", "A#4", "D5"], bpm=85, mood='happy')

    # Art Studio — creative, flowing (G major)
    generate_bgm("bgm_art.wav", "G", ["G4", "B4", "D5", "F#5"], bpm=75, mood='happy')

    # Community Center — gentle, communal (B flat major)
    generate_bgm("bgm_community.wav", "A#", ["A#4", "D5", "F5", "A5"], bpm=80, mood='calm')

    # Menu — simple ambient (C major, very slow)
    generate_bgm("bgm_menu.wav", "C", ["C4", "E4", "G4", "C5"], bpm=50, mood='calm')

    print("\nGenerating SFX...")
    generate_sfx_click()
    generate_sfx_notify()
    generate_sfx_quest()
    generate_sfx_buy()
    generate_sfx_levelup()
    generate_sfx_door()
    generate_sfx_sleep()

    print(f"\nAll audio files generated in {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
