# https://matplotlib.org/examples/animation/basic_example.html
"""
===========
Random data
===========

An animation of random data.

"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import math
import random

number_of_plots = 4
# fig, ax = plt.subplots()
fig, ax = plt.subplots(number_of_plots, 1)

lines = []
for i in range(number_of_plots):
    a = math.pi / 6
    lines.append(ax[i].plot(np.random.rand(100)))
    ax[i].set_ylim(0, 1)


def update(data):

    for line_index, line in enumerate(lines):
        line[0].set_ydata(data[line_index, 0:])

    return lines


def data_gen():
    a = math.pi / 6
    number_of_channels = 4
    number_of_samples_per_frame = 100
    # data = [[0 for x in range(buffer_size)] for y in range(number_of_channels)]
    sin_count = 0

    print("data_gen()")

    while True:

        channel_data = np.zeros(shape=(number_of_channels, number_of_samples_per_frame), dtype=float)

        for channel_index in range(number_of_channels):
            for value_index in range(number_of_samples_per_frame):
                value = math.sin(a + value_index + channel_index) + random.uniform(0.0, 0.1)
                channel_data[channel_index][value_index] = (value + 1.0) * 0.5

        yield channel_data


ani = animation.FuncAnimation(fig, update, data_gen, interval=100)
plt.show()

input("Press enter to continue...")
