# coding=utf-8
'''
from cpython.dict cimport PyDict_GetItem, PyDict_SetItem
from cpython.exc cimport PyErr_Clear, PyErr_GivenExceptionMatches, PyErr_Occurred
from cpython.list cimport PyList_Append, PyList_GET_ITEM, PyList_GET_SIZE
from cpython.object cimport PyObject_RichCompareBool, Py_NE
from cpython.ref cimport PyObject, Py_INCREF, Py_XDECREF
from cpython.sequence cimport PySequence_Check
from cpython.set cimport PySet_Add, PySet_Contains
from cpython.tuple cimport PyTuple_GET_ITEM, PyTuple_GetSlice, PyTuple_New, PyTuple_SET_ITEM
from typing import List,Tuple
from time import perf_counter

from libc.stdio cimport sprintf


'''
from cpython.object cimport Py_SIZE
from time import perf_counter

from cpython cimport array
import array
from cpython.list cimport PyList_Append


cdef class Timings:
    cdef bytes prefix
    cdef list names
    cdef array.array timings

    def __cinit__(self, bytes prefix):
        self.prefix = prefix
        self.timings = array.array('d',[])
        self.names = ['created']

    cpdef record(self, name:str):
        cdef double now = perf_counter()
        self.timings.append(now)
        PyList_Append(self.names, name)

    cdef array.array[double] calculate_elapsed(self, array.array[double] timings):
        cdef double time1, time2, elapsed
        cdef Py_ssize_t len_timings = len(timings)
        cdef int i
        cdef array.array[double] results = array.copy(timings)
        for i in range(1,len_timings):
            time1 = timings.data.as_doubles[i-1]
            time2 = timings.data.as_doubles[i]
            elapsed = ((time2 - time1) * 1000)
            results[i-1] = elapsed
        return results

    cpdef list stats(self):
        cdef array.array[double] elapsed  = self.calculate_elapsed(self.timings)
        prefix = self.prefix.decode()
        return [f'{prefix}.{name}:{stat:0.6f}|ms' for name,stat in zip(self.names,elapsed)]
