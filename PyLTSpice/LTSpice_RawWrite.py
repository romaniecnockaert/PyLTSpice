#!/usr/bin/env python
# coding=utf-8

# -------------------------------------------------------------------------------
# Name:        LTSpice_RawWrite.py
# Purpose:     Create RAW Files
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     16-10-2021
# Licence:     General Public GNU License
# -------------------------------------------------------------------------------

"""
This module generates RAW Files from user data.
It can be used to combine RAW files generated by different Simulation Runs
"""
from typing import Union
from time import strftime
from PyLTSpice.LTSpice_RawRead import DataSet, USE_NNUMPY, LTSpiceRawRead
from struct import pack

if USE_NNUMPY:
    from numpy import array


class Trace(DataSet):
    """Helper class representing a trace. This class is based on DataSet, therefore, it doesn't support STEPPED data."""

    def __init__(self, name, data):
        if name == 'time':
            datatype = 'time'
            numerical_type = 'real'
        elif name == 'frequency':
            datatype = 'frequency'
            numerical_type = 'complex'
        else:
            datatype = 'voltage'
            numerical_type = 'real'

        DataSet.__init__(self, name, datatype, 0)
        self.numerical_type = numerical_type
        if USE_NNUMPY and isinstance(data, (list, tuple)):
            self.data = array(data)
        else:
            self.data = data


class LTSpiceRawWrite(object):
    """
    This class represents the RAW data file being generated. Contrary to the the LTSpiceRawRead this class doesn't
    support stepped data.

    """

    def __init__(self, plot_name='', fastacces=True):
        self._traces = list()
        self.flag_numtype = 'real'
        self.flag_stepped = False
        self.flag_fastaccess = fastacces
        self.plot_name = plot_name
        self.offset = 0.0
        self.encoding = 'utf_16_le'
        
    def _str_flags(self):
        flags = [self.flag_numtype]
        if self.flag_stepped:
            flags.append('stepped')
        if self.flag_fastaccess:
            flags.append('fastaccess')
        return ' '.join(flags)

    def _format_for_trace(self, datatype):
        if datatype == 'time':
            fmt = 'd'
        elif datatype == 'frequency':
            fmt = 'dd'
        else:
            fmt = 'f'
        return fmt

    def add_trace(self, trace: Trace):
        """
        Adds a trace to the RAW file. The trace needs to have the same size of the trace 0 ('time', 'frequency', etc..)
        The first trace added defines the X-Axis and therefore the type of RAW file being generated. If no plot name
        was defined, it will automatically assign a name.
        :param trace: Needs to be of the
        :type trace:
        :return: Nothing
        :rtype: None
        """
        assert isinstance(trace, Trace), "The trace needs to be of the type ""Trace"""
        if self.plot_name is None or len(self._traces) == 0:
            if trace.type == 'time':
                self.plot_name = self.plot_name or 'Time Transient'
                self.flag_numtype = 'real'
            elif trace.type == 'frequency':
                self.plot_name = self.plot_name or 'AC Analysis'
                self.flag_numtype = 'complex'
            elif trace.type in ('voltage', 'current'):
                self.plot_name = self.plot_name or 'DC transfer characteristic'
                self.flag_numtype = 'real'
            elif trace.type == 'param':
                self.plot_name = self.plot_name or 'Operating Point'
                self.flag_numtype = 'real'
            else:
                raise ValueError("First Trace needs to be either 'time', 'frequency', 'param', 'voltage' or '...'")
        else:
            if len(self._traces[0]) != len(trace):
                raise IndexError("The trace needs to be the same size of the trace 0")
        self._traces.append(trace)

    def save(self, filename: str):
        """
        Saves the RAW file into a file. The file format is always binary. Text based RAW output format is not supported
        in this version.

        :param filename: filename to where the RAW file is going to be written. Make sure that the extension of the file
        is .RAW.

        :type filename: str
        :return: Nothing
        :rtype: None
        """
        f = open(filename, 'wb')
        f.write("Title: * PyLTSpice LTSpice_RawWrite\n".encode(self.encoding))
        f.write("Date: {}\n".format(strftime("%a %b %d %H:%M:%S %Y")).encode(self.encoding))
        f.write("Plotname: {}\n".format(self.plot_name).encode(self.encoding))
        f.write("Flags: {}\n".format(self._str_flags()).encode(self.encoding))
        f.write("No. Variables: {}\n".format(len(self._traces)).encode(self.encoding))
        f.write("No. Points: {:12}\n".format(len(self._traces[0])).encode(self.encoding))
        f.write("Offset:   {:.16e}\n".format(self.offset).encode(self.encoding))
        f.write("Command: Linear Technology Corporation LTspice XVII\n".encode(self.encoding))
        f.write("Backannotation: \n".encode(self.encoding))
        f.write("Variables:\n".encode(self.encoding))
        for i, trace in enumerate(self._traces):
            f.write("\t{0}\t{1}\t{2}\n".format(i, trace.name, trace.type).encode(self.encoding))
        total_bytes = 0
        f.write("Binary:\n".encode(self.encoding))
        if self.flag_fastaccess:
            for trace in self._traces:
                if False: #USE_NNUMPY:
                    # TODO: Implement a faster save using the numpy methods
                    f.write(trace.data.pack('dd'))
                else:
                    fmt = self._format_for_trace(trace.type)
                    for value in trace.data:
                        f.write(pack(fmt, value))
        else:
            for i in range(len(self._traces[0])):
                for trace in self._traces:
                    fmt = self._format_for_trace(trace.type)
                    total_bytes += f.write(pack(fmt, trace[i]))
        f.close()

    def _rename_netlabel(self, name, rename_format: str, *kwargs) -> str:
        """Makes sure that a trace is not a duplicate when adding it to the set"""
        # Make the rename as requested
        if name.endswith(')') and name.startswith('V(') or name.startswith('I('):
            new_name = name[:2] + rename_format.format(name, **kwargs) + name[-1]
        else:
            new_name = rename_format.format(name, **kwargs)
        return new_name

    def _name_exists(self, name: str) -> bool:
        # first check whether it is a duplicate
        for trace in self._traces:
            if trace.name == name:
                return True
        return False

    def add_traces_from_raw(self, other: LTSpiceRawRead, trace_filter: Union[list, tuple], **kwargs):
        skip_doc ="""
        *(Not fully implemented)*

        Merge two LTSpiceRawWrite classes together resulting in a new instance
        :param other: another instance of the LTSpiceRawWrite class.
        :type other: LTSpiceRawWrite
        :param trace_filter: A list of signals that should be imported into the new file
        :type trace_filter: list
        :keyword force_axis_alignment: If two raw files don't have the same axis, an attempt is made to sync the two
        :keyword admissible_error: maximum error allowed in the sync between the two axis
        :keyword rename_format: when adding traces with the same name, it is possible to define a rename format.
            For example, if there are two traces named N001 in order to avoid duplicate names the
            rename format can be defined as "{}_{kwarg_name} where kwarg_name is passed as a keyword
            argument of this function

        :keyword step: by default only step 0 is added from the second raw. It is possible to add other steps, by
            using this keyword parameter. This is useful when we want to "flatten" the multiple step runs into the same 
            view.
        :keyword: minimum_timestep: This parameter forces the two axis to sync using a minimum time step. That is, all
            time increments that are less than this parameter will be suppressed.
        :return: A new instance of LTSpiceRawWrite with
        :rtype: LTSpiceRawWrite
        """
        for flag in other.get_raw_property('Flags').split(' '):
            if flag in ('real', 'complex'):
                other_flag_num_type = flag
                break
        else:
            other_flag_num_type = 'real'

        if (self.flag_numtype != other_flag_num_type) or (self._traces[0].type != other.get_trace(0).type):
            raise ValueError("The two instances should have the same type")
        force_axis_alignment = kwargs.get('force_axis_alignment', False)
        admissible_error = kwargs.get('admissible_error', 1e-11)
        rename_format = kwargs.get('rename_format', '{}')
        from_step = kwargs.get('step', 0)
        minimum_timestep = kwargs.get('fixed_timestep', 0.0)

        if len(self._traces) == 0:  # if no X axis is present, copy from the first one
            new_axis = Trace(other.get_trace(0).name, other.get_axis(from_step))
            self._traces.append(new_axis)
            force_axis_alignment = False
        my_axis = self._traces[0].get_wave()
        other_axis = other.get_axis()

        if force_axis_alignment or minimum_timestep > 0.0:
            new_axis = []
            if minimum_timestep > 0.0:
                raise NotImplementedError
            else:
                i = 0  # incomming data counter
                e = 0  # existing data counter
                existing_data = {}
                incoming_data = {}
                new_traces = {}
                updated_traces = {}

                for new_trace in trace_filter:
                    new_traces[new_trace] = []
                    incoming_data[new_trace] = other.get_trace(new_trace).get_wave(from_step)
                for trace in self._traces[1:]:  # not considering axis
                    updated_traces[trace.name] = []
                    existing_data[trace.name] = self.get_trace(trace.name).get_wave()

                axis_name = self._traces[0].name  # Saving the trace name for recreating all the traces

                while e < len(my_axis)-1 and i < len(other_axis)-1:
                    error = other_axis[i] - my_axis[e]
                    if abs(error) < admissible_error:
                        new_axis.append(my_axis[e])
                        i += 1
                        e += 1
                    elif error < 0:
                        # Other axis is smaller
                        new_axis.append(other_axis[i])
                        i += 1
                    else:
                        new_axis.append(my_axis[e])
                        e += 1
                    for trace in incoming_data:
                        new_traces[trace].append(incoming_data[trace][i])
                    for trace in existing_data:
                        updated_traces[trace].append(existing_data[trace][e])

                self._traces.clear()  # Cleaning class list of traces
                # Creating the New Axis
                self._traces.append(Trace(axis_name, new_axis))
                # Now recreating all tre traces
                for trace in incoming_data:
                    self._traces.append(Trace(trace, incoming_data[trace]))
                for trace in existing_data:
                    self._traces.append(Trace(trace, existing_data[trace]))

        else:
            assert len(self._traces[0]) == len(other.get_axis()), "The two instances should have the same size"
            for trace in trace_filter:
                data = other.get_trace(trace).get_wave(from_step)
                self._traces.append(Trace(rename_format.format(trace, **kwargs), data))

    def get_trace(self, trace_ref):
        """
        Retrieves the trace with the requested name (trace_ref).

        :param trace_ref: Name of the trace
        :type trace_ref: str
        :return: An object containing the requested trace
        :rtype: DataSet subclass
        """
        if isinstance(trace_ref, str):
            for trace in self._traces:
                if trace_ref == trace.name:
                    # assert isinstance(trace, DataSet)
                    return trace
            return None
        else:
            return self._traces[trace_ref]

    def __getitem__(self, item):
        """Helper function to access traces by using the [ ] operator."""
        return self.get_trace(item)


if __name__ == '__main__':
    import numpy as np
    from LTSpice_RawRead import LTSpiceRawRead

    def test_trc2raw():  # Convert Teledyne-Lecroy trace files to raw files
        f = open(r"Current_Lock_Front_Right_8V.trc")
        raw_type = ''  # Initialization of parameters that need to be overridden by the file header
        wave_size = 0
        for line in f:
            tokens = line.rstrip('\n').split(',')
            if len(tokens) == 4:
                if tokens[0] == 'Segments' and tokens[2] == 'SegmentSize':
                    wave_size = int(tokens[1]) * int(tokens[3])
            if len(tokens) == 2:
                if tokens[0] == 'Time' and tokens[1] == 'Ampl':
                    raw_type = 'transient'
                    break
        if raw_type == 'transient' and wave_size > 0:
            data = np.genfromtxt(f, dtype='float,float', delimiter=',', max_rows=wave_size)
            LW = LTSpiceRawWrite()
            LW.add_trace(Trace('time', [x[0] for x in data]))
            LW.add_trace(Trace('Ampl', [x[1] for x in data]))
            LW.save("teste_trc.raw")
        f.close()


    def test_axis_sync():  # Test axis sync
        LW = LTSpiceRawWrite()
        tx = Trace('time', np.arange(0.0, 3e-3, 997E-11))
        vy = Trace('N001', np.sin(2 * np.pi * tx.data * 10000))
        vz = Trace('N002', np.cos(2 * np.pi * tx.data * 9970))
        LW.add_trace(tx)
        LW.add_trace(vy)
        LW.add_trace(vz)
        LW.save("teste_w.raw")
        LR = LTSpiceRawRead("..\\test_files\\testfile.raw")
        LW.add_traces_from_raw(LR, ('V(out)',), force_axis_alignment=True)
        LW.save("merge.raw")
        test = """
        equal = True
        for ii in range(len(tx)):
            if t[ii] != tx[ii]:
                print(t[ii], tx[ii])
                equal = False
        print(equal)
    
        v = LR.get_trace('N001')
        max_error = 1.5e-12
        for ii in range(len(vy)):
            err = abs(v[ii] - vy[ii])
            if err > max_error:
                max_error = err
                print(v[ii], vy[ii], v[ii] - vy[ii])
        print(max_error)
        """

    test_axis_sync()