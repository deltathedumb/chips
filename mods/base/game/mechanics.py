"""What a FOUNDRY game can do: its verbs and its derived numbers.

Every name here is bound onto the engine's `Game` by `api.method`, which is
why they are written with `self` despite living in a mod. The engine has no
idea a wafer exists; after this runs, `g.buy_stepper()` works anyway.

    fab     derived costs and the process node
    system  bandwidth, threads, the buffer and the burst
    floor   making chips and selling them
    units   hardware bought in bulk, on a compounding curve
    ticks   what each act does with a second
"""

from base.game import fab, floor, system, ticks, units


def install(api):
    # fab
    api.method("node", fab.node)
    api.method("buffer_bytes", fab.buffer_bytes)
    api.method("compute_rate", fab.compute_rate)
    api.method("data_rate", fab.data_rate)
    api.method("ops_rate", fab.ops_rate)
    api.method("stepper_cost", fab.stepper_cost)
    api.method("scanner_cost", fab.scanner_cost)
    api.method("design_win_cost", fab.design_win_cost)
    # system
    api.method("BURST_SECONDS", system.BURST_SECONDS)
    api.method("BURST_COOLDOWN", system.BURST_COOLDOWN)
    api.method("burst_seconds", system.burst_seconds)
    api.method("burst_cooldown", system.burst_cooldown)
    api.method("burst_cost", system.burst_cost)
    api.method("burst_yield", system.burst_yield)
    api.method("fire_burst", system.fire_burst)
    api.method("upgrade_burst", system.upgrade_burst)
    api.method("free_bandwidth", system.free_bandwidth)
    api.method("bandwidth_ratio", system.bandwidth_ratio)
    api.method("thread_cost", floor.thread_cost)
    api.method("buffer_cost", floor.buffer_cost)
    api.method("buffer_chip_cost", floor.buffer_chip_cost)
    api.method("stock_cap", floor.stock_cap)
    api.method("buffer_in_stock", floor.buffer_in_stock)
    api.method("buffer_restock_in", floor.buffer_restock_in)
    api.method("_tick_buffer_stock", floor._tick_buffer_stock)
    api.method("why_not_thread", floor.why_not_thread)
    api.method("why_not_buffer", floor.why_not_buffer)
    # floor
    api.method("order_flow", floor.order_flow)
    api.method("chip_rate", floor.chip_rate)
    api.method("effective_yield", floor.effective_yield)
    api.method("dies_available", floor.dies_available)
    api.method("power_demand", floor.power_demand)
    api.method("power_supply", floor.power_supply)
    api.method("battery_capacity", floor.battery_capacity)
    api.method("firmware_allocated", floor.firmware_allocated)
    api.method("firmware_free", floor.firmware_free)
    api.method("make_chip", floor.make_chip)
    api.method("buy_wafers", floor.buy_wafers)
    api.method("buy_stepper", floor.buy_stepper)
    api.method("buy_scanner", floor.buy_scanner)
    api.method("buy_design_win", floor.buy_design_win)
    api.method("buy_thread", floor.buy_thread)
    api.method("buy_buffer", floor.buy_buffer)
    # units
    api.method("UNIT_COST", units.UNIT_COST)
    api.method("UNIT_RATE", units.UNIT_RATE)
    api.method("UNIT_ATTR", units.UNIT_ATTR)
    api.method("UNIT_LABEL", units.UNIT_LABEL)
    api.method("unit_price", units.unit_price)
    api.method("UNIT_TECH", units.UNIT_TECH)
    api.method("buy_units", units.buy_units)
    api.method("launch_seed_fabs", units.launch_seed_fabs)
    # ticks
    api.method("adjust_price", ticks.adjust_price)
    api.method("price_step", ticks.price_step)
    api.method("set_price", ticks.set_price)
    api.method("clearing_price", ticks.clearing_price)
    api.method("_tick_autoprice", ticks._tick_autoprice)
    api.method("adjust_firmware", ticks.adjust_firmware)
    api.method("_consume", ticks._consume)
    api.method("_tick_fab", ticks._tick_fab)
    api.method("_tick_lithosphere", ticks._tick_lithosphere)
    api.method("act_target", ticks.act_target)
    api.method("_tick_light_cone", ticks._tick_light_cone)
    api.method("_tick_system", ticks._tick_system)
    api.method("_tick_bandwidth", ticks._tick_bandwidth)
    # Two systems run underneath every act, whatever it is doing.
    api.system_tick(ticks._tick_system)
    api.system_tick(lambda g, dt: g._tick_bandwidth())
    api.system_tick(lambda g, dt: g._tick_buffer_stock(dt))
    api.system_tick(lambda g, dt: g._tick_autoprice(dt))
