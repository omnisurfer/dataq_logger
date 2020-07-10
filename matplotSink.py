"""
Matplot example this is derived from
- https://matplotlib.org/examples/animation/basic_example.html

"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import math
import random

"""
number_of_plots = 4
fig, ax = plt.subplots(number_of_plots, 1)

lines = []


def setup_graphs():
    # sets up how many lines are present
    for i in range(number_of_plots):
        a = math.pi / 6
        lines.append(ax[i].plot(np.random.rand(100)))
        ax[i].set_ylim(0, 1)


def update_graph(data):
    for line_index, line in enumerate(lines):
        line[0].set_ydata(data[line_index, 0:])

    return lines


def data_gen():
    a = math.pi / 6
    number_of_channels = 4
    number_of_samples_per_frame = 100

    print("data_gen()")

    while True:

        channel_data = np.zeros(shape=(number_of_channels, number_of_samples_per_frame), dtype=float)

        for channel_index in range(number_of_channels):
            for value_index in range(number_of_samples_per_frame):
                value = math.sin(a + value_index + channel_index) + random.uniform(0.0, 0.1)
                channel_data[channel_index][value_index] = (value + 1.0) * 0.5

        yield channel_data
"""


class MatplotSink:

    def __init__(self, number_of_channels_to_plot):
        self.number_of_plots = number_of_channels_to_plot

        self.fig, self.ax = plt.subplots(self.number_of_plots, 1)
        self.lines = []

        self.number_of_points_to_plot = 100

        for i in range(self.number_of_plots):
            self.lines.append(self.ax[i].plot(np.random.rand(self.number_of_points_to_plot)))
            self.ax[i].set_ylim(0, 1)

    def update_graph(self, data):
        for line_index, line in enumerate(self.lines):
            line[0].set_ydata(data[line_index, 0:])

        return self.lines

    def data_gen(self):
        phase_offset = math.pi / 2
        number_of_channels = self.number_of_plots
        number_of_samples_per_frame = self.number_of_points_to_plot

        demo_freq_hz = 10
        demo_rad_s = 2 * math.pi * demo_freq_hz

        print("data_gen()")

        while True:

            channel_data = np.zeros(shape=(number_of_channels, number_of_samples_per_frame), dtype=float)

            for channel_index in range(number_of_channels):
                for sample_index in range(number_of_samples_per_frame):
                    # (phase_offset + sample_index + channel_index) * 0.25
                    value = math.sin(demo_freq_hz * (sample_index/number_of_samples_per_frame)) + random.uniform(0.0, 0.1)
                    channel_data[channel_index][sample_index] = (value + 1.0) * 0.5

            yield channel_data

    def show_graph(self):
        ani = animation.FuncAnimation(self.fig, self.update_graph, self.data_gen, interval=10)
        # execution freezes here
        plt.show()


def main():

    """
    setup_graphs()

    ani = animation.FuncAnimation(fig, update_graph, data_gen, interval=100)
    # execution freezes here
    plt.show()
    """

    matplot_sink = MatplotSink(4)

    matplot_sink.show_graph()

    input("Press enter to continue...")


if __name__ == "__main__":
    main()
