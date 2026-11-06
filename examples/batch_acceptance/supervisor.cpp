#include <plc.hpp>

plc::Ton on_delay{0, 10, 3};
plc::Tof off_delay{1, 10, 2};
plc::Pulse pulse_timer{2, 10, 2};
plc::Clock light_clock{20};
plc::Counter counter{0, 2};
plc::Fifo fifo{0};
plc::Lifo lifo{1};
plc::RisingEdge rise;
plc::FallingEdge fall;
bool latched = false;
plc::i16 sequence_step = 0;

void scan() {
    plc::i16 scenario = plc::read_word(0);
    if (!plc::input(19)) {
        scenario = 0;
        if (plc::input(20)) { scenario = plc::add_i16(scenario, 1); }
        if (plc::input(21)) { scenario = plc::add_i16(scenario, 2); }
        if (plc::input(22)) { scenario = plc::add_i16(scenario, 4); }
        if (plc::input(23)) { scenario = plc::add_i16(scenario, 8); }
        plc::write_word(0, scenario);
    }
    bool reset = plc::input(0);
    if (reset) { plc::clear_arithmetic_error(); }
    bool rising = rise.update(plc::input(1));
    bool falling = fall.update(plc::input(1));
    if (reset || scenario != 1) { latched = false; }
    else if (rising) { latched = !latched; }
    if (reset || scenario != 4) { sequence_step = 0; }
    else if (rising) {
        sequence_step = plc::rem_i16(plc::add_i16(sequence_step, 1), 3);
    }

    bool timer_enable = scenario == 2 && !reset && plc::input(1);
    bool ton_q = on_delay.update(timer_enable);
    bool tof_q = off_delay.update(timer_enable);
    bool pulse_q = pulse_timer.update(timer_enable);
    bool lights_enabled = scenario == 7 && !reset && plc::input(1) && !plc::input(2);
    bool light_phase = light_clock.update(lights_enabled);
    counter.update(reset || scenario != 4, false,
                   scenario == 4 && plc::input(1), scenario == 4 && plc::input(2));
    if (plc::input(3)) { fifo.set_input(22); lifo.set_input(22); }
    else { fifo.set_input(11); lifo.set_input(11); }
    if (scenario == 3 && plc::input(4)) { fifo.set_output(42); lifo.set_output(42); }
    fifo.update(reset || scenario != 3,
                scenario == 3 && plc::input(1), scenario == 3 && plc::input(2));
    lifo.update(reset || scenario != 3,
                scenario == 3 && plc::input(1), scenario == 3 && plc::input(2));

    plc::i16 result = 0;
    if (scenario == 0) {
        result = plc::read_input_bits_i16(0, 16);
        plc::write_word(10, plc::read_input_bits_i16(16, 8));
    } else if (scenario == 1) {
        if (plc::input(1)) { result = plc::add_i16(result, 1); }
        if (!plc::input(2)) { result = plc::add_i16(result, 2); }
        if (plc::input(1) && plc::input(2)) { result = plc::add_i16(result, 4); }
        if (plc::input(1) || plc::input(2)) { result = plc::add_i16(result, 8); }
        if (plc::input(1) != plc::input(2)) { result = plc::add_i16(result, 16); }
        if (rising) { result = plc::add_i16(result, 32); }
        if (falling) { result = plc::add_i16(result, 64); }
        if (latched) { result = plc::add_i16(result, 128); }
    } else if (scenario == 2) {
        if (ton_q) { result = plc::add_i16(result, 1); }
        if (tof_q) { result = plc::add_i16(result, 2); }
        if (pulse_q) { result = plc::add_i16(result, 4); }
        plc::write_word(10, on_delay.value());
        plc::write_word(11, off_delay.value());
        plc::write_word(12, pulse_timer.value());
    } else if (scenario == 3) {
        if (fifo.empty()) { result = plc::add_i16(result, 1); }
        if (fifo.full()) { result = plc::add_i16(result, 2); }
        if (lifo.empty()) { result = plc::add_i16(result, 4); }
        if (lifo.full()) { result = plc::add_i16(result, 8); }
        if (fifo.output() == 11) { result = plc::add_i16(result, 16); }
        if (fifo.output() == 22) { result = plc::add_i16(result, 32); }
        if (lifo.output() == 11) { result = plc::add_i16(result, 64); }
        if (lifo.output() == 22) { result = plc::add_i16(result, 128); }
        if (fifo.output() == 42) { result = plc::add_i16(result, 256); }
        if (lifo.output() == 42) { result = plc::add_i16(result, 512); }
        plc::write_word(10, fifo.output());
        plc::write_word(11, lifo.output());
    } else if (scenario == 4) {
        plc::i16 limit = 3;
        if (plc::input(3)) { limit = 5; }
        plc::i16 sum = 0;
        for (plc::i16 term = 1; term <= limit; term = plc::add_i16(term, 1)) {
            sum = plc::add_i16(sum, term);
        }
        result = sequence_step;
        if (counter.done()) { result = plc::add_i16(result, 16); }
        if (counter.value() == 0) { result = plc::add_i16(result, 32); }
        if (counter.value() == 1) { result = plc::add_i16(result, 64); }
        if (counter.value() == 2) { result = plc::add_i16(result, 128); }
        if (sum == 6) { result = plc::add_i16(result, 256); }
        if (sum == 15) { result = plc::add_i16(result, 512); }
        plc::write_word(10, sequence_step);
        plc::write_word(11, counter.value());
        plc::write_word(12, sum);
    } else if (scenario == 5) {
        plc::i16 a = plc::read_word(20);
        plc::i16 b = plc::read_word(21);
        result = plc::add_i16(a, b);
        plc::write_word(10, plc::sub_i16(a, b));
        plc::write_word(11, plc::mul_i16(a, b));
        if (b != 0) {
            plc::write_word(12, plc::div_i16(a, b));
            plc::write_word(13, plc::rem_i16(a, b));
        }
        plc::write_word(14, plc::sqrt_i16(plc::read_word(22)));
        if (plc::system(18)) { plc::write_word(15, 1); }
        else { plc::write_word(15, 0); }
    } else if (scenario == 7) {
        if (light_phase) { result = plc::add_i16(result, 1); }
        if (lights_enabled && !light_phase) { result = plc::add_i16(result, 2); }
        if (lights_enabled) { result = plc::add_i16(result, 4); }
        if (plc::input(2)) { result = plc::add_i16(result, 8); }
    } else {
        result = -1;
    }
    plc::write_word(1, result);
    plc::write_output_bits_i16(0, 16, result);
}
