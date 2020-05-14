from nmigen.back.pysim import Simulator
from nmigen_sigma_delta.cic import CIC
import random
import math
import numpy as np
import pytest

def run_sim(dut, data, n):
    sim = Simulator(dut)
    sim.add_clock(10e-9, domain='sync')
    sim.add_sync_process(dut.input.send_driver(data))
    sim.add_sync_process(dut.output.recv_driver(n))
    sim.run()

def test_paper_result():
    discared = CIC(4, 25, 16, 16).get_discared_bits()
    assert discared == [1, 6, 9, 13, 14, 15, 16, 17]


def run_step_test(dut, value):
    n = dut.order + 4
    data = [value for i in range(dut.decimation * n)]
    gain = dut.get_gain()
    run_sim(dut, data, n)
    assert dut.output._received[-1] == value * gain


@pytest.mark.parametrize('order', [1, 2, 3, 4])
@pytest.mark.parametrize('decimation', [8, 16, 256])
def test_step(order, decimation, i_width=8, o_width=10):
    dut = CIC(order, decimation, i_width, o_width)
    run_step_test(dut, 2**i_width - 1)
    run_step_test(dut, 0)


def test_one_bit():
    decimation = 255
    dut = CIC(2, decimation, 1, 9)
    run_step_test(dut, 1)
    run_step_test(dut, 0)


@pytest.mark.parametrize('order', [1, 2, 3, 4])
def test_sine(order):
    decim = 256
    dut = CIC(order, decim, 8, 8)

    n = np.arange(0, decim * 10)
    data = 255 * ((np.sin(2 * np.pi * n / (10 * decim)) + 1) / 2)
    data = [int(d) for d in data]

    run_sim(dut, data, 10)

    h = dut.get_impulsive_response()
    expected = np.convolve(data, h)[decim - 1::decim] >> (8 * order)
    result = np.array(dut.output._received)
    assert (expected[:len(result)] == result).any()
