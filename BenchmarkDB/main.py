"""
DB Benchmarking Application
===========================

Main.py

This file houses the core of the application, and is where all of the
read/write commands are issued from, timed, and all data is analyzed.  Results
from the trials are printed to the console by default, and are also printed to
a markdown file to keep a record of.  This is particularly helpful when
benchmarking multiple DB's in a row to see which one is fastest for deployment
purposes.

    Usage:
        main.py <database> [options]
        main.py --debug [options]
        main.py --list
        main.py <database> <report_title> [options]

    Options:
        -h --help           Show this help screen
        -v                  Show verbose output from the application
        -V                  Show REALLY verbose output, including the time
                                from each run
        -s                  Sleep mode (experimental) - sleeps for 1/20 (s)
                                between each read and write
        -c --chaos          Activates CHAOS mode, where reads are taken
                                randomly from the DB instead of sequentially
        -l --list           Outputs a list of available DB modules
        --csv               Records unaltered read and write data to a CSV file
                                for your own analysis
        --no-report         Option to disable the creation of the report file
        --no-split          Alternate between reads and writes instead of all
                                writes before reads
        --debug             Generates a random dataset instead of actually
                                connecting to a DB
        --length=<n>        Specify an entry length for reads/writes
                                [default: 10]
        --trials=<n>        Specify the number of reads and writes to make to
                                the DB to collect data on [default: 1000]
"""
from __future__ import absolute_import
from __future__ import print_function

# TODO [x] - add a progress bar for non-verbose output
# TODO [x] - add some better data analysis
# TODO [ ] - add python 3.x support
# TODO [ ] - remove outlier table from report and add system parameter table

import time
import string
import random
import importlib
import pylab
import ipdb
import seaborn
import pandas as pd
import numpy as np

from os import getcwd, listdir, makedirs
from sys import exit
from tabulate import tabulate
from docopt import docopt
from clint.textui import progress
import six
from six.moves import range


def retrieve_module_list():
    """ This function will retrieve a list of all available modules in the
    project directory and then return said list.

    :return mod_list: The list of modules in the project directory

    """

    current_dir = getcwd()
    mod_list = []

    for item in listdir(current_dir):

        if item.endswith('db'):

            mod_list.append(item)

    return mod_list


class Benchmark():

    def __init__(self):
        """

        """

        if options.get('--list'):

            self.__print_module_list()

        self.collection = 'test'

        # Retrieve command line options
        self.verbose = options.get('-v')
        self.really_verbose = options.get('-V')
        self.entry_length = int(options.get('--length'))
        self.trials = int(options.get('--trials'))
        self.no_report = options.get('--no-report')
        self.chaos = options.get('--chaos')
        self.csv = options.get('--csv')
        self.report_title = options.get('<report_title>')

        if options.get('--no-split'):

            self.split = False

        else:

            self.split = True

        self.write_times = []
        self.read_times = []

        self.time_and_date = time.strftime("%a, %d %b, %Y at %H:%M:%S")
        self.report_date = time.strftime("%b%d-%Y--%H-%M")

        if options.get('--debug'):

            self.feaux_run()

        else:

            self.db_name = options.get('<database>')

            self.module = self.__register_module(self.db_name)
            self.database_client = self.module.main.Benchmark(
                self.collection, setup=True, trials=self.trials
            )

            module_settings = self.module.local
            self.number_of_nodes = module_settings.NUMBER_OF_NODES

            self.db_name = self.db_name.replace('db', '').upper()

            # Run the benchmarks!
            if self.split:

                self.run_split()

            else:

                self.run()

        if not self.report_title:

            self.report_title = '{db}-{date}'.format(
                db=self.db_name,
                date=self.report_date,
            )

        self.reports_dir = 'generated_reports/{title}'.format(
            title=self.report_title,
            )
        makedirs(self.reports_dir)

        self.images_dir = self.reports_dir + '/images'
        makedirs(self.images_dir)

        data = self.compile_data()

        report_data = self.generate_report_data(data)

        self.generate_report(report_data)

    def feaux_run(self):
        """ This function generates fake data to be used for testing purposes.
        """

        self.number_of_nodes = 'n/a'
        self.db_name = 'feaux_db'

        r = np.random.normal(0.004, 0.001, self.trials)
        self.read_times = r.tolist()

        w = np.random.normal(0.005, 0.0015, self.trials)
        self.write_times = w.tolist()

        for i in progress.bar(list(range(self.trials))):

            pass

    def random_entry(self):
        """ This function generates a random string or random number depending
        on the arguments passed in.  The string is generated from all ascii
        letters and the number is generated from numbers 0-9.

        :param entry_type: the specified type of random entry, either 'string'
                    or 'number'

        :return: the random string or number that was just generated
        """

        entry = dict()

        entry_fields = {
            'Number': string.digits,
            'Info': string.ascii_letters,
        }

        for field, selection in entry_fields.items():

            field_val = None

            for x in range(self.entry_length):

                field_val += random.choice(selection)

            entry[field] = field_val

        return entry

    def run(self):
        """ This function will keep track of and call the read/ write functions
        for benchmarking.  For each iteration, a new DB entry will be created,
        written to the DB,  and then read back from it.

        """
        if self.chaos:

            msg = 'Error! Chaos mode can ONLY be used with split reads/writes!'
            exit(msg)

        for index in progress.bar(list(range(self.trials))):

            entry = self.random_entry()

            self.write(entry)

            if self.chaos:
                index = random.randint(0, index)

            if options.get('-s'):
                time.sleep(1/20)

            self.read(index)

    def run_split(self):
        """ This function performs the same actions as 'run()', with the key
        exception that this splits reads and writes into two separate runs,
        instead of alternating reads and writes.
        """

        print('\nWrite progress:\n')

        for index in progress.bar(list(range(self.trials))):

            entry = self.random_entry()

            self.write(entry)

            if options.get('-s'):
                time.sleep(1/20)

        print('\nRead progress:\n')

        for index in progress.bar(list(range(self.trials))):

            if self.chaos:
                index = random.randint(0, index)

            self.read(index)

            if options.get('-s'):
                time.sleep(1/20)

    def write(self, entry):
        """ This function handles all DB write commands, and times that action
        as well.  It takes a single parameter ('entry'), which is the data to
        be written to the DB.

        :param entry: The entry to be recorded to the DB

        :return: True, if all operations successfully completed
        """

        write_start_time = time.time()

        self.database_client.write(entry)

        write_stop_time = time.time()

        write_time = write_stop_time - write_start_time

        self.write_times.append(write_time)

        if self.really_verbose:

            write_msg = 'Write time: {time}'.format(time=write_time)

            print(write_msg)

    def read(self, index):
        """ This function handles all DB read commands, and times that action
        as well.  It takes a single parameter, which is the index of an entry
        to retrieve from the DB.

        :param index: The index of the item to be retrieved from the DB

        :return: True, if all operations successfully completed
        """

        read_start_time = time.time()

        read_entry = self.database_client.read(index)

        read_stop_time = time.time()

        read_time = read_stop_time - read_start_time

        self.read_times.append(read_time)

        if self.verbose or self.really_verbose:

            read_msg = 'Read data: {data}'.format(data=read_entry)

            if self.really_verbose:

                read_msg += '\nRead time: {time}'.format(time=read_time)

                read_msg += '\n--------------------------'

            print(read_msg)

        return True

    def compile_data(self):
        """ This function takes all the data collected from the trials (read
        and write times) and then calculates some important statistics about
        said data.  Without altering functionality, a report will be generated
        upon completion of analysis.

        :return compiled_data: All of the data needed to generate a full
                    benchmarking report
        """

        w = pd.DataFrame({'data': self.write_times})
        r = pd.DataFrame({'data': self.read_times})

        if self.csv:
            self.__generate_csv()

        write_metrics = self.__compute_descriptive_stats(w)
        read_metrics = self.__compute_descriptive_stats(r)

        rolling_avg_range = self.trials / 10

        writes_rolling_avg = self.__compute_rolling_avg(w, rolling_avg_range)
        reads_rolling_avg = self.__compute_rolling_avg(r, rolling_avg_range)

        write_metrics.update(rolling_avg=writes_rolling_avg)
        read_metrics.update(rolling_avg=reads_rolling_avg)

        normalized_writes = self.__normalize_data(
            w,
            write_metrics.get('avg'),
            write_metrics.get('stdev'),
        )
        normalized_reads = self.__normalize_data(
            r,
            read_metrics.get('avg'),
            read_metrics.get('stdev'),
        )

        write_metrics.update(normalized_data=normalized_writes)
        read_metrics.update(normalized_data=normalized_reads)

        compiled_data = {
            'write_metrics': write_metrics,
            'read_metrics': read_metrics,
            'n_stdev': self.n_stdev,
            'rolling_avg_range': rolling_avg_range,
        }

        return compiled_data

    @staticmethod
    def __compute_descriptive_stats(dataframe):
        """

        :param dataframe:
        :return:
        """

        df = dataframe

        metrics = {
            'avg': df.data.mean(),
            'stdev': df.data.std(),
            'max': df.data.max(),
            'min': df.data.min(),
            }

        range = metrics.get('max') - metrics.get('min')
        metrics.update(range=range)

        return metrics

    def __generate_csv(self):
        """

        :param dataframe:
        :return:
        """

        raw_data = pd.DataFrame({
                'reads': self.read_times,
                'writes': self.write_times,
            })

        raw_data.to_csv('{parent_dir}/raw_data.csv'.format(
            parent_dir=self.reports_dir
        ))

    def __normalize_data(self, dataframe, average, stdev):
        """

        :return:
        """
        df = dataframe

        n_stdev = 3

        if options.get('--debug'):
            stdev = 15

        if stdev > 3 * average:

            n_stdev = 1

        elif stdev > 2 * average:

            n_stdev = 2

        self.n_stdev = n_stdev

        dataframe = df[abs(df.data - average) <= (n_stdev * stdev)]

        return dataframe

    def generate_report_data(self, compiled_data):
        """ This function generates all of the actual tabular data that is
        displayed in the report.

        :param compiled_data: The post-analysis data from the benchmarks

        :return report_data: All of the tables for the report
        """

        cd = compiled_data

        param_header, param_values = self.__generate_paramater_table(
            compiled_data
        )

        data_header, data_values = self.__generate_data_table(
            compiled_data
        )

        param_table = tabulate(
            tabular_data=param_values,
            headers=param_header,
            tablefmt='grid',
        )

        data_table = tabulate(
            tabular_data=data_values,
            headers=data_header,
            tablefmt='grid',
            floatfmt='.5f',
        )

        param_table_md = tabulate(
            tabular_data=param_values,
            headers=param_header,
            tablefmt='pipe',
        )

        data_table_md = tabulate(
            tabular_data=data_values,
            headers=data_header,
            tablefmt='pipe',
            floatfmt='.5f',
        )

        #TODO - fix the terminal report so graph names aren't generated

        image_template = '![Alt text](images/{db}-{date}-{name}.png "{name}")'

        speed_plot = image_template.format(
            db=self.db_name,
            date=self.report_date,
            name='rw',
        )

        hist_plot = image_template.format(
            db=self.db_name,
            date=self.report_date,
            name='stats',
        )

        avgs_plot = image_template.format(
            db=self.db_name,
            date=self.report_date,
            name='running_averages',
        )

        rw = pd.DataFrame({
            'Writes': cd['writes'].data,
            'Reads': cd['reads'].data,
        })

        avgs = pd.DataFrame({
            'Writes Average': cd['writes_rolling_avg'],
            'Reads Average': cd['reads_rolling_avg'],
        })

        if not self.no_report:

            self.generate_plot(
                'rw', rw,
                title='Plot of Read and Write Speeds',
                x_label='Trial Number',
                y_label='Time (s)',
            )

            self.generate_plot(
                'running_averages', avgs,
                title='Plot of Rolling Averages for Reads and Writes',
                x_label='Trial Number',
                y_label='Time (s)',
            )

            self.generate_plot(
                'stats', rw,
                title='Histogram of Read and Write Times',
                plot_type='hist',
                x_label='Value (s)',
            )

        report_data = {
            'database': self.db_name,
            'time_and_date': self.time_and_date,
            'entry_length': self.entry_length,
            'node_number': self.number_of_nodes,
            'trial_number': self.trials,
            'param_table': param_table,
            'data_table': data_table,
            'outlier_table': outlier_table,
            'param_table_md': param_table_md,
            'data_table_md': data_table_md,
            'outlier_table_md': outlier_table_md,
            'speed_plot': speed_plot,
            'hist_plot': hist_plot,
            'avgs_plot': avgs_plot,
        }

        return report_data

    def __compute_rolling_avg(self, dataframe, range=None):
        """ Given a dataframe object, this function will compute a running
        average and return it as a separate dataframe object

        :param dataframe: a dataframe with which to compute a running average
        :param range: the range over which the rolling average should be
                    computed
        :return rolling_avg: a dataframe object with .data containing the
                    running average data
        """

        if not range:
            range = self.trials / 10

        rolling_avg = pd.stats.moments.rolling_mean(
            dataframe,
            range,
        ).data

        return rolling_avg

    def __generate_paramater_table(self, compiled_data):
        """

        :return:
        """

        cd = compiled_data

        param_header = [
            'Parameter',
            'Value',
        ]

        param_values = [
            ['Database Tested', self.db_name],
            ['Number of Trials', str(self.trials)],
            ['Length of Each Entry Field', str(self.entry_length)],
            ['Number of Nodes in Cluster', str(self.number_of_nodes)],
            ['# of StDev\'s Displayed in Graphs', str(cd.get('n_stdev'))],
            ['Range of Rolling Average in Graphs', str(cd.get('rolling_avg_range'))],
            ['Split Reads and Writes', str(self.split)],
            ['Debug Mode', str(options.get('--debug'))],
            ['Chaos Mode (Random Reads)', str(options.get('--chaos'))],
        ]

        return param_header, param_values

    def __generate_data_table(self, compiled_data):
        """

        :param compiled_data:
        :return:
        """

        cd = compiled_data

        data_header = [
            'Operation',
            'Average',
            'St. Dev.',
            'Max Time',
            'Min Time',
            'Range',
        ]

        data_values = [
            [
                'Writes',
                cd.get('write_avg'),
                cd.get('write_stdev'),
                cd.get('write_max'),
                cd.get('write_min'),
                cd.get('write_range'),
            ],
            [
                'Reads',
                cd.get('read_avg'),
                cd.get('read_stdev'),
                cd.get('read_max'),
                cd.get('read_min'),
                cd.get('read_range'),
            ],
        ]

        return data_header, data_values

    def generate_report(self, report_data):
        """ This function will take the compiled data and generated a report
        from it.  A report file will also be saved in the `generated_reports`
        directory, unless the `--no_report` option was selected at runtime.

        :param report_data: all of the necessary data to generate the
                    benchmark report
        """

        if self.report_title:

            report_name = '{parent_dir}/{title}.md'.format(
                          parent_dir=self.reports_dir,
                          title=self.report_title,
            )

        else:

            report_name = '{parent_dir}/{db}-{date}.report.md'.format(
                parent_dir=self.reports_dir,
                db=self.db_name,
                date=self.report_date,
            )

        with open('report_template.md', 'r') as infile:

            template = infile.read()

            terminal_report = template.format(**report_data)

            print('\n\n' + terminal_report + '\n\n')

            if not self.no_report:

                template = template.replace('_table', '_table_md')

                report = template.format(**report_data)

                with open(report_name, 'w+') as outfile:

                    outfile.write(report)

    def generate_plot(self, name, data_frame, title=None, x_label=None,
                      y_label=None, grid=True, plot_type='line'):
        """ This function take several parameters and generates a plot based
        on them.

        :param name: The name of the plot, which is important for saving
        :param data_frame: The data to be plotted
        :param title: The title to be displayed above the plot
        :param x_label: The label for the x-axis
        :param y_label: The label for the y-axis
        :param grid: Boolean to determine whether or not a grid should be used
        :param plot_type: The type of plot to generate
        """

        import matplotlib.pyplot as plt

        plt.figure()

        ax = data_frame.plot(
            title=title,
            grid=grid,
            legend=True,
            kind=plot_type,
        )

        if x_label:

            ax.set_xlabel(x_label)

        if y_label:

            ax.set_ylabel(y_label)

        current_name = '{parent_dir}/{db}-{date}-{name}'.format(
            parent_dir=self.images_dir,
            db=self.db_name,
            date=self.report_date,
            name=name,
        )

        plt.savefig(current_name)

    def register_module(self, db_mod):
        """ This function begins the process of registering a module for
        benchmarking.  The first step is to check to see if the module exists,
        and if it does, it will call `import_db_mod` to attempt the import.

        :param db_mod: The module to register

        :return mod_class: `mod_class` will ONLY BE RETURNED IF `import_db_mod`
                    runs successfully!
        """

        mod_list = retrieve_module_list()

        if db_mod in mod_list:

            mod_class = self.import_db_mod(db_mod)

            return mod_class

        else:

            error = 'Invalid DB module!  Please be sure you are using the \n' \
                    'package name and not just the name of the database ' \
                    'itself.\n'

            exit(error)

    @staticmethod
    def import_db_mod(module, mod_file='main'):
        """ This function will do the actual import of the database-specific
        module.  The `try/except` format is meant to be able to attempt the
        import, but fail gracefully if for some reason the package can't be
        imported.

        :param module: The module to be imported

        :return mod_class: The `Benchmark` class of the module, if it exists
        """

        try:

            package = '{mod}.{file}'.format(mod=module, file=mod_file)

            mod_class = importlib.import_module(package)

            return mod_class

        except ImportError:

            error = 'Error!  Package could not be imported!  Please make \n' \
                    'sure you are using the package name and not the name \n' \
                    'of the database itself.'

            exit(error)

if __name__ == '__main__':

    options = docopt(__doc__)

    Benchmark()