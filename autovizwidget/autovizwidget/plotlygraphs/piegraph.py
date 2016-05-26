# Copyright (c) 2015  aggftw@gmail.com
# Distributed under the terms of the Modified BSD License.

from plotly.graph_objs import Pie, Figure, Data
from plotly.offline import iplot
from pandas.core.groupby import DataError

from autovizwidget.utils.configuration import AutoVizConfiguration


class PieGraph(object):
    @staticmethod
    def render(df, encoding, output):
        if encoding.x is None:
            with output:
                print("\n\n\nPlease select an X axis.")
                return

        try:
            values, labels = PieGraph._get_x_values_labels(df, encoding)
        except TypeError:
            with output:
                print("\n\n\nCannot group by X selection because of its type: '{}'. Please select another column."
                      .format(df[encoding.x].dtype))
                return
        except (ValueError, DataError):
            with output:
                print("\n\n\nCannot group by X selection. Please select another column."
                      .format(df[encoding.x].dtype))
                if df.size == 0:
                    print("\n\n\nCannot display a pie graph for an empty data set.")
                return

        max_slices_pie_graph = AutoVizConfiguration().max_slices_pie_graph()
        with output:
            # There's performance issues with a large amount of slices.
            # 1500 rows crash the browser.
            # 500 rows take ~15 s.
            # 100 rows is almost automatic.
            if len(values) > max_slices_pie_graph:
                print("There's {} values in your pie graph, which would render the graph unresponsive.\n"
                      "Please select another X with at most {} possible values."
                      .format(len(values), max_slices_pie_graph))
            else:
                data = [Pie(values=values, labels=labels)]

                fig = Figure(data=Data(data))
                iplot(fig, show_link=False)

    @staticmethod
    def display_logarithmic_x_axis():
        return False

    @staticmethod
    def display_logarithmic_y_axis():
        return False

    @staticmethod
    def display_x():
        return True

    @staticmethod
    def display_y():
        return False

    @staticmethod
    def _get_x_values_labels(df, encoding):
        series = df.groupby([encoding.x]).size()
        return series.values.tolist(), series.index.tolist()
