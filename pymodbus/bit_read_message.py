"""
Bit Reading Request/Response messages
--------------------------------------

"""
import struct
from pymodbus.pdu import ModbusRequest
from pymodbus.pdu import ModbusResponse
from pymodbus.pdu import ModbusExceptions as merror
from pymodbus.utilities import pack_bitstring, unpack_bitstring


class ReadBitsRequestBase(ModbusRequest):
    ''' Base class for Messages Requesting bit values '''

    _rtu_frame_size = 8

    def __init__(self, address, count, **kwargs):
        ''' Initializes the read request data

        :param address: The start address to read from
        :param count: The number of bits after 'address' to read
        '''
        ModbusRequest.__init__(self, **kwargs)
        self.address = address
        self.count   = count

    def encode(self):
        ''' Encodes a request pdu

        :returns: The encoded pdu
        '''
        return struct.pack('>HH', self.address, self.count)

    def decode(self, data):
        ''' Decodes a request pdu

        :param data: The packet data to decode
        '''
        self.address, self.count = struct.unpack('>HH', data)

    def __str__(self):
        ''' Returns a string representation of the instance

        :returns: A string representation of the instance
        '''
        return "ReadBitRequest(%d,%d)" % (self.address, self.count)


class ReadBitsResponseBase(ModbusResponse):
    ''' Base class for Messages responding to bit-reading values '''

    _rtu_byte_count_pos = 2

    def __init__(self, values, **kwargs):
        ''' Initializes a new instance

        :param values: The requested values to be returned
        '''
        ModbusResponse.__init__(self, **kwargs)
        self._bits = None
        self._raw_bits = None

        if values:  # Values is not None or empty
            # Is `values` a list of bools or a byte array?
            if isinstance(values[0], (bool, int)):
                # This is a sequence of bools
                self._bits = [bool(v) for v in values]
            elif isinstance(values[0], (bytes, str)):
                # This is a raw bit string
                self._raw_bits = values
            else:
                raise TypeError(
                        'values (%r) not a bytestring or boolean list' % values)

    @property
    def bits(self):
        '''
        Lazily decode and return the bitstring.
        '''
        if self._bits is None:
            self._bits = unpack_bitstring(self._raw_bits or b'')
        return self._bits

    @bits.setter
    def bits(self, newbits):
        '''
        Replace the data with the given bits
        '''
        self._bits = newbits
        self._raw_bits = None
        self._byte_count = None

    @property
    def raw_bits(self):
        '''
        Retrieve the raw bitstring for the given bits.
        '''
        if self._raw_bits is None:
            self._raw_bits = pack_bitstring(self._bits or [])
        return self._raw_bits

    @raw_bits.setter
    def raw_bits(self, newbits):
        '''
        Replace the data with the given bits
        '''
        self._raw_bits = newbits
        self._bits = None
        self._byte_count = None

    @property
    def byte_count(self):
        if self._byte_count is None:
            self._byte_count = len(self.raw_bits)
        return self._byte_count

    def encode(self):
        ''' Encodes response pdu

        :returns: The encoded packet message
        '''
        result = self.raw_bits
        packet = struct.pack(">B", len(result)) + result
        return packet

    def decode(self, data):
        ''' Decodes response pdu

        :param data: The packet data to decode
        '''
        self._byte_count = struct.unpack(">B", data[0])[0]
        self._raw_bits = data[1:]
        self._bits = None

    def setBit(self, address, value=1):
        ''' Helper function to set the specified bit

        :param address: The bit to set
        :param value: The value to set the bit to
        '''
        self.bits[address] = (value != 0)
        self._raw_bits = None

    def resetBit(self, address):
        ''' Helper function to set the specified bit to 0

        :param address: The bit to reset
        '''
        self.setBit(address, 0)
        self._raw_bits = None

    def getBit(self, address):
        ''' Helper function to get the specified bit's value

        :param address: The bit to query
        :returns: The value of the requested bit
        '''
        return self.bits[address]

    def __str__(self):
        ''' Returns a string representation of the instance

        :returns: A string representation of the instance
        '''
        return "ReadBitResponse(%d)" % len(self.bits)


class ReadCoilsRequest(ReadBitsRequestBase):
    '''
    This function code is used to read from 1 to 2000(0x7d0) contiguous status
    of coils in a remote device. The Request PDU specifies the starting
    address, ie the address of the first coil specified, and the number of
    coils. In the PDU Coils are addressed starting at zero. Therefore coils
    numbered 1-16 are addressed as 0-15.
    '''
    function_code = 1

    def __init__(self, address=None, count=None, **kwargs):
        ''' Initializes a new instance

        :param address: The address to start reading from
        :param count: The number of bits to read
        '''
        ReadBitsRequestBase.__init__(self, address, count, **kwargs)

    def execute(self, context):
        ''' Run a read coils request against a datastore

        Before running the request, we make sure that the request is in
        the max valid range (0x001-0x7d0). Next we make sure that the
        request is valid against the current datastore.

        :param context: The datastore to request from
        :returns: The initializes response message, exception message otherwise
        '''
        if not (1 <= self.count <= 0x7d0):
            return self.doException(merror.IllegalValue)
        if not context.validate(self.function_code, self.address, self.count):
            return self.doException(merror.IllegalAddress)
        values = context.getValues(self.function_code, self.address, self.count)
        return ReadCoilsResponse(values)


class ReadCoilsResponse(ReadBitsResponseBase):
    '''
    The coils in the response message are packed as one coil per bit of
    the data field. Status is indicated as 1= ON and 0= OFF. The LSB of the
    first data byte contains the output addressed in the query. The other
    coils follow toward the high order end of this byte, and from low order
    to high order in subsequent bytes.

    If the returned output quantity is not a multiple of eight, the
    remaining bits in the final data byte will be padded with zeros
    (toward the high order end of the byte). The Byte Count field specifies
    the quantity of complete bytes of data.
    '''
    function_code = 1

    def __init__(self, values=None, **kwargs):
        ''' Intializes a new instance

        :param values: The request values to respond with
        '''
        ReadBitsResponseBase.__init__(self, values, **kwargs)


class ReadDiscreteInputsRequest(ReadBitsRequestBase):
    '''
    This function code is used to read from 1 to 2000(0x7d0) contiguous status
    of discrete inputs in a remote device. The Request PDU specifies the
    starting address, ie the address of the first input specified, and the
    number of inputs. In the PDU Discrete Inputs are addressed starting at
    zero. Therefore Discrete inputs numbered 1-16 are addressed as 0-15.
    '''
    function_code = 2

    def __init__(self, address=None, count=None, **kwargs):
        ''' Intializes a new instance

        :param address: The address to start reading from
        :param count: The number of bits to read
        '''
        ReadBitsRequestBase.__init__(self, address, count, **kwargs)

    def execute(self, context):
        ''' Run a read discrete input request against a datastore

        Before running the request, we make sure that the request is in
        the max valid range (0x001-0x7d0). Next we make sure that the
        request is valid against the current datastore.

        :param context: The datastore to request from
        :returns: The initializes response message, exception message otherwise
        '''
        if not (1 <= self.count <= 0x7d0):
            return self.doException(merror.IllegalValue)
        if not context.validate(self.function_code, self.address, self.count):
            return self.doException(merror.IllegalAddress)
        values = context.getValues(self.function_code, self.address, self.count)
        return ReadDiscreteInputsResponse(values)


class ReadDiscreteInputsResponse(ReadBitsResponseBase):
    '''
    The discrete inputs in the response message are packed as one input per
    bit of the data field. Status is indicated as 1= ON; 0= OFF. The LSB of
    the first data byte contains the input addressed in the query. The other
    inputs follow toward the high order end of this byte, and from low order
    to high order in subsequent bytes.

    If the returned input quantity is not a multiple of eight, the
    remaining bits in the final data byte will be padded with zeros
    (toward the high order end of the byte). The Byte Count field specifies
    the quantity of complete bytes of data.
    '''
    function_code = 2

    def __init__(self, values=None, **kwargs):
        ''' Intializes a new instance

        :param values: The request values to respond with
        '''
        ReadBitsResponseBase.__init__(self, values, **kwargs)

#---------------------------------------------------------------------------#
# Exported symbols
#---------------------------------------------------------------------------#
__all__ = [
    "ReadCoilsRequest", "ReadCoilsResponse",
    "ReadDiscreteInputsRequest", "ReadDiscreteInputsResponse",
]
