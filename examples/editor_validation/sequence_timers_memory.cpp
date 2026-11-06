#include <plc.hpp>

// 10 s warmup, 10 s pulse, then 10 s off-delay. All milestones survive until RESET.
plc::Ton warmup{0, 1000, 10};
plc::Pulse process_pulse{1, 1000, 10};
plc::Tof run_on{2, 1000, 10};
plc::i16 phase = 0;
plc::i16 accepted = 0;
plc::i16 completed = 0;
plc::i16 aborted = 0;
plc::i16 rejected = 0;
plc::i16 reason = 0;
bool warm_seen = false;
bool pulse_seen = false;
bool tail_seen = false;
bool complete_seen = false;
bool abort_seen = false;
bool reject_seen = false;

void scan() {
    bool start = plc::read_m(800);
    bool permit = plc::read_m(801);
    bool stop = plc::read_m(802);
    bool reset = plc::read_m(803);
    bool start_edge = plc::m_rising(800);

    if (reset) {
        phase = 0;
        accepted = 0;
        completed = 0;
        aborted = 0;
        rejected = 0;
        reason = 4;
        warm_seen = false;
        pulse_seen = false;
        tail_seen = false;
        complete_seen = false;
        abort_seen = false;
        reject_seen = false;
    } else {
        if (stop || !permit) {
            if (phase > 0 && phase < 4) {
                phase = 0;
                aborted = plc::add_i16(aborted, 1);
                abort_seen = true;
                if (stop) { reason = 2; }
                else { reason = 3; }
            }
        }
        if (start_edge) {
            if (permit && !stop && (phase == 0 || phase == 4)
                && !process_pulse.done() && !run_on.done()) {
                phase = 1;
                accepted = plc::add_i16(accepted, 1);
                reason = 0;
            } else {
                rejected = plc::add_i16(rejected, 1);
                reject_seen = true;
                reason = 5;
            }
        }
    }

    bool safe = permit && !stop && !reset;
    bool warm_done = warmup.update(phase == 1 && safe);
    if (phase == 1 && warm_done) {
        warm_seen = true;
        phase = 2;
    }
    bool pulse_active = process_pulse.update(phase == 2 && safe);
    if (phase == 2) {
        if (pulse_active) { pulse_seen = true; }
        else { phase = 3; }
    }
    bool tail_active = run_on.update(phase == 2 && pulse_active && safe);
    if (phase == 3 && safe) {
        tail_seen = true;
        if (!tail_active) {
            phase = 4;
            completed = plc::add_i16(completed, 1);
            complete_seen = true;
            reason = 6;
        }
    }

    plc::i16 busy = 0;
    if (pulse_active || tail_active) { busy = 1; }
    plc::write_word(180, phase);
    plc::write_word(181, accepted);
    plc::write_word(182, completed);
    plc::write_word(183, aborted);
    plc::write_word(184, rejected);
    plc::write_word(185, warmup.value());
    plc::write_word(186, process_pulse.value());
    plc::write_word(187, run_on.value());
    plc::write_word(188, busy);
    plc::write_word(189, reason);
    plc::write_word(190, warmup.preset());
    plc::write_word(191, process_pulse.preset());
    plc::write_word(192, run_on.preset());
    plc::write_m(704, phase == 0);
    plc::write_m(705, phase == 1 && safe);
    plc::write_m(706, phase == 2 && pulse_active && safe);
    plc::write_m(707, phase == 3 && tail_active && safe);
    plc::write_m(708, complete_seen);
    plc::write_m(709, warm_seen);
    plc::write_m(710, pulse_seen);
    plc::write_m(711, tail_seen);
    plc::write_m(712, abort_seen);
    plc::write_m(713, reject_seen);
    plc::write_m(714, permit);
    plc::write_m(715, stop);
    plc::write_m(716, reset);
    plc::write_m(717, start);
    plc::write_m(718, pulse_active);
    plc::write_m(719, tail_active);
}
