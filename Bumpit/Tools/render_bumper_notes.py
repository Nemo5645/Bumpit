"""Render the original 16-hit bumper audition as a mono PCM master for UE import."""
import math
import random
import struct
import wave
from pathlib import Path

RATE = 44100
DURATION = .22
NOTES = (None, 55, 58, 60, 62, 65, 67, 69, 70, 72, 74, 75, 77, 79, 81, 82)
# Sample offsets are shared with the importer so even the last tail stays intact.
STARTS = [round(RATE * (.12 + .37 * i - .004 * i * (i - 1))) for i in range(len(NOTES))]


def strike(index, midi):
    rng = random.Random(190 + index)
    samples = []
    # Three resonances model a small steel plate struck against a wooden cabinet.
    modes = [(760, .013, .43), (1640, .023, .34), (2930, .009, .22)]
    plate = [0.0] * len(modes)
    previous = [0.0] * len(modes)
    poles = []
    for hz, decay, _ in modes:
        radius = math.exp(-1 / (RATE * decay))
        poles.append((2 * radius * math.cos(math.tau * hz / RATE), radius ** 2))
    strength = index / (len(NOTES) - 1)
    accent = index in (3, 7, 11, 15)
    for frame in range(round(DURATION * RATE)):
        t = frame / RATE
        # The return stroke lands a few milliseconds behind the initial contact.
        rebound = max(0, t - .012)
        noise = rng.uniform(-1, 1)
        impulse = noise * (math.exp(-t / .0028) +
                           (.48 * math.exp(-rebound / .0022) if t >= .012 else 0))
        clang = 0
        for mode, (_, _, level) in enumerate(modes):
            feedback, damping = poles[mode]
            new = impulse + feedback * plate[mode] - damping * previous[mode]
            previous[mode], plate[mode] = plate[mode], new
            clang += level * math.tanh(new * .44)
        phase = math.tau * (82 * t + 2.65 * (1 - math.exp(-t / .009)))
        body = math.tanh(2.3 * math.sin(phase)) * math.exp(-t / .045)
        sample = .94 * body + (.80 + .25 * strength) * clang + .26 * impulse
        if midi is not None and t > .009:
            u = t - .009
            angle = math.tau * 440 * 2 ** ((midi - 69) / 12) * u
            # Brief FM bite settles into a narrow, buzzy pitched tail.
            bite = math.sin(angle + (2.2 + strength) * math.exp(-u / .016) * math.sin(2 * angle))
            pulse = math.tanh(2.6 * (bite + .37 * math.sin(2 * angle)))
            sample += (.55 + .22 * strength) * pulse * math.exp(-u / .047) * min(1, u / .001)
        if accent and t >= .030:
            u = t - .030
            pawl = math.sin(math.tau * 413 * u) + .6 * math.sin(math.tau * 1753 * u)
            sample += .62 * math.tanh(2 * pawl) * math.exp(-u / .014) * min(1, u / .0008)
        edge = min(1, t / .00035, (DURATION - t) / .012)
        samples.append(round(31000 * edge * math.tanh(1.65 * sample)))
    return samples


if __name__ == '__main__':
    master = [0] * (STARTS[-1] + round(RATE * (DURATION + .12)))
    for index, note in enumerate(NOTES):
        hit = strike(index, note)
        master[STARTS[index]:STARTS[index] + len(hit)] = hit
    out = Path(__file__).resolve().parents[1] / 'AudioPreviews' / 'bumper_chain_16.wav'
    with wave.open(str(out), 'wb') as audio:
        audio.setparams((1, 2, RATE, 0, 'NONE', ''))
        audio.writeframes(struct.pack(f'<{len(master)}h', *master))
