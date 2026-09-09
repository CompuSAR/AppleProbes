#!/usr/bin/python3

"""
send_to_apple.py

Parse a vasm .lst listing file (same format handled by parse_lst) and feed
the resulting bytes to an Apple II sitting at the System Monitor prompt over
a serial connection, using the monitor's memory-write syntax:

    2000:00 01 FE 6A 85
    :42 37 8B

The first line of a contiguous run of bytes includes the address; follow-up
lines for the *same* run start with a bare ':' and the monitor keeps
advancing the address automatically, which is why we only need to give the
address once per contiguous run.

Usage:
    ./send_to_apple.py test_program_mos.lst /dev/ttyUSB0
    ./send_to_apple.py test_program_mos.lst /dev/ttyUSB0 --dry-run
    ./send_to_apple.py test_program_mos.lst /dev/ttyUSB0 --run 300
"""

import argparse
import re
import sys
import serial
import time

import termios
import tty
import select

BAUD = 19200

# Same grammar as parse_lst, used to pull (address, data-bytes) records out
# of the vasm listing file.
LST_LINE = re.compile(
    r'''
    ^
    (?P<SourceHeader> Source: \s "(?P<source_file> .*)" )
    |
    (?P<Data> [0-9A-F]+: (?P<address> [0-9A-F]{4}) \s (?P<data> ([0-9A-F]{2})+) )
        (?P<Source> \s+ (?P<source_line> \d+) : \s+ (?P<source> .*))?
    |
    (?P<Array> [0-9A-F]+: (?P<address_> [0-9A-F]{4}) \s \*)
    $
    ''',
    re.VERBOSE)


def parse_lst(path):
    """Walk the listing file and return a sorted list of (address, byte)
    tuples describing every byte the assembler placed in memory."""

    memory = {}  # address -> byte value; later writes win, same as loading
                 # into real memory in file order.
    source_file = None
    last_record = None      # (address, [bytes]) of the most recent Data line
    pending_array = None    # (start_address, [fill_bytes]) awaiting an
                             # "Array" (repeat-fill, e.g. .fill/.ds) line
    first_addr1 = None

    with open(path) as f:
        for raw_line in f:
            line = raw_line.rstrip('\n')
            match = LST_LINE.match(line)

            if match is None:
                last_record = None
                continue

            if match['SourceHeader']:
                source_file = match['source_file']
                last_record = None

            elif match['Data']:
                if source_file is None:
                    last_record = None
                    continue

                out_addr = int(match['address'], 16)
                if first_addr1 is None:
                    first_addr1 = out_addr

                # A pending array fills every address between the previous
                # record's end and this line's address with its one byte.
                if pending_array is not None:
                    fill_start, fill_bytes = pending_array
                    assert len(fill_bytes) == 1, "Multi-byte arrays not implemented"
                    for addr in range(fill_start, out_addr):
                        memory[addr] = fill_bytes[0]
                    pending_array = None

                data_str = match['data']
                data_bytes = [int(data_str[i:i + 2], 16)
                              for i in range(0, len(data_str), 2)]

                for i, b in enumerate(data_bytes):
                    memory[out_addr + i] = b

                last_record = (out_addr, data_bytes)

            elif match['Array']:
                assert last_record, "Got an array with no previous data line"
                out_addr = int(match['address_'], 16)
                assert out_addr == last_record[0] + len(last_record[1]), \
                    "Array address does not immediately follow previous address"
                pending_array = (out_addr, last_record[1])

    return sorted(memory.items()), first_addr1

def group_into_runs(byte_list):
    """Turn a sorted [(addr, byte), ...] list into a list of
    (start_addr, [bytes...]) runs of contiguous addresses."""

    runs = []
    for addr, byte in byte_list:
        if runs and addr == runs[-1][0] + len(runs[-1][1]):
            runs[-1][1].append(byte)
        else:
            runs.append((addr, [byte]))
    return runs


# Bit 7 of an Apple II text-page byte only select display mode (inverse /
# flash / normal); they don't change which character it is. When comparing
# a line we sent against the echo we got back, mask them off on both sides
# so mode bits never cause a false mismatch.
CHAR_MASK = 0x7F

def recv_chars(ser, block):
    line = ""
    if block:
        for b in ser.read():
            line += chr(b&CHAR_MASK)
    else:
        for b in ser.read_all():
            line += chr(b&CHAR_MASK)

    for c in line:
        if c == '\r':
            print()
        else:
            print(c, end="")

    return line

def recv_char(ser, ch):
    while True:
        line = ser.read()
        if (line[len(line)-1] & CHAR_MASK) == (ord(ch)&CHAR_MASK):
            break

    if ch=='\r':
        print()
    else:
        print(ch, end="")

def send_char(ser, ch):
    recv_chars(ser, False)
    ser.write(ch.encode())
    ser.flush()
    time.sleep(args.delay)

    recv_char(ser, ch)

def send_chars(ser, s):
    for c in s:
        send_char(ser, c)

def wait_prompt(ser):
    while True:
        prompt = recv_chars(ser, True)
        if prompt[len(prompt)-1] == ']':
            send_chars(ser, "CALL -151\r")
        elif prompt[len(prompt)-1] == '*':
            break

def enter_monitor(ser):
    print("\n-- Entering monitor")
    send_char(ser, "\r")

    wait_prompt(ser)

def dumb_term(ser):
    formerstate = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin)
    try:
        while(True):
            readready, writeready, err = select.select([ser, sys.stdin], [], [])

            for r in readready:
                if r is ser:
                    chars = ser.read_all()

                    for c in chars:
                        c = c & 0x7f
                        if c==13:
                            print()
                        else:
                            print(chr(c), end="", flush=True)
                if r is sys.stdin:
                    ch = sys.stdin.read(1)

                    if ch=='\n':
                        ser.write(b'\r')
                    else:
                        ser.write(ch.encode())
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, formerstate)

def main():
    ap = argparse.ArgumentParser(
        description="Send a vasm .lst listing to an Apple II monitor over serial.")
    ap.add_argument('list_file', help="The .lst listing file to load")
    ap.add_argument('port', nargs='?',
                     help="Serial port, e.g. /dev/ttyUSB0 or COM3 "
                          "(not needed with --dry-run)")
    ap.add_argument('--bytes-per-line', type=int, default=8,
                     help="How many data bytes to pack per monitor command "
                          "line (default: 8)")
    ap.add_argument('--delay', type=float, default=0,
                     help="Seconds to pause after each char.")
    ap.add_argument('--wait-echo', dest='wait_echo', action='store_true',
                     default=True,
                     help="Wait for the Apple II to echo each line back "
                          "before sending the next one, instead of a fixed "
                          "delay. Use this if your serial card/firmware "
                          "echoes received characters. (default: on)")
    ap.add_argument('--no-wait-echo', dest='wait_echo', action='store_false',
                     help="Don't wait for echo; just pace sends with "
                          "--delay instead.")
    ap.add_argument('--run', nargs='?', const='AUTO', default=None,
                     metavar='ADDR',
                     help="After loading, send 'ADDR G' to jump to and run "
                          "that address (hex, no leading $). If given with "
                          "no value, runs from the first opcode of the "
                          "program (the lowest address in the listing).")
    ap.add_argument('--dry-run', action='store_true',
                     help="Just print the monitor commands, don't open a "
                          "serial port")
    ap.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                     default=True,
                     help="Print each command line as it's sent (default: on)")
    ap.add_argument('-q', '--quiet', dest='verbose', action='store_false',
                     help="Don't print each command line as it's sent")
    global args
    args = ap.parse_args()

    if not args.port:
        ap.error("port is required unless --dry-run is given")

    memory, run_addr = parse_lst(args.list_file)
    if not memory:
        print("No data records found in listing file.", file=sys.stderr)
        sys.exit(1)

    runs = group_into_runs(memory)

    total_bytes = sum(len(data) for _, data in runs)
    print(f"{len(runs)} contiguous run(s), {total_bytes} byte(s), ", file=sys.stderr)

    with serial.Serial(args.port, BAUD, timeout=2) as ser:
        ser.read_all()
        send_char(ser, "\r")
        send_chars(ser, "\x02\r")
        enter_monitor(ser)
        for addr, data in runs:
            i = 0
            send_chars(ser, f"{addr:04X}")
            while len(data)>i:
                send_chars(ser, ":")
                j = min(args.bytes_per_line, len(data)-i)
                while j>0:
                    send_chars(ser, f"{data[i]:02X} ")
                    i = i+1
                    j = j-1
                    addr = addr+1

                send_char(ser, "\r")
                wait_prompt(ser)

        dumb_term(ser)


if __name__ == '__main__':
    main()
