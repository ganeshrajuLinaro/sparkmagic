import json
import pandas as pd
from hdijupyterutils.guid import ObjectWithGuid

from sparkmagic.utils.utils import coerce_pandas_df_to_numeric_datetime
import sparkmagic.utils.configuration as conf
import sparkmagic.utils.constants as constants
from sparkmagic.utils.sparkevents import SparkEvents
from .command import Command
from .exceptions import DataFrameParseException, BadUserDataException


class SQLQuery(ObjectWithGuid):
    def __init__(self, query, samplemethod=None, maxrows=None, samplefraction=None, spark_events=None):
        super(SQLQuery, self).__init__()
        
        if samplemethod is None:
            samplemethod = conf.default_samplemethod()
        if maxrows is None:
            maxrows = conf.default_maxrows()
        if samplefraction is None:
            samplefraction = conf.default_samplefraction()

        if samplemethod not in {u'take', u'sample'}:
            raise BadUserDataException(u'samplemethod (-m) must be one of (take, sample)')
        if not isinstance(maxrows, int):
            raise BadUserDataException(u'maxrows (-n) must be an integer')
        if not 0.0 <= samplefraction <= 1.0:
            raise BadUserDataException(u'samplefraction (-r) must be a float between 0.0 and 1.0')

        self.query = query
        self.samplemethod = samplemethod
        self.maxrows = maxrows
        self.samplefraction = samplefraction
        if spark_events is None:
            spark_events = SparkEvents()
        self._spark_events = spark_events

    def to_command(self, kind):
        if kind == constants.SESSION_KIND_PYSPARK:
            return self._pyspark_command()
        elif kind == constants.SESSION_KIND_SPARK:
            return self._scala_command()
        elif kind == constants.SESSION_KIND_SPARKR:
            return self._r_command()
        else:
            raise BadUserDataException(u"Kind '{}' is not supported.".format(kind))

    def execute(self, session):
        self._spark_events.emit_sql_execution_start_event(session.guid, session.kind, session.id, self.guid,
                                                          self.samplemethod, self.maxrows, self.samplefraction)
        command_guid = ''
        try:
            command = self.to_command(session.kind)
            command_guid = command.guid
            (success, records_text) = command.execute(session)
            if not success:
                raise DataFrameParseException(records_text)
            result = self._records_to_dataframe(records_text)
        except Exception as e:
            self._spark_events.emit_sql_execution_end_event(session.guid, session.kind, session.id, self.guid,
                                                            command_guid, False, e.__class__.__name__, str(e))
            raise
        else:
            self._spark_events.emit_sql_execution_end_event(session.guid, session.kind, session.id, self.guid,
                                                            command_guid, True, "", "")
            return result

    @staticmethod
    def _records_to_dataframe(records_text):
        if records_text == '':
            strings = []
        else:
            strings = records_text.split('\n')
        try:
            df = pd.DataFrame([json.loads(s) for s in strings])
            coerce_pandas_df_to_numeric_datetime(df)
            return df
        except ValueError:
            raise DataFrameParseException(u"Cannot parse object as JSON: '{}'".format(strings))

    def _pyspark_command(self):
        command = u'sqlContext.sql(u"""{} """).toJSON()'.format(self.query)
        if self.samplemethod == u'sample':
            command = u'{}.sample(False, {})'.format(command, self.samplefraction)
        if self.maxrows >= 0:
            command = u'{}.take({})'.format(command, self.maxrows)
        else:
            command = u'{}.collect()'.format(command)
        command = u'for {} in {}: print({}.encode("{}"))'.format(constants.LONG_RANDOM_VARIABLE_NAME,
                                                    command,
                                                    constants.LONG_RANDOM_VARIABLE_NAME,
                                                    conf.pyspark_sql_encoding())
        return Command(command)

    def _scala_command(self):
        command = u'sqlContext.sql("""{}""").toJSON'.format(self.query)
        if self.samplemethod == u'sample':
            command = u'{}.sample(false, {})'.format(command, self.samplefraction)
        if self.maxrows >= 0:
            command = u'{}.take({})'.format(command, self.maxrows)
        else:
            command = u'{}.collect'.format(command)
        return Command(u'{}.foreach(println)'.format(command))

    def _r_command(self):
        raise NotImplementedError()

    # Used only for unit testing
    def __eq__(self, other):
        return self.query == other.query and \
            self.samplemethod == other.samplemethod and \
            self.maxrows == other.maxrows and \
            self.samplefraction == other.samplefraction

    def __ne__(self, other):
        return not (self == other)
