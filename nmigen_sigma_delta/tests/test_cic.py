from nmigen.back.pysim import Simulator
from nmigen_sigma_delta.cic import CIC
import random
import math

def test_paper_result():
    discared = CIC(4, 25, 16, 16).get_discared_bits()
    assert discared == [1, 6, 9, 13, 14, 15, 16, 17]

def test_cic():
    decimation = 256
    func = lambda p: int(255 * ((math.sin(p) + 1) / 2))
    data = [func(2 * math.pi * n / (100 *decimation)) for n in range(200 * decimation)]

    dut = CIC(2, decimation, 8, 8)
    sim = Simulator(dut)
    sim.add_clock(10e-9, domain='sync')
    sim.add_sync_process(dut.input.send_driver(data))
    sim.add_sync_process(dut.output.recv_driver(len(data) // decimation))
    sim.run()

    # TODO: add some assertios here

def test_one_bit_cic():
    decimation = 1024

    data = [random.getrandbits(1) for _ in range(decimation * 40)]
    dut = CIC(4, decimation, 1, 10)
    sim = Simulator(dut)
    sim.add_clock(10e-9, domain='sync')
    sim.add_sync_process(dut.input.send_driver(data))
    sim.add_sync_process(dut.output.recv_driver(len(data) // decimation))
    sim.run()

    # TODO: add some assertios here
