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

    def __init__(self, number_of_channels_to_plot, number_of_points_to_plot_per_channel, voltage_scale_n, voltage_scale_p, update_rate_ms):
        self.number_of_plots = number_of_channels_to_plot

        self.fig, self.ax = plt.subplots(self.number_of_plots, 1)
        self.lines = []

        self.number_of_points_to_plot = number_of_points_to_plot_per_channel
        self.plot_update_interval_ms = update_rate_ms

        self.channel_data = np.zeros(shape=(number_of_channels_to_plot, number_of_points_to_plot_per_channel), dtype=float)

        if self.number_of_plots == 1:
            self.lines.append(self.ax.plot(np.random.rand(self.number_of_points_to_plot)))
            self.ax.set_ylim(voltage_scale_n, voltage_scale_p)
        else:
            for i in range(self.number_of_plots):
                self.lines.append(self.ax[i].plot(np.random.rand(self.number_of_points_to_plot)))
                self.ax[i].set_ylim(voltage_scale_n, voltage_scale_p)

    def update_graph(self, data):
        for line_index, line in enumerate(self.lines):
            line[0].set_ydata(data[line_index, ::-1])
            # line[0].set_ydata(data[line_index, 0:])
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
        print("data_transfer")

        while True:

            local_channel_data = self.channel_data.copy()

            yield local_channel_data

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

    def voltage_data_sink_handler(self, voltage_channel_data: np.ndarray):
        name = "voltage_data_sink_handler"
        # print(name)

        # Have to do a deep copy so that this doesn't block
        self.channel_data = voltage_channel_data.copy()
        """
        print(voltage_channel_data[0])
        print(voltage_channel_data[1])
        print(voltage_channel_data[2])
        print(voltage_channel_data[3])

        print(voltage_channel_data[4])
        print(voltage_channel_data[5])
        print(voltage_channel_data[6])
        print(voltage_channel_data[7])
        """


def main():

    number_of_channels = 8
    number_of_samples_per_channel = 1000

    matplot_sink = MatplotSink(number_of_channels, number_of_samples_per_channel, 0, 10, 100)

    matplot_sink.show_graph()

    input("Press enter to continue...")


if __name__ == "__main__":
    main()
