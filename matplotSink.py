"""
Matplot example this is derived from
- https://matplotlib.org/examples/animation/basic_example.html

"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import math
import random
import time


class MatplotSink:

    def __init__(self, number_of_channels_to_plot, number_of_points_to_plot):
        self.number_of_plots = number_of_channels_to_plot

        self.fig, self.ax = plt.subplots(self.number_of_plots, 1)
        self.lines = []

        self.number_of_points_to_plot = number_of_points_to_plot
        self.plot_update_interval_ms = 100

        for i in range(self.number_of_plots):
            self.lines.append(self.ax[i].plot(np.random.rand(self.number_of_points_to_plot)))
            self.ax[i].set_ylim(0, 1)

    def update_graph(self, data):
        for line_index, line in enumerate(self.lines):
            line[0].set_ydata(data[line_index, 0:])

        return self.lines

    def data_gen_demo(self):
        phase_offset = math.pi / 2

        demo_freq_hz = 10
        demo_rad_s = 2 * math.pi * demo_freq_hz

        print("data_gen()")

        while True:

            channel_data = np.zeros(shape=(self.number_of_plots, self.number_of_points_to_plot), dtype=float)

            for channel_index in range(self.number_of_plots):
                for sample_index in range(self.number_of_points_to_plot):
                    value = math.sin(demo_freq_hz * (sample_index/self.number_of_points_to_plot)) + random.uniform(0.0, 0.1)
                    channel_data[channel_index][sample_index] = (value + 1.0) * 0.5

            yield channel_data

    def data_transfer(self):
        phase_offset = math.pi / 2

        demo_freq_hz = 10
        demo_rad_s = 2 * math.pi * demo_freq_hz

        samples_this_frame = 500

        while True:
            channel_data = np.zeros(shape=(self.number_of_plots, self.number_of_points_to_plot), dtype=float)

            for channel_index in range(self.number_of_plots):
                for sample_index in range(self.number_of_points_to_plot - samples_this_frame):
                    value = math.sin(demo_freq_hz * (sample_index/self.number_of_points_to_plot)) + random.uniform(0.0, 0.1)
                    channel_data[channel_index][sample_index] = (value + 1.0) * 0.5

            yield channel_data

    def show_graph(self):
        ani = animation.FuncAnimation(self.fig, self.update_graph, self.data_transfer, interval=self.plot_update_interval_ms)
        # execution freezes here
        plt.show()

    def get_number_of_channels_plots(self):
        return self.number_of_plots

    def get_number_of_points_to_plot(self):
        return self.number_of_points_to_plot

    def get_plot_update_intervale_ms(self):
        return self.plot_update_interval_ms

    def voltage_data_sink(self):
        print("does nothing...")


def main():

    matplot_sink = MatplotSink(8, 1000)

    matplot_sink.show_graph()

    input("Press enter to continue...")


if __name__ == "__main__":
    main()
